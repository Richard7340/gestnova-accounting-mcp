import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_lookup_legal_reference_finds_irpf():
    server = build_server()
    res = await server.call_tool("lookupLegalReference", {"country": "ES", "query": "IRPF brackets"})
    assert len(res["matches"]) >= 1
    assert any("irpf" in m["rule"].lower() for m in res["matches"])


@pytest.mark.asyncio
async def test_lookup_no_match():
    server = build_server()
    res = await server.call_tool("lookupLegalReference", {"country": "ES", "query": "criptomonedas"})
    assert res["matches"] == []
    assert "hint" in res


@pytest.mark.asyncio
async def test_get_applicable_rules_for_payroll():
    server = build_server()
    res = await server.call_tool("getApplicableRules", {
        "country": "ES",
        "area": "payroll",
        "date": "2026-05-15",
    })
    rule_names = [r["rule"] for r in res["rules"]]
    assert "irpf_brackets" in rule_names
    assert "ss_employee_rates" in rule_names


@pytest.mark.asyncio
async def test_list_supported_countries_includes_es():
    server = build_server()
    res = await server.call_tool("listSupportedCountries", {})
    assert "ES" in res["countries"]


@pytest.mark.asyncio
async def test_get_country_fiscal_profile_es():
    server = build_server()
    res = await server.call_tool("getCountryFiscalProfile", {"country": "ES"})
    assert res["country"] == "ES"
    assert "vat_rates" in res["summary"]
    assert "max_overtime_yearly" in res["summary"]
