"""Time-tracking tools: clockInLegal, getJornadaStatus, getOvertimeBalance.

Principle (Art. 34.9 ET): we ALWAYS record the real timestamp. The tool
classifies and alerts; it never maquillates the hour.
"""
from __future__ import annotations
from datetime import datetime, date, time
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup, _result_to_jsonable


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _is_within(working: dict, ts: datetime) -> bool:
    """Check if `ts` falls within the working-hours window for that calendar day."""
    start_t = _parse_hhmm(working["start"])
    end_t = _parse_hhmm(working["end"])
    return start_t <= ts.time() <= end_t


def _hours_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600.0


class ClockInLegalTool(BaseTool):
    name = "clockInLegal"
    description = (
        "Register a clock-in/out event. Always records the REAL timestamp "
        "(Art. 34.9 ET). Classifies as regular | overtime | outside-hours and "
        "raises legal alerts when applicable. May prompt the caller to confirm "
        "real work outside working hours."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "timestamp": {"type": "string", "format": "date-time"},
            "intent": {"type": "string", "enum": ["in", "out", "break-start", "break-end"]},
            "workingHours": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
                "required": ["start", "end"],
            },
            "previousEntriesToday": {"type": "array", "items": {"type": "object"}, "default": []},
            "overtimeYTD": {"type": "number", "default": 0},
            "declaredAsRealWork": {"type": "boolean", "default": False},
        },
        "required": ["country", "timestamp", "intent", "workingHours"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        ts = datetime.fromisoformat(args["timestamp"])
        on_date = ts.date()
        intent = args["intent"]
        working = args["workingHours"]
        prev = args.get("previousEntriesToday", [])
        ot_ytd = float(args.get("overtimeYTD", 0))

        max_daily = float(get_lookup().get("ES", "max_daily_hours", on_date).data["hours"])
        max_overtime = float(get_lookup().get("ES", "max_overtime_yearly", on_date).data["hours"])

        worked = 0.0
        last_in: datetime | None = None
        for e in prev:
            t = datetime.fromisoformat(e["timestamp"])
            if e["intent"] == "in":
                last_in = t
            elif e["intent"] == "out" and last_in:
                worked += _hours_between(last_in, t)
                last_in = None
        if intent == "out" and last_in:
            worked += _hours_between(last_in, ts)

        within = _is_within(working, ts)
        classification = "regular"
        alerts: list[dict] = []
        prompt = {"type": "none"}

        if not within:
            classification = "outside-hours"
            prompt = {
                "type": "confirm_real_work",
                "message": (
                    f"Tu fichaje a las {ts.strftime('%H:%M')} está fuera del horario laboral "
                    f"({working['start']}-{working['end']}). ¿Estabas trabajando realmente?"
                ),
            }

        if worked > max_daily:
            alerts.append({
                "level": "warning",
                "code": "exceeds_max_daily_hours",
                "message": f"Llevas {worked:.2f}h hoy, máximo legal {max_daily}h (Art. 34.3 ET).",
                "legalRef": "ET Art. 34.3",
            })

        overtime_today = max(0.0, worked - max_daily)
        overtime_remaining = max_overtime - (ot_ytd + overtime_today)
        alerts.append({
            "level": "info" if overtime_remaining > 0 else "warning",
            "code": "overtime_budget",
            "message": f"Saldo horas extra: {ot_ytd + overtime_today:.1f}h usadas, {overtime_remaining:.1f}h disponibles (límite 80h/año Art. 35.2 ET).",
            "legalRef": "ET Art. 35.2",
        })

        rule_daily = get_lookup().get("ES", "max_daily_hours", on_date)
        rule_ot = get_lookup().get("ES", "max_overtime_yearly", on_date)
        rule_record = get_lookup().get("ES", "time_record_obligation", on_date)

        return _result_to_jsonable({
            "registered": True,
            "recorded_timestamp": args["timestamp"],
            "classification": classification,
            "alerts": alerts,
            "cumulative": {
                "daily_hours": round(worked, 2),
                "overtime_year_to_date": round(ot_ytd + overtime_today, 2),
                "overtime_remaining": round(overtime_remaining, 2),
            },
            "prompt": prompt,
            "rules_applied": [
                {"rule": "max_daily_hours", "effective_from": str(rule_daily.effective_from), "source": rule_daily.source},
                {"rule": "max_overtime_yearly", "effective_from": str(rule_ot.effective_from), "source": rule_ot.source},
                {"rule": "time_record_obligation", "effective_from": str(rule_record.effective_from), "source": rule_record.source},
            ],
        })


class GetJornadaStatusTool(BaseTool):
    name = "getJornadaStatus"
    description = "Aggregate worked hours and overtime for an employee in a period."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "entries": {"type": "array", "items": {"type": "object"}},
            "periodStart": {"type": "string", "format": "date"},
            "periodEnd": {"type": "string", "format": "date"},
            "workingHours": {"type": "object"},
        },
        "required": ["country", "entries", "periodStart", "periodEnd", "workingHours"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        max_daily = float(get_lookup().get("ES", "max_daily_hours", date.fromisoformat(args["periodStart"])).data["hours"])
        max_weekly = float(get_lookup().get("ES", "max_weekly_hours", date.fromisoformat(args["periodStart"])).data["hours"])

        by_day: dict[date, list[dict]] = {}
        for e in args["entries"]:
            d = datetime.fromisoformat(e["timestamp"]).date()
            by_day.setdefault(d, []).append(e)

        total = 0.0
        overtime = 0.0
        alerts: list[dict] = []
        for d, entries in by_day.items():
            entries.sort(key=lambda x: x["timestamp"])
            worked = 0.0
            last_in: datetime | None = None
            for e in entries:
                t = datetime.fromisoformat(e["timestamp"])
                if e["intent"] == "in":
                    last_in = t
                elif e["intent"] == "out" and last_in:
                    worked += _hours_between(last_in, t)
                    last_in = None
            total += worked
            if worked > max_daily:
                ot = worked - max_daily
                overtime += ot
                alerts.append({
                    "level": "warning",
                    "code": "daily_overtime",
                    "message": f"{d.isoformat()}: {worked:.1f}h trabajadas, supera límite diario {max_daily}h por {ot:.1f}h",
                    "legalRef": "ET Art. 34.3",
                })

        if total > max_weekly:
            alerts.append({
                "level": "warning",
                "code": "weekly_overtime",
                "message": f"{total:.1f}h en el periodo, supera 40h promedio semanal",
                "legalRef": "ET Art. 34.1",
            })

        return _result_to_jsonable({
            "total_hours": round(total, 2),
            "overtime_hours": round(overtime, 2),
            "alerts": alerts,
        })


class GetOvertimeBalanceTool(BaseTool):
    name = "getOvertimeBalance"
    description = "Return overtime budget remaining for the year (Art. 35.2 ET — 80h/year ES)."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "year": {"type": "integer"},
            "overtimeUsed": {"type": "number"},
        },
        "required": ["country", "year", "overtimeUsed"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "max_overtime_yearly", date(args["year"], 6, 1))
        limit = float(rule.data["hours"])
        used = float(args["overtimeUsed"])
        return {
            "limit": limit,
            "used": used,
            "remaining": round(limit - used, 2),
            "rules_applied": [
                {"rule": "max_overtime_yearly", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        }
