"""Fiscal model tools for ES: 303, 111, 190, 130, 200 + fiscal calendar."""
from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from ._base import BaseTool
from .payroll import get_lookup, _result_to_jsonable


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


class PrepareModel303Tool(BaseTool):
    name = "prepareModel303"
    description = "Prepare quarterly IVA dataset for AEAT modelo 303. Returns casillas + totals + artifact metadata."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "quarter": {"type": "integer", "minimum": 1, "maximum": 4},
            "year": {"type": "integer"},
            "salesByRate": {
                "type": "object",
                "description": "Map rate → {base, iva}. E.g. {'0.21': {base: 10000, iva: 2100}, '0.10': {...}}",
            },
            "expensesByType": {
                "type": "object",
                "description": "Map type → {base, iva}. E.g. {'corrientes': {base:5000, iva:1050}, 'inversion':{base:2000, iva:420}}",
                "default": {},
            },
        },
        "required": ["country", "quarter", "year", "salesByRate"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "model_303", date(args["year"], 6, 1))

        casillas: dict[str, Decimal] = {}
        # Map rate → casillas (base, cuota)
        rate_to_casillas = {
            "0.04": ("01", "03"),
            "0.10": ("04", "06"),
            "0.21": ("07", "09"),
        }
        for rate_str, vals in args["salesByRate"].items():
            base_cas, cuota_cas = rate_to_casillas.get(rate_str, (None, None))
            if base_cas:
                casillas[base_cas] = _round(Decimal(str(vals.get("base", 0))))
                casillas[cuota_cas] = _round(Decimal(str(vals.get("iva", 0))))

        total_devengado = sum(
            (casillas.get(c, Decimal("0")) for c in ["03", "06", "09"]),
            Decimal("0"),
        )
        casillas["27"] = _round(total_devengado)

        expenses = args.get("expensesByType", {})
        if "corrientes" in expenses:
            casillas["28"] = _round(Decimal(str(expenses["corrientes"].get("base", 0))))
            casillas["29"] = _round(Decimal(str(expenses["corrientes"].get("iva", 0))))
        if "inversion" in expenses:
            casillas["30"] = _round(Decimal(str(expenses["inversion"].get("base", 0))))
            casillas["31"] = _round(Decimal(str(expenses["inversion"].get("iva", 0))))
        if "intracom" in expenses:
            casillas["32"] = _round(Decimal(str(expenses["intracom"].get("base", 0))))
            casillas["33"] = _round(Decimal(str(expenses["intracom"].get("iva", 0))))

        total_deducible = sum(
            (casillas.get(c, Decimal("0")) for c in ["29", "31", "33"]),
            Decimal("0"),
        )
        casillas["45"] = _round(total_deducible)
        casillas["46"] = _round(total_devengado - total_deducible)
        casillas["71"] = casillas["46"]   # sin ajustes complejos en Plan 2

        deadline = rule.data["deadlines"].get(f"Q{args['quarter']}")

        return _result_to_jsonable({
            "country": "ES",
            "model": "303",
            "quarter": args["quarter"],
            "year": args["year"],
            "deadline": deadline,
            "casillas": casillas,
            "totals": {
                "devengado": total_devengado,
                "deducible": total_deducible,
                "resultado": casillas["46"],
                "to_pay_or_refund": ("a_ingresar" if casillas["46"] > 0 else "a_devolver_o_compensar"),
            },
            "warnings": [],
            "rules_applied": [
                {"rule": "model_303", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class PrepareModel111Tool(BaseTool):
    name = "prepareModel111"
    description = "Prepare quarterly retention IRPF dataset for AEAT modelo 111."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "quarter": {"type": "integer"},
            "year": {"type": "integer"},
            "workers": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "gross": {"type": "string"},
                    "retained": {"type": "string"},
                },
            },
            "professionals": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "gross": {"type": "string"},
                    "retained": {"type": "string"},
                },
            },
        },
        "required": ["country", "quarter", "year"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "model_111", date(args["year"], 6, 1))

        casillas: dict[str, Any] = {}
        workers = args.get("workers", {})
        if workers:
            casillas["01"] = int(workers.get("count", 0))
            casillas["02"] = _round(Decimal(str(workers.get("gross", 0))))
            casillas["03"] = _round(Decimal(str(workers.get("retained", 0))))
        prof = args.get("professionals", {})
        if prof:
            casillas["04"] = int(prof.get("count", 0))
            casillas["05"] = _round(Decimal(str(prof.get("gross", 0))))
            casillas["06"] = _round(Decimal(str(prof.get("retained", 0))))

        total = sum(
            (Decimal(str(casillas.get(c, 0))) for c in ["03", "06", "09"]),
            Decimal("0"),
        )
        casillas["28"] = _round(total)
        casillas["29"] = _round(total)

        return _result_to_jsonable({
            "country": "ES",
            "model": "111",
            "quarter": args["quarter"],
            "year": args["year"],
            "deadline": rule.data["deadlines"].get(f"Q{args['quarter']}"),
            "casillas": casillas,
            "totals": {"to_pay": _round(total)},
            "rules_applied": [
                {"rule": "model_111", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class PrepareModel190Tool(BaseTool):
    name = "prepareModel190"
    description = "Prepare annual retention summary dataset for AEAT modelo 190."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "year": {"type": "integer"},
            "perceptores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nif": {"type": "string"},
                        "name": {"type": "string"},
                        "clave": {"type": "string"},   # A, B, G, …
                        "gross": {"type": "string"},
                        "retained": {"type": "string"},
                    },
                },
            },
        },
        "required": ["country", "year", "perceptores"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "model_190", date(args["year"], 6, 1))
        perceptores = args["perceptores"]
        total_gross = sum((Decimal(str(p.get("gross", 0))) for p in perceptores), Decimal("0"))
        total_retained = sum((Decimal(str(p.get("retained", 0))) for p in perceptores), Decimal("0"))
        casillas = {
            "01": len(perceptores),
            "02": _round(total_gross),
            "03": _round(total_retained),
        }
        return _result_to_jsonable({
            "country": "ES",
            "model": "190",
            "year": args["year"],
            "deadline": rule.data["deadline"],
            "casillas": casillas,
            "perceptores_detail": perceptores,
            "totals": {"gross": _round(total_gross), "retained": _round(total_retained)},
            "rules_applied": [
                {"rule": "model_190", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class PrepareModel130Tool(BaseTool):
    name = "prepareModel130"
    description = "Prepare quarterly autónomo pago fraccionado dataset for AEAT modelo 130."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "quarter": {"type": "integer"},
            "year": {"type": "integer"},
            "ingresos": {"type": "string"},
            "gastos": {"type": "string"},
            "previousQuarterPayments": {"type": "string", "default": "0"},
            "retentionsReceived": {"type": "string", "default": "0"},
        },
        "required": ["country", "quarter", "year", "ingresos", "gastos"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "model_130", date(args["year"], 6, 1))
        rate = Decimal(str(rule.data["rate"]))   # 0.20

        ingresos = Decimal(args["ingresos"])
        gastos = Decimal(args["gastos"])
        rendimiento_neto = ingresos - gastos
        cuota = max(Decimal("0"), rendimiento_neto * rate)
        prev = Decimal(args.get("previousQuarterPayments", "0"))
        retenciones = Decimal(args.get("retentionsReceived", "0"))
        resultado = cuota - prev - retenciones

        casillas = {
            "01": _round(ingresos),
            "02": _round(gastos),
            "03": _round(rendimiento_neto),
            "04": _round(cuota),
            "05": _round(prev),
            "06": _round(retenciones),
            "07": _round(resultado),
        }
        return _result_to_jsonable({
            "country": "ES",
            "model": "130",
            "quarter": args["quarter"],
            "year": args["year"],
            "deadline": rule.data["deadlines"].get(f"Q{args['quarter']}"),
            "casillas": casillas,
            "totals": {"to_pay": _round(resultado)},
            "rules_applied": [
                {"rule": "model_130", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class PrepareModel200Tool(BaseTool):
    name = "prepareModel200"
    description = "Prepare annual Impuesto Sociedades dataset for AEAT modelo 200."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "year": {"type": "integer"},
            "resultadoContable": {"type": "string"},
            "ajustesPositivos": {"type": "string", "default": "0"},
            "ajustesNegativos": {"type": "string", "default": "0"},
            "companyType": {
                "type": "string",
                "enum": ["general", "pyme_nueva_creacion", "micro_pyme", "cooperativas_protegidas", "entidades_sin_animo_lucro"],
                "default": "general",
            },
            "pagosFraccionados": {"type": "string", "default": "0"},
            "retenciones": {"type": "string", "default": "0"},
        },
        "required": ["country", "year", "resultadoContable"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        rule = get_lookup().get("ES", "model_200", date(args["year"], 6, 1))

        resultado = Decimal(args["resultadoContable"])
        ajustes_pos = Decimal(args.get("ajustesPositivos", "0"))
        ajustes_neg = Decimal(args.get("ajustesNegativos", "0"))
        base_imp = resultado + ajustes_pos - ajustes_neg

        company_type = args.get("companyType", "general")
        tax_rate = Decimal(str(rule.data["rates"].get(company_type, rule.data["rates"]["general"])))
        cuota_integra = max(Decimal("0"), base_imp * tax_rate)
        pagos = Decimal(args.get("pagosFraccionados", "0"))
        retenciones = Decimal(args.get("retenciones", "0"))
        liquido = cuota_integra - pagos - retenciones

        casillas = {
            "00501": _round(resultado),
            "00518": _round(ajustes_pos),
            "00519": _round(ajustes_neg),
            "00550": _round(base_imp),
            "00552": _round(base_imp),
            "00558": _round(cuota_integra),
            "00582": _round(cuota_integra),
            "00599": _round(pagos),
            "00621": _round(liquido),
        }
        return _result_to_jsonable({
            "country": "ES",
            "model": "200",
            "year": args["year"],
            "deadline": rule.data["deadline_default"],
            "companyType": company_type,
            "taxRate": tax_rate,
            "casillas": casillas,
            "totals": {
                "base_imponible": _round(base_imp),
                "cuota_integra": _round(cuota_integra),
                "to_pay_or_refund": _round(liquido),
            },
            "rules_applied": [
                {"rule": "model_200", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class GetFiscalCalendarTool(BaseTool):
    name = "getFiscalCalendar"
    description = "Return key fiscal deadlines for a country and year."
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES"]},
            "year": {"type": "integer"},
        },
        "required": ["country", "year"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        year = args["year"]
        on = date(year, 6, 1)
        deadlines = []
        for model_key in ["model_303", "model_111", "model_130", "model_190", "model_200"]:
            try:
                r = get_lookup().get("ES", model_key, on)
                if "deadlines" in r.data:
                    for q, d in r.data["deadlines"].items():
                        deadlines.append({"model": model_key.replace("model_", ""), "period": q, "date": str(d)})
                if "deadline" in r.data:
                    deadlines.append({"model": model_key.replace("model_", ""), "period": "anual", "date": str(r.data["deadline"])})
                if "deadline_default" in r.data:
                    deadlines.append({"model": model_key.replace("model_", ""), "period": "anual", "date": r.data["deadline_default"]})
            except Exception:
                continue
        deadlines.sort(key=lambda x: x["date"] if x["date"][0].isdigit() else "9999")
        return {
            "country": "ES",
            "year": year,
            "deadlines": deadlines,
        }
