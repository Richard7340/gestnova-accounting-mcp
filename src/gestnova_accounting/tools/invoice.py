"""Invoice + expense tools for ES (Plan 2)."""
from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup, _result_to_jsonable
from ..engine.calc.iva import forward_iva, reverse_iva


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


class CalculateInvoiceTool(BaseTool):
    name = "calculateInvoice"
    description = (
        "Compute an invoice: items × rate → IVA breakdown by tipo + retención profesional optional + total. "
        "Detects intracommunity / reverse-charge scenarios."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unitPrice": {"type": "string"},
                        "vatCategory": {"type": "string"},  # 'general'|'reducido'|'super_reducido'|'exento' or natural cat
                    },
                    "required": ["description", "quantity", "unitPrice"],
                },
            },
            "retention": {
                "type": "object",
                "properties": {
                    "apply": {"type": "boolean"},
                    "rate": {"type": "string"},
                    "isNewProfessional": {"type": "boolean", "default": False},
                },
                "default": {"apply": False},
            },
            "customerCountry": {"type": "string"},
            "supplierCountry": {"type": "string"},
            "customerHasEuVatNumber": {"type": "boolean", "default": False},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "items", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        on = date.fromisoformat(args["date"])
        rates_rule = get_lookup().get("ES", "vat_rates", on)
        cat_rule = get_lookup().get("ES", "vat_categories", on)
        rates_map = {k: Decimal(str(v)) for k, v in rates_rule.data.items()}

        # Detect invoice type
        supplier_country = args.get("supplierCountry", "ES")
        customer_country = args.get("customerCountry", "ES")
        invoice_type = "national"
        legal_notes: list[str] = []

        EU_COUNTRIES = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"}
        if supplier_country == "ES" and customer_country != "ES":
            if customer_country in EU_COUNTRIES and args.get("customerHasEuVatNumber"):
                invoice_type = "intracommunity"
                legal_notes.append("Operación intracomunitaria — Art. 25 LIVA, exenta de IVA. Declarar en modelo 349.")
            else:
                invoice_type = "export"
                legal_notes.append("Exportación — Art. 21 LIVA, exenta de IVA.")

        # Compute IVA per item
        iva_by_rate: dict[str, dict[str, Decimal]] = {}
        total_base = Decimal("0")
        for item in args["items"]:
            qty = Decimal(str(item["quantity"]))
            unit = Decimal(str(item["unitPrice"]))
            item_base = qty * unit
            total_base += item_base

            if invoice_type in ("intracommunity", "export"):
                # No IVA
                continue

            cat = item.get("vatCategory") or "general"
            # If it's a natural category, map to tipo
            if cat in cat_rule.data:
                tipo = cat_rule.data[cat]
            else:
                tipo = cat  # already a tipo like 'general'

            rate = rates_map.get(tipo, rates_map["general"])
            iva = _round(item_base * rate)
            entry = iva_by_rate.setdefault(str(rate), {"rate": rate, "base": Decimal("0"), "iva": Decimal("0")})
            entry["base"] += item_base
            entry["iva"] += iva

        # Retention (only national typically)
        retention_amount = Decimal("0")
        retention_rate = Decimal("0")
        retention = args.get("retention") or {"apply": False}
        if retention.get("apply") and invoice_type == "national":
            if "rate" in retention and retention["rate"]:
                retention_rate = Decimal(str(retention["rate"]))
            else:
                rt = get_lookup().get("ES", "professional_retention_rates", on)
                rate_key = "new_professional_first_3_years" if retention.get("isNewProfessional") else "standard"
                retention_rate = Decimal(str(rt.data[rate_key]))
            retention_amount = _round(total_base * retention_rate)

        iva_total = sum((v["iva"] for v in iva_by_rate.values()), Decimal("0"))
        total = total_base + iva_total - retention_amount

        breakdown = [
            {"rate": str(v["rate"]), "base": _round(v["base"]), "amount": _round(v["iva"])}
            for v in iva_by_rate.values()
        ]

        return _result_to_jsonable({
            "base": _round(total_base),
            "ivaBreakdown": breakdown,
            "retention": {"rate": retention_rate, "amount": retention_amount},
            "total": _round(total),
            "invoiceType": invoice_type,
            "legalNotes": legal_notes,
            "rules_applied": [
                {"rule": "vat_rates", "effective_from": str(rates_rule.effective_from), "source": rates_rule.source},
            ],
        })


class CalculateIVATool(BaseTool):
    name = "calculateIVA"
    description = "Primitive: forward (base+rate→iva+total) or reverse (total+rate→base+iva)."
    input_schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "string"},
            "rate": {"type": "string"},
            "mode": {"type": "string", "enum": ["forward", "reverse"], "default": "forward"},
        },
        "required": ["amount", "rate"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        amount = Decimal(args["amount"])
        rate = Decimal(args["rate"])
        if args.get("mode", "forward") == "forward":
            res = forward_iva(base=amount, rate=rate)
        else:
            res = reverse_iva(total=amount, rate=rate)
        return _result_to_jsonable({
            "base": res.base,
            "iva": res.iva,
            "total": res.total,
            "rate": res.rate,
        })


class GetApplicableVATRateTool(BaseTool):
    name = "getApplicableVATRate"
    description = "Return the VAT rate applicable to a natural product/service category in a country+date."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "category": {"type": "string"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "category", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        on = date.fromisoformat(args["date"])
        cat_rule = get_lookup().get("ES", "vat_categories", on)
        rates_rule = get_lookup().get("ES", "vat_rates", on)
        tipo = cat_rule.data.get(args["category"])
        if not tipo:
            return {
                "status": "unknown_category",
                "category": args["category"],
                "hint": f"Category '{args['category']}' not catalogued. Default to 'general' (21%) or pass explicit vatCategory in calculateInvoice.",
            }
        rate = rates_rule.data[tipo]
        return _result_to_jsonable({
            "status": "ok",
            "category": args["category"],
            "tipo": tipo,
            "rate": Decimal(str(rate)),
            "rules_applied": [
                {"rule": "vat_categories", "effective_from": str(cat_rule.effective_from), "source": cat_rule.source},
                {"rule": "vat_rates", "effective_from": str(rates_rule.effective_from), "source": rates_rule.source},
            ],
        })


class ValidateInvoiceDataTool(BaseTool):
    name = "validateInvoiceData"
    description = "Verify an invoice payload has all legally-required fields for the country."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "invoice": {"type": "object"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "invoice", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "invoice_required_fields", date.fromisoformat(args["date"]))
        required = rule.data["required"]
        invoice = args["invoice"]
        missing = [f for f in required if not invoice.get(f)]
        return {
            "ok": not missing,
            "missing_fields": missing,
            "rules_applied": [
                {"rule": "invoice_required_fields", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        }


class ClassifyExpenseTool(BaseTool):
    name = "classifyExpense"
    description = "Suggest category + applicable VAT tipo + deductibility for a given expense (description + supplier hint)."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "description": {"type": "string"},
            "supplier": {"type": "string"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "description", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        on = date.fromisoformat(args["date"])
        cat_rule = get_lookup().get("ES", "vat_categories", on)
        rates_rule = get_lookup().get("ES", "vat_rates", on)

        desc = args["description"].lower()
        supplier = (args.get("supplier") or "").lower()
        haystack = f"{desc} {supplier}"

        # Simple keyword-based classification
        keyword_map = {
            "consultoria": ["consultor", "asesoría", "asesoramiento"],
            "hosteleria_restauracion": ["restaurante", "bar", "café", "menu", "comida"],
            "hotel": ["hotel", "alojamiento", "pernocta"],
            "transporte_pasajeros": ["taxi", "uber", "cabify", "metro", "tren", "ave"],
            "gasolina_combustible": ["gasolinera", "diesel", "gasolina", "repsol", "cepsa"],
            "luz": ["endesa", "iberdrola", "naturgy", "luz", "electricidad"],
            "agua": ["agua", "canal isabel"],
            "internet": ["movistar", "vodafone", "orange", "internet", "fibra"],
            "telefonia": ["telefonía", "móvil"],
            "libros_papel": ["libro", "manual"],
            "formacion_privada": ["formación", "curso", "training"],
            "suministros_oficina": ["oficina", "papelería", "material"],
        }

        suggested_category: str | None = None
        for category, keywords in keyword_map.items():
            if any(k in haystack for k in keywords):
                suggested_category = category
                break

        if not suggested_category:
            suggested_category = "consultoria"  # safe default 'general' bucket

        tipo = cat_rule.data.get(suggested_category, "general")
        rate = Decimal(str(rates_rule.data[tipo]))

        return _result_to_jsonable({
            "suggested_category": suggested_category,
            "vat_tipo": tipo,
            "vat_rate": rate,
            "deductible": tipo != "exento",
            "confidence": "high" if suggested_category != "consultoria" else "low",
            "notes": "Si la confianza es baja, confirma con el empleado.",
            "rules_applied": [
                {"rule": "vat_categories", "effective_from": str(cat_rule.effective_from), "source": cat_rule.source}
            ],
        })


class CheckDietaExemptTool(BaseTool):
    name = "checkDietaExempt"
    description = "Check if a dieta amount is within the legal exempt limit (comida, pernocta, kilometraje)."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "type": {"type": "string", "enum": [
                "dieta_comida_nacional", "dieta_pernoctacion_nacional",
                "dieta_comida_extranjero", "dieta_pernoctacion_extranjero",
            ]},
            "amount": {"type": "string"},
            "days": {"type": "number", "default": 1},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "type", "amount", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "exempt_concepts", date.fromisoformat(args["date"]))
        spec = rule.data.get(args["type"])
        if not spec:
            return {"status": "unknown_type", "type": args["type"]}
        days = Decimal(str(args.get("days", 1)))
        amount = Decimal(args["amount"])
        cap = (Decimal(str(spec["max_daily"])) * days).quantize(CENT)
        exempt = amount if amount <= cap else cap
        taxable = max(Decimal("0"), amount - cap)
        return _result_to_jsonable({
            "exempt": _round(exempt),
            "taxable": _round(taxable),
            "cap": cap,
            "rule": args["type"],
            "rules_applied": [
                {"rule": "exempt_concepts", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class ApplyKilometrageRateTool(BaseTool):
    name = "applyKilometrageRate"
    description = "Apply the legal kilometrage rate (€/km) to compute the exempt amount."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "kilometers": {"type": "number"},
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "kilometers", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "exempt_concepts", date.fromisoformat(args["date"]))
        rate = Decimal(str(rule.data["kilometraje"]["rate_per_km"]))
        km = Decimal(str(args["kilometers"]))
        exempt = (rate * km).quantize(CENT)
        return _result_to_jsonable({
            "kilometers": km,
            "rate_per_km": rate,
            "exempt_amount": exempt,
            "rules_applied": [
                {"rule": "exempt_concepts", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })
