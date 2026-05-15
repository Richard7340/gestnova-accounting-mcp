from decimal import Decimal
import pytest
from gestnova_accounting.server import build_server


@pytest.mark.asyncio
async def test_calculate_invoice_national_general():
    server = build_server()
    res = await server.call_tool("calculateInvoice", {
        "country": "ES",
        "items": [
            {"description": "Consultoría abril", "quantity": 1, "unitPrice": "2400", "vatCategory": "general"},
        ],
        "customerCountry": "ES",
        "supplierCountry": "ES",
        "date": "2026-05-15",
    })
    assert res["base"] == "2400.00"
    assert res["invoiceType"] == "national"
    assert res["total"] == "2904.00"
    iva = res["ivaBreakdown"][0]
    assert iva["amount"] == "504.00"


@pytest.mark.asyncio
async def test_calculate_invoice_with_professional_retention():
    server = build_server()
    res = await server.call_tool("calculateInvoice", {
        "country": "ES",
        "items": [
            {"description": "Honorarios", "quantity": 1, "unitPrice": "1000", "vatCategory": "general"},
        ],
        "retention": {"apply": True, "isNewProfessional": False},
        "customerCountry": "ES",
        "supplierCountry": "ES",
        "date": "2026-05-15",
    })
    # Base 1000, IVA 210, retención 15% * 1000 = 150
    # Total = 1000 + 210 - 150 = 1060
    assert res["base"] == "1000.00"
    assert res["retention"]["rate"] == "0.15"
    assert res["retention"]["amount"] == "150.00"
    assert res["total"] == "1060.00"


@pytest.mark.asyncio
async def test_calculate_invoice_intracommunity_no_iva():
    server = build_server()
    res = await server.call_tool("calculateInvoice", {
        "country": "ES",
        "items": [
            {"description": "Servicios consulting Acme DE", "quantity": 1, "unitPrice": "2000"},
        ],
        "customerCountry": "DE",
        "supplierCountry": "ES",
        "customerHasEuVatNumber": True,
        "date": "2026-05-15",
    })
    assert res["invoiceType"] == "intracommunity"
    assert res["ivaBreakdown"] == []
    assert res["total"] == "2000.00"
    assert any("Art. 25 LIVA" in n for n in res["legalNotes"])


@pytest.mark.asyncio
async def test_calculate_iva_forward():
    server = build_server()
    res = await server.call_tool("calculateIVA", {
        "amount": "100", "rate": "0.21", "mode": "forward",
    })
    assert res["iva"] == "21.00"
    assert res["total"] == "121.00"


@pytest.mark.asyncio
async def test_get_applicable_vat_rate_consultoria_is_21():
    server = build_server()
    res = await server.call_tool("getApplicableVATRate", {
        "country": "ES", "category": "consultoria", "date": "2026-05-15",
    })
    assert res["status"] == "ok"
    assert res["tipo"] == "general"
    assert Decimal(res["rate"]) == Decimal("0.21")


@pytest.mark.asyncio
async def test_get_applicable_vat_rate_libros_super_reducido():
    server = build_server()
    res = await server.call_tool("getApplicableVATRate", {
        "country": "ES", "category": "libros_papel", "date": "2026-05-15",
    })
    assert res["tipo"] == "super_reducido"
    assert Decimal(res["rate"]) == Decimal("0.04")


@pytest.mark.asyncio
async def test_validate_invoice_data_complete():
    server = build_server()
    res = await server.call_tool("validateInvoiceData", {
        "country": "ES",
        "invoice": {
            "numero_correlativo": "F-2026-042",
            "serie": "F",
            "fecha_emision": "2026-05-15",
            "emisor_nif": "B12345678",
            "emisor_nombre": "Gestnova SL",
            "emisor_domicilio": "Madrid",
            "receptor_nif": "B98765432",
            "receptor_nombre": "Acme SL",
            "receptor_domicilio": "Barcelona",
            "descripcion_operacion": "Consultoría",
            "base_imponible": 1000,
            "tipo_iva": 0.21,
            "cuota_iva": 210,
            "total": 1210,
        },
        "date": "2026-05-15",
    })
    assert res["ok"] is True
    assert res["missing_fields"] == []


@pytest.mark.asyncio
async def test_validate_invoice_data_missing():
    server = build_server()
    res = await server.call_tool("validateInvoiceData", {
        "country": "ES",
        "invoice": {"numero_correlativo": "F-001"},
        "date": "2026-05-15",
    })
    assert res["ok"] is False
    assert "receptor_nif" in res["missing_fields"]


@pytest.mark.asyncio
async def test_classify_expense_restaurant_is_reducido():
    server = build_server()
    res = await server.call_tool("classifyExpense", {
        "country": "ES",
        "description": "Comida con cliente",
        "supplier": "Restaurante La Buena Mesa",
        "date": "2026-05-15",
    })
    assert res["suggested_category"] == "hosteleria_restauracion"
    assert res["vat_tipo"] == "reducido"
    assert Decimal(res["vat_rate"]) == Decimal("0.10")


@pytest.mark.asyncio
async def test_check_dieta_within_limit():
    server = build_server()
    res = await server.call_tool("checkDietaExempt", {
        "country": "ES",
        "type": "dieta_comida_nacional",
        "amount": "20",
        "days": 1,
        "date": "2026-05-15",
    })
    assert res["exempt"] == "20.00"
    assert res["taxable"] == "0.00"


@pytest.mark.asyncio
async def test_apply_kilometrage():
    server = build_server()
    res = await server.call_tool("applyKilometrageRate", {
        "country": "ES", "kilometers": 100, "date": "2026-05-15",
    })
    # 100 km × 0.26 = 26
    assert res["exempt_amount"] == "26.00"
    assert res["rate_per_km"] == "0.26"
