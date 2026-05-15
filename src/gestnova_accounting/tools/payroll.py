"""Payroll tools: calculatePayroll, simulatePayrollChange, validatePayrollConceptExemption, generatePayslip."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from ._base import BaseTool
from ..engine.rule_lookup import RuleLookup
from ..engine.calc.payroll import compute_payroll_es


def _result_to_jsonable(r):
    """Convert Decimals to strings to keep JSON exact."""
    if isinstance(r, dict):
        return {k: _result_to_jsonable(v) for k, v in r.items()}
    if isinstance(r, list):
        return [_result_to_jsonable(v) for v in r]
    if isinstance(r, Decimal):
        return str(r)
    return r


# Module-level lookup — instantiated lazily by tools using PACKS_ROOT.
_PACKS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "packs"
_lookup: RuleLookup | None = None


def get_lookup() -> RuleLookup:
    global _lookup
    if _lookup is None:
        _lookup = RuleLookup(_PACKS_ROOT)
    return _lookup


class CalculatePayrollTool(BaseTool):
    name = "calculatePayroll"
    description = (
        "Compute payroll for an employee in the given period using the country's "
        "current legal rules (IRPF/ISR brackets, SS/IMSS rates, exempt concepts)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "monthlyBase": {"type": "string", "description": "Monthly cotization base as decimal string"},
            "periodStart": {"type": "string", "format": "date"},
            "periodEnd": {"type": "string", "format": "date"},
            "extras": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "amount": {"type": "string"},
                        "exempt": {"type": "boolean", "default": False},
                    },
                    "required": ["code", "amount"],
                },
                "default": [],
            },
        },
        "required": ["country", "monthlyBase", "periodStart", "periodEnd"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        country = args["country"]
        if country != "ES":
            return {"error": "not_supported_for_country", "country": country, "hint": "MX pack lands in Plan 3."}
        result = compute_payroll_es(
            lookup=get_lookup(),
            monthly_base=Decimal(args["monthlyBase"]),
            extras=args.get("extras", []),
            on_date=date.fromisoformat(args["periodStart"]),
        )
        return _result_to_jsonable(result)


class SimulatePayrollChangeTool(BaseTool):
    name = "simulatePayrollChange"
    description = (
        "Simulate what happens to net pay if specified concepts are added/removed. "
        "Returns current vs simulated payroll with delta and narrative explanation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "monthlyBase": {"type": "string"},
            "periodStart": {"type": "string", "format": "date"},
            "periodEnd": {"type": "string", "format": "date"},
            "currentExtras": {"type": "array", "items": {"type": "object"}, "default": []},
            "addExtras": {"type": "array", "items": {"type": "object"}, "default": []},
            "removeExtraCodes": {"type": "array", "items": {"type": "string"}, "default": []},
        },
        "required": ["country", "monthlyBase", "periodStart", "periodEnd"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        d = date.fromisoformat(args["periodStart"])
        base = Decimal(args["monthlyBase"])
        current_extras = args.get("currentExtras", [])
        simulated_extras = [e for e in current_extras if e["code"] not in args.get("removeExtraCodes", [])]
        simulated_extras += args.get("addExtras", [])

        current = compute_payroll_es(lookup=get_lookup(), monthly_base=base, extras=current_extras, on_date=d)
        simulated = compute_payroll_es(lookup=get_lookup(), monthly_base=base, extras=simulated_extras, on_date=d)

        def diff(a, b):
            return a - b

        delta = {
            "bruto": diff(simulated["bruto"], current["bruto"]),
            "retencion_irpf": diff(simulated["retencion_irpf"]["amount"], current["retencion_irpf"]["amount"]),
            "ss_empleado": diff(simulated["ss_empleado"]["amount"], current["ss_empleado"]["amount"]),
            "liquido": diff(simulated["liquido"], current["liquido"]),
        }

        bits = []
        bruto_d = delta["bruto"]
        liq_d = delta["liquido"]
        if bruto_d != 0:
            sign = "+" if bruto_d > 0 else ""
            bits.append(f"Bruto cambia {sign}{bruto_d}€")
        if liq_d != 0:
            sign = "+" if liq_d > 0 else ""
            bits.append(f"líquido {sign}{liq_d}€")
        if delta["retencion_irpf"] != 0:
            bits.append(f"IRPF se ajusta {delta['retencion_irpf']:+}€")
        explanation = ". ".join(bits) + "." if bits else "Sin cambios."

        return _result_to_jsonable({
            "current": current,
            "simulated": simulated,
            "delta": delta,
            "explanation": explanation,
        })


class ValidatePayrollConceptExemptionTool(BaseTool):
    name = "validatePayrollConceptExemption"
    description = (
        "For a given payroll concept (dieta, kilometraje, plus_transport, etc.), "
        "validate whether the amount is fully exempt, partially exempt, or fully taxable, "
        "citing the applicable legal rule."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "concept": {"type": "string"},
            "amount": {"type": "string"},
            "details": {
                "type": "object",
                "properties": {
                    "kilometers": {"type": "number"},
                    "days": {"type": "number"},
                },
                "default": {},
            },
            "date": {"type": "string", "format": "date"},
        },
        "required": ["country", "concept", "amount", "date"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}

        rule = get_lookup().get("ES", "exempt_concepts", date.fromisoformat(args["date"]))
        concept = args["concept"]
        concept_rule = rule.data.get(concept)
        if not concept_rule:
            return {
                "status": "unknown_concept",
                "concept": concept,
                "hint": f"Concept '{concept}' is not in the exempt-concepts catalog. Treat as fully taxable unless you can cite a legal exception.",
            }

        amount = Decimal(args["amount"])
        details = args.get("details", {})

        exempt_cap: Decimal | None = None
        if concept == "kilometraje" and "rate_per_km" in concept_rule:
            km = Decimal(str(details.get("kilometers", 0)))
            exempt_cap = (km * Decimal(str(concept_rule["rate_per_km"]))).quantize(Decimal("0.01"))
        elif "max_daily" in concept_rule and concept_rule["max_daily"] is not None:
            days = Decimal(str(details.get("days", 1)))
            exempt_cap = (Decimal(str(concept_rule["max_daily"])) * days).quantize(Decimal("0.01"))
        elif "max_monthly" in concept_rule and concept_rule["max_monthly"] is not None:
            exempt_cap = Decimal(str(concept_rule["max_monthly"]))
        elif "max_yearly_per_person" in concept_rule:
            exempt_cap = Decimal(str(concept_rule["max_yearly_per_person"]))

        cent = Decimal("0.01")
        if exempt_cap is None:
            status = "fully_exempt"
            exempt_amount = amount.quantize(cent)
            taxable_amount = Decimal("0.00")
        elif amount <= exempt_cap:
            status = "fully_exempt"
            exempt_amount = amount.quantize(cent)
            taxable_amount = Decimal("0.00")
        else:
            status = "partially_exempt"
            exempt_amount = exempt_cap.quantize(cent)
            taxable_amount = (amount - exempt_cap).quantize(cent)

        return _result_to_jsonable({
            "status": status,
            "concept": concept,
            "exempt_amount": exempt_amount,
            "taxable_amount": taxable_amount,
            "notes": concept_rule.get("notes"),
            "rules_applied": [
                {"rule": "exempt_concepts", "effective_from": str(rule.effective_from), "source": rule.source}
            ],
        })


class GeneratePayslipTool(BaseTool):
    name = "generatePayslip"
    description = (
        "Generate a payslip payload conforming to the country's recibo de salarios "
        "regulations. Plan 1 returns JSON; PDF rendering is wired in Plan 4 via Ian."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "country": {"type": "string", "enum": ["ES", "MX"]},
            "employee": {"type": "object"},
            "company": {"type": "object"},
            "monthlyBase": {"type": "string"},
            "periodStart": {"type": "string", "format": "date"},
            "periodEnd": {"type": "string", "format": "date"},
            "extras": {"type": "array", "items": {"type": "object"}, "default": []},
        },
        "required": ["country", "employee", "company", "monthlyBase", "periodStart", "periodEnd"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if args["country"] != "ES":
            return {"error": "not_supported_for_country", "country": args["country"]}
        comp = compute_payroll_es(
            lookup=get_lookup(),
            monthly_base=Decimal(args["monthlyBase"]),
            extras=args.get("extras", []),
            on_date=date.fromisoformat(args["periodStart"]),
        )
        payslip = {
            "employee": args["employee"],
            "company": args["company"],
            "period": {"start": args["periodStart"], "end": args["periodEnd"]},
            "conceptos": comp["conceptos"],
            "deducciones": {
                "irpf": comp["retencion_irpf"],
                "ss_empleado": comp["ss_empleado"],
            },
            "totals": {
                "bruto": comp["bruto"],
                "liquido": comp["liquido"],
            },
        }
        return _result_to_jsonable({
            "format": "json",
            "payslip": payslip,
            "rules_applied": comp["rules_applied"],
        })
