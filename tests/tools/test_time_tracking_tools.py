import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_clock_in_within_hours_regular():
    server = build_server()
    res = await server.call_tool("clockInLegal", {
        "country": "ES",
        "timestamp": "2026-05-15T10:30:00+02:00",
        "intent": "in",
        "workingHours": {"start": "09:00", "end": "19:00"},
        "previousEntriesToday": [],
    })
    assert res["registered"] is True
    assert res["classification"] == "regular"
    assert res["prompt"]["type"] == "none"


@pytest.mark.asyncio
async def test_clock_out_outside_hours_prompts_for_confirmation():
    """User clocks out at midnight outside working hours → must prompt + alert."""
    server = build_server()
    res = await server.call_tool("clockInLegal", {
        "country": "ES",
        "timestamp": "2026-05-15T00:00:00+02:00",
        "intent": "out",
        "workingHours": {"start": "09:00", "end": "19:00"},
        "previousEntriesToday": [
            {"timestamp": "2026-05-14T09:30:00+02:00", "intent": "in"},
        ],
    })
    assert res["registered"] is True
    assert res["classification"] == "outside-hours"
    assert res["prompt"]["type"] == "confirm_real_work"
    assert any(a["code"] == "exceeds_max_daily_hours" for a in res["alerts"])


@pytest.mark.asyncio
async def test_clock_does_not_maquillar():
    """Even when prompted, the recorded timestamp is the real one (no rounding down)."""
    server = build_server()
    res = await server.call_tool("clockInLegal", {
        "country": "ES",
        "timestamp": "2026-05-15T23:00:00+02:00",
        "intent": "out",
        "workingHours": {"start": "09:00", "end": "19:00"},
        "previousEntriesToday": [
            {"timestamp": "2026-05-15T09:00:00+02:00", "intent": "in"},
        ],
    })
    assert res["recorded_timestamp"] == "2026-05-15T23:00:00+02:00"
    assert res["registered"] is True


@pytest.mark.asyncio
async def test_get_jornada_status_aggregates_week():
    server = build_server()
    res = await server.call_tool("getJornadaStatus", {
        "country": "ES",
        "entries": [
            {"timestamp": "2026-05-11T09:00:00+02:00", "intent": "in"},
            {"timestamp": "2026-05-11T18:00:00+02:00", "intent": "out"},
            {"timestamp": "2026-05-12T09:00:00+02:00", "intent": "in"},
            {"timestamp": "2026-05-12T20:00:00+02:00", "intent": "out"},
        ],
        "periodStart": "2026-05-11",
        "periodEnd": "2026-05-17",
        "workingHours": {"start": "09:00", "end": "19:00"},
    })
    assert res["total_hours"] == 20.0
    assert res["overtime_hours"] == 2.0
    assert len(res["alerts"]) >= 1


@pytest.mark.asyncio
async def test_get_overtime_balance_es():
    server = build_server()
    res = await server.call_tool("getOvertimeBalance", {
        "country": "ES",
        "year": 2026,
        "overtimeUsed": 23.5,
    })
    assert res["limit"] == 80
    assert res["used"] == 23.5
    assert res["remaining"] == 56.5
    assert "rules_applied" in res
