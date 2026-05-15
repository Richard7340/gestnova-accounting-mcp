from decimal import Decimal
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_prepare_model_303_q2():
    server = build_server()
    res = await server.call_tool("prepareModel303", {
        "country": "ES",
        "quarter": 2,
        "year": 2026,
        "salesByRate": {
            "0.21": {"base": "10000", "iva": "2100"},
            "0.10": {"base": "2000", "iva": "200"},
        },
        "expensesByType": {
            "corrientes": {"base": "3000", "iva": "630"},
            "inversion": {"base": "1000", "iva": "210"},
        },
    })
    assert res["model"] == "303"
    assert res["quarter"] == 2
    assert res["casillas"]["07"] == "10000.00"
    assert res["casillas"]["09"] == "2100.00"
    assert res["casillas"]["04"] == "2000.00"
    assert res["casillas"]["06"] == "200.00"
    assert res["casillas"]["27"] == "2300.00"   # devengado
    assert res["casillas"]["45"] == "840.00"    # deducible
    assert res["casillas"]["46"] == "1460.00"   # resultado
    assert res["totals"]["to_pay_or_refund"] == "a_ingresar"


@pytest.mark.asyncio
async def test_prepare_model_111_workers_and_pros():
    server = build_server()
    res = await server.call_tool("prepareModel111", {
        "country": "ES",
        "quarter": 2,
        "year": 2026,
        "workers": {"count": 5, "gross": "12500", "retained": "2000"},
        "professionals": {"count": 2, "gross": "3000", "retained": "450"},
    })
    assert res["casillas"]["01"] == 5
    assert res["casillas"]["03"] == "2000.00"
    assert res["casillas"]["06"] == "450.00"
    assert res["casillas"]["28"] == "2450.00"
    assert res["totals"]["to_pay"] == "2450.00"


@pytest.mark.asyncio
async def test_prepare_model_190_annual():
    server = build_server()
    res = await server.call_tool("prepareModel190", {
        "country": "ES",
        "year": 2026,
        "perceptores": [
            {"nif": "X", "name": "Empleado 1", "clave": "A", "gross": "30000", "retained": "5000"},
            {"nif": "Y", "name": "Empleado 2", "clave": "A", "gross": "25000", "retained": "4000"},
        ],
    })
    assert res["casillas"]["01"] == 2
    assert res["casillas"]["02"] == "55000.00"
    assert res["casillas"]["03"] == "9000.00"


@pytest.mark.asyncio
async def test_prepare_model_130_autonomo():
    server = build_server()
    res = await server.call_tool("prepareModel130", {
        "country": "ES",
        "quarter": 2,
        "year": 2026,
        "ingresos": "15000",
        "gastos": "5000",
        "previousQuarterPayments": "0",
        "retentionsReceived": "1500",
    })
    # Rendimiento neto 10000, 20% = 2000, menos 1500 retenciones = 500
    assert res["casillas"]["03"] == "10000.00"
    assert res["casillas"]["04"] == "2000.00"
    assert res["casillas"]["07"] == "500.00"


@pytest.mark.asyncio
async def test_prepare_model_200_is_general():
    server = build_server()
    res = await server.call_tool("prepareModel200", {
        "country": "ES",
        "year": 2026,
        "resultadoContable": "100000",
        "ajustesPositivos": "5000",
        "ajustesNegativos": "2000",
        "companyType": "general",
    })
    # Base imp = 100000 + 5000 - 2000 = 103000
    # Cuota = 103000 * 0.25 = 25750
    assert res["casillas"]["00552"] == "103000.00"
    assert res["casillas"]["00582"] == "25750.00"
    assert Decimal(res["taxRate"]) == Decimal("0.25")


@pytest.mark.asyncio
async def test_prepare_model_200_pyme_nueva_15pct():
    server = build_server()
    res = await server.call_tool("prepareModel200", {
        "country": "ES",
        "year": 2026,
        "resultadoContable": "50000",
        "companyType": "pyme_nueva_creacion",
    })
    # 50000 * 0.15 = 7500
    assert Decimal(res["taxRate"]) == Decimal("0.15")
    assert res["casillas"]["00582"] == "7500.00"


@pytest.mark.asyncio
async def test_get_fiscal_calendar_es_2026():
    server = build_server()
    res = await server.call_tool("getFiscalCalendar", {"country": "ES", "year": 2026})
    assert res["country"] == "ES"
    models_with_deadlines = {d["model"] for d in res["deadlines"]}
    assert "303" in models_with_deadlines
    assert "111" in models_with_deadlines
    assert "130" in models_with_deadlines
    assert "190" in models_with_deadlines
