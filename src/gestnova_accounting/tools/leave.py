"""Leave tools: checkLeaveEntitlement, getVacationBalance, getLeaveCalendar."""
from __future__ import annotations
from datetime import date
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup


class CheckLeaveEntitlementTool(BaseTool):
    name = "checkLeaveEntitlement"
    description = "Return days entitled for a given leave reason, citing the legal reference."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "reason": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "requires_displacement": {"type": "boolean", "default": False},
        },
        "required": ["country", "reason", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "leave_reasons", date.fromisoformat(args["date"]))
        reason = args["reason"]
        spec = rule.data.get(reason)
        if not spec:
            return {
                "status": "unknown_reason",
                "reason": reason,
                "hint": "Reason not catalogued. May need convenio colectivo or be unpaid leave.",
            }
        days = spec.get("days")
        if args.get("requires_displacement") and spec.get("days_if_displacement"):
            days = spec["days_if_displacement"]
        return {
            "status": "ok",
            "reason": reason,
            "days": days,
            "unit": spec.get("unit", "working"),
            "legal_ref": spec.get("legal_ref"),
            "notes": spec.get("notes"),
            "rules_applied": [
                {"rule": "leave_reasons", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        }


class GetVacationBalanceTool(BaseTool):
    name = "getVacationBalance"
    description = "Compute vacation days remaining for an employee in a given year."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "year": {"type": "integer"},
            "daysAlreadyUsed": {"type": "number", "default": 0},
        },
        "required": ["country", "year"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "vacation_days_minimum", date(args["year"], 6, 1))
        natural = int(rule.data["natural_days"])
        working = int(rule.data["working_days_equivalent"])
        used = float(args.get("daysAlreadyUsed", 0))
        return {
            "total_natural": natural,
            "working_days_equivalent": working,
            "used": used,
            "remaining_working_days": working - int(used),
            "rules_applied": [
                {"rule": "vacation_days_minimum", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        }


class GetLeaveCalendarTool(BaseTool):
    name = "getLeaveCalendar"
    description = "Return national holidays for the given country and year."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "year": {"type": "integer"},
        },
        "required": ["country", "year"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "national_holidays_default", date(args["year"], 6, 1))
        return {
            "country": "ES",
            "year": args["year"],
            "holidays": rule.data,
            "rules_applied": [
                {"rule": "national_holidays_default", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        }
