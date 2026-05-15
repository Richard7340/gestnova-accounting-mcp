"""End-to-end test: simulate a full day of operations for an ES employee."""
from decimal import Decimal
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_full_day_workflow_es():
    server = build_server()

    # Ping
    ping = await server.call_tool("ping", {})
    assert ping["status"] == "ok"

    # List countries — ES must be loaded
    countries = await server.call_tool("listSupportedCountries", {})
    assert "ES" in countries["countries"]

    # Fiscal profile of ES
    profile = await server.call_tool("getCountryFiscalProfile", {"country": "ES"})
    assert profile["summary"]["max_daily_hours"]["hours"] == 9

    # Employee clocks in at 09:30
    clock_in = await server.call_tool("clockInLegal", {
        "country": "ES",
        "timestamp": "2026-05-15T09:30:00+02:00",
        "intent": "in",
        "workingHours": {"start": "09:00", "end": "19:00"},
        "previousEntriesToday": [],
    })
    assert clock_in["classification"] == "regular"

    # Payroll for May
    payroll = await server.call_tool("calculatePayroll", {
        "country": "ES",
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [{"code": "plus_transport", "amount": "80", "exempt": True}],
    })
    assert payroll["liquido"] == "1821.62"

    # Simulate adding 200€ bonus
    sim = await server.call_tool("simulatePayrollChange", {
        "country": "ES",
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "currentExtras": [{"code": "plus_transport", "amount": "80", "exempt": True}],
        "addExtras": [{"code": "bonus", "amount": "200", "exempt": False}],
        "removeExtraCodes": [],
    })
    assert sim["current"]["liquido"] == "1821.62"
    assert Decimal(sim["simulated"]["liquido"]) > Decimal(sim["current"]["liquido"])

    # Request marriage leave
    marriage = await server.call_tool("checkLeaveEntitlement", {
        "country": "ES", "reason": "matrimonio", "date": "2026-06-14",
    })
    assert marriage["days"] == 15

    # Overtime balance
    ot = await server.call_tool("getOvertimeBalance", {"country": "ES", "year": 2026, "overtimeUsed": 23.5})
    assert ot["remaining"] == 56.5

    # Clock out at midnight → outside-hours alert
    clock_out = await server.call_tool("clockInLegal", {
        "country": "ES",
        "timestamp": "2026-05-16T00:00:00+02:00",
        "intent": "out",
        "workingHours": {"start": "09:00", "end": "19:00"},
        "previousEntriesToday": [
            {"timestamp": "2026-05-15T09:30:00+02:00", "intent": "in"},
        ],
        "overtimeYTD": 23.5,
    })
    assert clock_out["classification"] == "outside-hours"
    assert clock_out["prompt"]["type"] == "confirm_real_work"
    assert any(a["code"] == "exceeds_max_daily_hours" for a in clock_out["alerts"])
