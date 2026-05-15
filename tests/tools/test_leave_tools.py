import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_check_marriage_leave_15_days():
    server = build_server()
    res = await server.call_tool("checkLeaveEntitlement", {
        "country": "ES",
        "reason": "matrimonio",
        "date": "2026-06-14",
    })
    assert res["days"] == 15
    assert res["unit"] == "natural"
    assert res["legal_ref"] == "Art. 37.3.a ET"


@pytest.mark.asyncio
async def test_check_sibling_funeral_1_day_2_if_displacement():
    server = build_server()
    res = await server.call_tool("checkLeaveEntitlement", {
        "country": "ES",
        "reason": "fallecimiento_hermanos_abuelos_nietos",
        "date": "2026-06-14",
        "requires_displacement": True,
    })
    assert res["days"] == 2


@pytest.mark.asyncio
async def test_unknown_reason_returns_error():
    server = build_server()
    res = await server.call_tool("checkLeaveEntitlement", {
        "country": "ES",
        "reason": "boda_vecino",
        "date": "2026-06-14",
    })
    assert res["status"] == "unknown_reason"


@pytest.mark.asyncio
async def test_get_vacation_balance_default_30nat():
    server = build_server()
    res = await server.call_tool("getVacationBalance", {
        "country": "ES",
        "year": 2026,
        "daysAlreadyUsed": 8,
    })
    assert res["total_natural"] == 30
    assert res["working_days_equivalent"] == 22
    assert res["used"] == 8
    assert res["remaining_working_days"] == 14


@pytest.mark.asyncio
async def test_get_leave_calendar_es_2026():
    server = build_server()
    res = await server.call_tool("getLeaveCalendar", {"country": "ES", "year": 2026})
    assert len(res["holidays"]) >= 10
    dates = [h["date"] for h in res["holidays"]]
    assert "2026-01-01" in dates
    assert "2026-12-25" in dates
