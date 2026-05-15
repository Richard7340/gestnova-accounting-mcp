"""MX payroll tool tests — verify dispatch and country-aware output."""
from decimal import Decimal
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_calculate_payroll_mx_basic():
    server = build_server()
    res = await server.call_tool("calculatePayroll", {
        "country": "MX",
        "monthlyBase": "20000",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [],
    })
    assert "isr" in res
    assert "imss_empleado" in res
    assert "liquido" in res
    # 20000 × 0.02375 = 475 IMSS
    assert res["imss_empleado"]["amount"] == "475.00"
    rules = [r["rule"] for r in res["rules_applied"]]
    assert "isr_brackets" in rules
    assert "imss_employee_rates" in rules


@pytest.mark.asyncio
async def test_calculate_payroll_mx_exempt_extra():
    server = build_server()
    res = await server.call_tool("calculatePayroll", {
        "country": "MX",
        "monthlyBase": "20000",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [{"code": "despensa", "amount": "800", "exempt": True}],
    })
    # Bruto includes exempt 800
    assert res["bruto"] == "20800.00"
    # IMSS still on taxable 20000
    assert res["imss_empleado"]["amount"] == "475.00"


@pytest.mark.asyncio
async def test_simulate_payroll_change_mx():
    server = build_server()
    res = await server.call_tool("simulatePayrollChange", {
        "country": "MX",
        "monthlyBase": "25000",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "currentExtras": [],
        "addExtras": [{"code": "bonus", "amount": "5000", "exempt": False}],
        "removeExtraCodes": [],
    })
    assert "delta" in res
    assert "isr_retenido" in res["delta"]
    # Adding 5000 raises ISR retained
    assert Decimal(res["delta"]["isr_retenido"]) > Decimal("0")


@pytest.mark.asyncio
async def test_generate_payslip_mx_has_isr_imss():
    server = build_server()
    res = await server.call_tool("generatePayslip", {
        "country": "MX",
        "employee": {"fullName": "Juan Pérez", "taxId": "PERJ800101XYZ"},
        "company": {"name": "Gestnova México SA", "taxId": "GME260101ABC"},
        "monthlyBase": "20000",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [],
    })
    assert res["payslip"]["country"] == "MX"
    assert "isr" in res["payslip"]["deducciones"]
    assert "imss_empleado" in res["payslip"]["deducciones"]
    assert "irpf" not in res["payslip"]["deducciones"]
    assert "ss_empleado" not in res["payslip"]["deducciones"]


@pytest.mark.asyncio
async def test_list_supported_countries_includes_mx():
    server = build_server()
    res = await server.call_tool("listSupportedCountries", {})
    assert "MX" in res["countries"]
    assert "ES" in res["countries"]


@pytest.mark.asyncio
async def test_get_country_fiscal_profile_mx():
    server = build_server()
    res = await server.call_tool("getCountryFiscalProfile", {"country": "MX"})
    assert res["country"] == "MX"
    assert "vat_rates" in res["summary"]
    # MX general is 16%
    assert Decimal(str(res["summary"]["vat_rates"]["general"])) == Decimal("0.16")


@pytest.mark.asyncio
async def test_lookup_legal_reference_mx_isr():
    server = build_server()
    res = await server.call_tool("lookupLegalReference", {
        "country": "MX", "query": "ISR brackets",
    })
    assert len(res["matches"]) >= 1
    assert any("isr" in m["rule"].lower() for m in res["matches"])
