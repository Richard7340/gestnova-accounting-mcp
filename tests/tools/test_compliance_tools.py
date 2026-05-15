from datetime import date
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_applicable_docs_es_small_consultoria():
    """ES consultoría con 5 empleados: lopd-rgpd + prl-basico + registro-horario obligatorios."""
    server = build_server()
    res = await server.call_tool("getApplicableComplianceDocs", {
        "country": "ES", "sector": "consultoria", "workers": 5,
    })
    docs = res["applicable_documents"]
    assert "lopd-rgpd" in docs
    assert "prl-basico" in docs
    assert "registro-horario" in docs
    # Plan de igualdad NO aplica (<50)
    assert "plan-igualdad" not in docs


@pytest.mark.asyncio
async def test_applicable_docs_es_plan_igualdad_50plus():
    """ES con 60 empleados: añade plan-igualdad + delegado-prevencion."""
    server = build_server()
    res = await server.call_tool("getApplicableComplianceDocs", {
        "country": "ES", "sector": "comercio", "workers": 60,
    })
    docs = res["applicable_documents"]
    assert "plan-igualdad" in docs
    assert "delegado-prevencion" in docs
    assert "comite-empresa" in docs


@pytest.mark.asyncio
async def test_applicable_docs_es_sector_regulado_adds_prevencion_penal():
    """Sector financiero añade prevencion-penal aunque tenga pocos empleados."""
    server = build_server()
    res = await server.call_tool("getApplicableComplianceDocs", {
        "country": "ES", "sector": "financiero", "workers": 5,
    })
    docs = res["applicable_documents"]
    assert "prevencion-penal" in docs


@pytest.mark.asyncio
async def test_applicable_docs_mx_minimo():
    """MX 1 empleado: lfpdppp + nom-035 + reglamento-interior."""
    server = build_server()
    res = await server.call_tool("getApplicableComplianceDocs", {
        "country": "MX", "sector": "consultoria", "workers": 1,
    })
    docs = res["applicable_documents"]
    assert "lfpdppp" in docs
    assert "nom-035-stps" in docs
    assert "reglamento-interior-trabajo" in docs


@pytest.mark.asyncio
async def test_get_template_lopd_rgpd():
    server = build_server()
    res = await server.call_tool("getComplianceTemplate", {
        "country": "ES", "documentType": "lopd-rgpd", "date": "2026-05-15",
    })
    template = res["template"]
    assert template["document_type"] == "lopd-rgpd"
    assert template["review_period_months"] == 12
    assert "company_name" in template["required_fields"]
    section_ids = [s["id"] for s in template["sections"]]
    assert "registro_actividades_tratamiento" in section_ids


@pytest.mark.asyncio
async def test_get_template_unknown():
    server = build_server()
    res = await server.call_tool("getComplianceTemplate", {
        "country": "ES", "documentType": "non_existing", "date": "2026-05-15",
    })
    assert res["error"] == "template_not_found"


@pytest.mark.asyncio
async def test_get_template_nom_035_mx():
    server = build_server()
    res = await server.call_tool("getComplianceTemplate", {
        "country": "MX", "documentType": "nom-035-stps", "date": "2026-05-15",
    })
    template = res["template"]
    assert template["review_period_months"] == 24
    assert "STPS" in template["legal_consequences"] or "UMAs" in template["legal_consequences"]


@pytest.mark.asyncio
async def test_check_status_valid():
    """Doc emitido hace 2 meses, review_period 12m → valid (más de 90 días para vencer)."""
    server = build_server()
    res = await server.call_tool("checkComplianceStatus", {
        "country": "ES", "documentType": "lopd-rgpd",
        "validFrom": "2026-03-15", "today": "2026-05-15",
    })
    assert res["status"] == "valid"
    assert res["days_to_expiry"] > 90


@pytest.mark.asyncio
async def test_check_status_expiring_soon():
    """Doc venció hace casi 12m → expiring_soon."""
    server = build_server()
    res = await server.call_tool("checkComplianceStatus", {
        "country": "ES", "documentType": "lopd-rgpd",
        "validFrom": "2025-06-01", "today": "2026-05-15",
    })
    # validFrom + 12 months = 2026-06-01, today 2026-05-15 → 17 days remaining
    assert res["status"] == "expiring_soon"


@pytest.mark.asyncio
async def test_check_status_expired():
    server = build_server()
    res = await server.call_tool("checkComplianceStatus", {
        "country": "ES", "documentType": "lopd-rgpd",
        "validFrom": "2024-01-01", "today": "2026-05-15",
    })
    assert res["status"] == "expired"
    assert res["days_to_expiry"] < 0


@pytest.mark.asyncio
async def test_detect_updates_when_template_unchanged():
    """Instance same date as template → no updates."""
    server = build_server()
    res = await server.call_tool("detectComplianceUpdates", {
        "country": "ES",
        "instances": [
            {"documentType": "lopd-rgpd", "templateVersion": "2026-01-01"},
            {"documentType": "prl-basico", "templateVersion": "2026-01-01"},
        ],
        "today": "2026-05-15",
    })
    assert res["no_updates_needed"] is True
    assert res["updates_detected"] == []


@pytest.mark.asyncio
async def test_detect_updates_when_instance_old():
    """Instance pre-2026 template → updates detected."""
    server = build_server()
    res = await server.call_tool("detectComplianceUpdates", {
        "country": "ES",
        "instances": [
            {"documentType": "lopd-rgpd", "templateVersion": "2024-01-01"},
        ],
        "today": "2026-05-15",
    })
    assert res["no_updates_needed"] is False
    assert len(res["updates_detected"]) == 1
    upd = res["updates_detected"][0]
    assert upd["document_type"] == "lopd-rgpd"
    assert upd["action"] == "review_needed"
