from decimal import Decimal
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_calculate_payroll_tool_es():
    server = build_server()
    result = await server.call_tool("calculatePayroll", {
        "country": "ES",
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [],
    })
    assert result["bruto"] == "2500.00"
    assert result["liquido"] == "1741.62"
    assert any(r["rule"] == "irpf_brackets" for r in result["rules_applied"])


@pytest.mark.asyncio
async def test_calculate_payroll_with_exempt_extra():
    server = build_server()
    result = await server.call_tool("calculatePayroll", {
        "country": "ES",
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [{"code": "plus_transport", "amount": "80", "exempt": True}],
    })
    assert result["bruto"] == "2580.00"
    assert result["liquido"] == "1821.62"


@pytest.mark.asyncio
async def test_simulate_payroll_change_adds_concept():
    server = build_server()
    result = await server.call_tool("simulatePayrollChange", {
        "country": "ES",
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "currentExtras": [],
        "addExtras": [{"code": "bonus", "amount": "200", "exempt": False}],
        "removeExtraCodes": [],
    })
    assert result["current"]["liquido"] == "1741.62"
    assert Decimal(result["simulated"]["liquido"]) > Decimal(result["current"]["liquido"])
    assert "delta" in result
    assert "explanation" in result


@pytest.mark.asyncio
async def test_validate_concept_kilometers_exempt_under_limit():
    server = build_server()
    result = await server.call_tool("validatePayrollConceptExemption", {
        "country": "ES",
        "concept": "kilometraje",
        "amount": "50",
        "details": {"kilometers": 100},
        "date": "2026-05-15",
    })
    # 100 km × 0.26 = 26 € exento. Pagamos 50 → 26 exento, 24 sujeto.
    assert result["status"] == "partially_exempt"
    assert result["exempt_amount"] == "26.00"
    assert result["taxable_amount"] == "24.00"


@pytest.mark.asyncio
async def test_validate_concept_dieta_comida_within_limit():
    server = build_server()
    result = await server.call_tool("validatePayrollConceptExemption", {
        "country": "ES",
        "concept": "dieta_comida_nacional",
        "amount": "20",
        "date": "2026-05-15",
    })
    assert result["status"] == "fully_exempt"
    assert result["exempt_amount"] == "20.00"


@pytest.mark.asyncio
async def test_validate_concept_dieta_comida_exceeds_limit():
    server = build_server()
    result = await server.call_tool("validatePayrollConceptExemption", {
        "country": "ES",
        "concept": "dieta_comida_nacional",
        "amount": "40",
        "date": "2026-05-15",
    })
    # Limit 26.67, paid 40 → 26.67 exento, 13.33 taxable
    assert result["status"] == "partially_exempt"
    assert result["exempt_amount"] == "26.67"
    assert result["taxable_amount"] == "13.33"


@pytest.mark.asyncio
async def test_generate_payslip_returns_structured_payload():
    server = build_server()
    result = await server.call_tool("generatePayslip", {
        "country": "ES",
        "employee": {"fullName": "Ricardo Izquierdo", "taxId": "12345678Z"},
        "company": {"name": "Gestnova SL", "taxId": "B12345678"},
        "monthlyBase": "2500",
        "periodStart": "2026-05-01",
        "periodEnd": "2026-05-31",
        "extras": [{"code": "plus_transport", "amount": "80", "exempt": True}],
    })
    assert result["payslip"]["employee"]["fullName"] == "Ricardo Izquierdo"
    assert result["payslip"]["totals"]["liquido"] == "1821.62"
    assert "rules_applied" in result
    assert result["format"] == "json"
