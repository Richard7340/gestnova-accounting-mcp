"""Compliance tools — applicability resolution, template lookup, status checks.

Reads `packs/<country>/compliance/applicability.yaml` to determine which
documents apply to a Company given its sector + size. Reads template YAMLs
to return the structure + required fields. Caller (Ian / livekit) then
generates concrete ComplianceDocInstance rows per company.
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup, _result_to_jsonable


class GetApplicableComplianceDocsTool(BaseTool):
    name = "getApplicableComplianceDocs"
    description = (
        "Given country + sector + headcount, return the list of compliance "
        "documents that apply to a company, citing the legal threshold."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "sector": {"type": "string", "description": "e.g. 'consultoria', 'financiero', 'industrial'"},
            "workers": {"type": "integer", "description": "Total number of workers"},
            "date": {"type": "string", "format": "date", "default": "2026-01-01"},
        },
        "required": ["country", "sector", "workers"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        country = args["country"]
        sector = args["sector"]
        workers = int(args["workers"])
        on = date.fromisoformat(args.get("date", date.today().isoformat()))

        rule = get_lookup().get(country, "compliance_applicability", on)
        applicable: list[str] = []
        reasoning: list[dict] = []

        for r in rule.data["rules"]:
            condition = r.get("if", {})
            # workers_min check
            if "workers_min" in condition and workers < condition["workers_min"]:
                continue
            # sector_in check
            if "sector_in" in condition and sector not in condition["sector_in"]:
                continue
            # If passed all filters → add documents
            for doc in r.get("always_required", []) + r.get("adds", []):
                if doc not in applicable:
                    applicable.append(doc)
            reasoning.append({"matched": condition, "reason": r.get("reason", "")})

        return _result_to_jsonable({
            "country": country,
            "sector": sector,
            "workers": workers,
            "applicable_documents": applicable,
            "reasoning": reasoning,
            "rules_applied": [
                {"rule": "compliance_applicability", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class GetComplianceTemplateTool(BaseTool):
    name = "getComplianceTemplate"
    description = (
        "Fetch a compliance document template (name, description, sections, "
        "required_fields, review_period_months, legal source) for the given "
        "country + documentType + date."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "documentType": {"type": "string", "description": "e.g. 'lopd-rgpd', 'plan-igualdad', 'nom-035-stps'"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "documentType"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        country = args["country"]
        doc_type = args["documentType"]
        on = date.fromisoformat(args.get("date", date.today().isoformat()))

        # Templates live under their own rule key 'compliance_template' but indexed
        # by document_type in data. We need to scan all compliance_template rules
        # for this country to find the one matching doc_type.
        lookup = get_lookup()
        candidates = lookup._rules.get((country, "compliance_template"), [])
        for r in candidates:
            if (
                r.data.get("document_type") == doc_type
                and r.effective_from <= on
                and (r.effective_until is None or on <= r.effective_until)
            ):
                return _result_to_jsonable({
                    "country": country,
                    "document_type": doc_type,
                    "template": r.data,
                    "rules_applied": [
                        {"rule": "compliance_template", "effective_from": str(r.effective_from), "source": r.source}
                    ],
                })
        return {
            "error": "template_not_found",
            "country": country,
            "documentType": doc_type,
            "hint": f"No template registered for '{doc_type}' in pack {country}.",
        }


class CheckComplianceStatusTool(BaseTool):
    name = "checkComplianceStatus"
    description = (
        "Compute the status of a compliance document instance: valid | "
        "expiring_soon | expired | review_needed. Uses the template's "
        "review_period_months and the provided validFrom/validUntil."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "documentType": {"type": "string"},
            "validFrom": {"type": "string", "format": "date"},
            "validUntil": {"type": "string", "format": "date", "description": "Optional. If null, computed from template review_period_months."},
            "today": {"type": "string", "format": "date", "default": "today"},
        },
        "required": ["country", "documentType", "validFrom"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        country = args["country"]
        doc_type = args["documentType"]
        valid_from = date.fromisoformat(args["validFrom"])
        today_arg = args.get("today", "today")
        today = date.today() if today_arg == "today" else date.fromisoformat(today_arg)

        # Get template to know review period
        lookup = get_lookup()
        candidates = lookup._rules.get((country, "compliance_template"), [])
        template = None
        for r in candidates:
            if r.data.get("document_type") == doc_type and r.effective_from <= today:
                template = r
                break
        if not template:
            return {"error": "template_not_found", "country": country, "documentType": doc_type}

        period_months = int(template.data.get("review_period_months", 12))
        # Compute valid_until: validFrom + period_months
        if args.get("validUntil"):
            valid_until = date.fromisoformat(args["validUntil"])
        else:
            valid_until_year = valid_from.year + (period_months // 12)
            valid_until_month = valid_from.month + (period_months % 12)
            if valid_until_month > 12:
                valid_until_year += 1
                valid_until_month -= 12
            try:
                valid_until = date(valid_until_year, valid_until_month, valid_from.day)
            except ValueError:
                # End-of-month edge case
                valid_until = date(valid_until_year, valid_until_month, 28)

        days_to_expiry = (valid_until - today).days

        if days_to_expiry < 0:
            status = "expired"
        elif days_to_expiry < 30:
            status = "expiring_soon"
        elif days_to_expiry < 90:
            status = "review_recommended"
        else:
            status = "valid"

        return {
            "country": country,
            "document_type": doc_type,
            "status": status,
            "valid_from": str(valid_from),
            "valid_until": str(valid_until),
            "days_to_expiry": days_to_expiry,
            "review_period_months": period_months,
            "rules_applied": [
                {"rule": "compliance_template", "effective_from": str(template.effective_from), "source": template.source}
            ],
        }


class DetectComplianceUpdatesTool(BaseTool):
    name = "detectComplianceUpdates"
    description = (
        "Given a list of compliance instances ({documentType, templateVersion}) "
        "compare with current templates. Returns docs whose template has been "
        "updated since the instance was created → review_needed."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "instances": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "documentType": {"type": "string"},
                        "templateVersion": {"type": "string", "description": "Date the template the doc was generated from (effective_from)"},
                    },
                    "required": ["documentType", "templateVersion"],
                },
            },
            "today": {"type": "string", "format": "date", "default": "today"},
        },
        "required": ["country", "instances"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        country = args["country"]
        today_arg = args.get("today", "today")
        today = date.today() if today_arg == "today" else date.fromisoformat(today_arg)

        lookup = get_lookup()
        candidates = lookup._rules.get((country, "compliance_template"), [])
        # Index current templates by document_type
        current: dict[str, Any] = {}
        for r in candidates:
            doc_type = r.data.get("document_type")
            if not doc_type:
                continue
            if r.effective_from <= today and (r.effective_until is None or today <= r.effective_until):
                # Prefer most recent effective_from
                existing = current.get(doc_type)
                if not existing or r.effective_from > existing.effective_from:
                    current[doc_type] = r

        updates: list[dict] = []
        for inst in args["instances"]:
            doc_type = inst["documentType"]
            inst_version = date.fromisoformat(inst["templateVersion"])
            curr = current.get(doc_type)
            if not curr:
                continue
            if curr.effective_from > inst_version:
                updates.append({
                    "document_type": doc_type,
                    "instance_template_version": str(inst_version),
                    "current_template_version": str(curr.effective_from),
                    "current_source": curr.source,
                    "action": "review_needed",
                    "reason": f"Template updated on {curr.effective_from.isoformat()}, instance was generated from {inst_version.isoformat()}.",
                })

        return {
            "country": country,
            "checked_at": str(today),
            "updates_detected": updates,
            "no_updates_needed": len(updates) == 0,
        }
