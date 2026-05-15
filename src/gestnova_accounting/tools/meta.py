"""Meta tools: lookupLegalReference, getApplicableRules, listSupportedCountries, getCountryFiscalProfile."""
from __future__ import annotations
from datetime import date
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup


class LookupLegalReferenceTool(BaseTool):
    name = "lookupLegalReference"
    description = "Search loaded rules for keyword matches; returns rule, source, and effective dates."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "query": {"type": "string"},
        },
        "required": ["country", "query"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        # Tokenize query so "IRPF brackets" matches "irpf_brackets" + source text.
        tokens = [t for t in args["query"].lower().replace("_", " ").split() if t]
        matches = []
        for (c, k), rules in get_lookup()._rules.items():
            if c != args["country"]:
                continue
            for r in rules:
                hay = f"{r.rule} {r.source}".lower().replace("_", " ")
                if all(tok in hay for tok in tokens):
                    matches.append({
                        "rule": r.rule,
                        "effective_from": str(r.effective_from),
                        "effective_until": str(r.effective_until) if r.effective_until else None,
                        "source": r.source,
                    })
                    break
        if not matches:
            return {
                "matches": [],
                "hint": f"No rules in pack {args['country']} match '{args['query']}'. Try a broader term or check if the area is covered.",
            }
        return {"matches": matches}


_AREA_PREFIXES = {
    "payroll": ["irpf", "isr", "ss_", "imss", "exempt_concepts"],
    "iva": ["vat_rates"],
    "leave": ["vacation", "leave_", "national_holidays"],
    "time_tracking": ["max_", "minimum_", "time_record"],
    "retention": ["professional_retention"],
}


class GetApplicableRulesTool(BaseTool):
    name = "getApplicableRules"
    description = "Return all currently-applicable rules for a given area + country + date."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "area": {"type": "string"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "area", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        prefixes = _AREA_PREFIXES.get(args["area"], [args["area"]])
        on = date.fromisoformat(args["date"])
        rules = []
        for prefix in prefixes:
            for r in get_lookup().get_all_for_area(args["country"], prefix, on):
                rules.append({
                    "rule": r.rule,
                    "effective_from": str(r.effective_from),
                    "effective_until": str(r.effective_until) if r.effective_until else None,
                    "source": r.source,
                })
        seen = set()
        unique = []
        for r in rules:
            if r["rule"] in seen:
                continue
            seen.add(r["rule"])
            unique.append(r)
        return {"area": args["area"], "country": args["country"], "date": args["date"], "rules": unique}


class ListSupportedCountriesTool(BaseTool):
    name = "listSupportedCountries"
    description = "Return ISO codes of countries with legal packs loaded."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"countries": get_lookup().supported_countries()}


class GetCountryFiscalProfileTool(BaseTool):
    name = "getCountryFiscalProfile"
    description = "Quick reference summary of a country's main fiscal parameters."
    input_schema = {
        "type": "object",
        "properties": {"country": {"type": "string", "enum": ["ES", "MX"]}},
        "required": ["country"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        on = date.today()
        country = args["country"]
        summary: dict[str, Any] = {}
        for key in ["vat_rates", "max_daily_hours", "max_overtime_yearly", "vacation_days_minimum"]:
            try:
                summary[key] = get_lookup().get(country, key, on).data
            except Exception:
                pass
        return {"country": country, "summary": summary}
