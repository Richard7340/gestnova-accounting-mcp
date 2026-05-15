"""MX payroll calculator — ISR tarifa (cuota fija + % excedente) + IMSS + subsidio empleo + neto.

Note: this is a SIMPLIFIED IMSS calculation (single aggregated rate). Real-world
MX payroll uses SBC + UMA bands per IMSS branch with caps and integration
factors that vary by employee. Plan 5 will refine via gestoría profesional.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Any
from ..rule_lookup import RuleLookup


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_isr_mx(*, monthly_base: Decimal, brackets: list[dict]) -> Decimal:
    """Apply MX ISR tarifa (cuota fija + percentage on excess).

    Each bracket: {limite_inferior, limite_superior, cuota_fija, pct_excedente}.
    Tax = cuota_fija + (base - limite_inferior) × pct_excedente, for the matching bracket.
    """
    for entry in brackets:
        lo = Decimal(str(entry["limite_inferior"]))
        hi = entry.get("limite_superior")
        hi_d = Decimal(str(hi)) if hi is not None else None
        if monthly_base >= lo and (hi_d is None or monthly_base <= hi_d):
            cuota_fija = Decimal(str(entry["cuota_fija"]))
            pct = Decimal(str(entry["pct_excedente"]))
            tax = cuota_fija + (monthly_base - lo) * pct
            return _round(tax)
    return Decimal("0.00")


def compute_subsidio_empleo_mx(*, monthly_base: Decimal, schedule: list[dict]) -> Decimal:
    """Look up subsidio para el empleo for monthly income. Returns 0 above threshold."""
    for entry in schedule:
        lo = Decimal(str(entry["limite_inferior"]))
        hi = Decimal(str(entry["limite_superior"]))
        if lo <= monthly_base <= hi:
            return _round(Decimal(str(entry["subsidio"])))
    return Decimal("0.00")


def compute_imss_employee_mx(*, monthly_base: Decimal, rates: dict) -> Decimal:
    """IMSS employee contribution — simplified to total aggregated rate × base."""
    total_rate = Decimal(str(rates["total"]))
    return _round(monthly_base * total_rate)


def compute_payroll_mx(
    *,
    lookup: RuleLookup,
    monthly_base: Decimal,
    extras: list[dict[str, Any]] | None = None,
    on_date: date,
) -> dict[str, Any]:
    """Full MX payroll computation for one month.

    Sequence: bruto → ISR (tarifa) → subsidio empleo → IMSS → neto.
    Exempt extras add to bruto but not to taxable base.
    """
    extras = extras or []
    isr_rule = lookup.get("MX", "isr_brackets", on_date)
    subs_rule = lookup.get("MX", "subsidio_empleo", on_date)
    imss_rule = lookup.get("MX", "imss_employee_rates", on_date)

    taxable_extras = sum(
        (Decimal(str(e["amount"])) for e in extras if not e.get("exempt", False)),
        Decimal("0"),
    )
    exempt_extras = sum(
        (Decimal(str(e["amount"])) for e in extras if e.get("exempt", False)),
        Decimal("0"),
    )

    monthly_taxable_base = monthly_base + taxable_extras
    isr_causado = compute_isr_mx(monthly_base=monthly_taxable_base, brackets=isr_rule.data)
    subsidio = compute_subsidio_empleo_mx(monthly_base=monthly_taxable_base, schedule=subs_rule.data)
    isr_retenido = max(Decimal("0"), isr_causado - subsidio)

    imss_employee = compute_imss_employee_mx(monthly_base=monthly_taxable_base, rates=imss_rule.data)

    bruto = monthly_taxable_base + exempt_extras
    liquido = bruto - isr_retenido - imss_employee
    # If subsidio > ISR causado, the difference is paid to the employee (entregable)
    subsidio_entregable = max(Decimal("0"), subsidio - isr_causado)
    if subsidio_entregable > 0:
        liquido += subsidio_entregable

    return {
        "bruto": _round(bruto),
        "conceptos": [
            {"code": "salario_base", "amount": _round(monthly_base), "exempt": False},
            *[{"code": e["code"], "amount": _round(Decimal(str(e["amount"]))), "exempt": bool(e.get("exempt"))} for e in extras],
        ],
        "isr": {
            "causado": isr_causado,
            "subsidio_empleo": subsidio,
            "retenido": isr_retenido,
            "entregable_al_empleado": subsidio_entregable,
        },
        "imss_empleado": {
            "amount": imss_employee,
            "total_rate": Decimal(str(imss_rule.data["total"])),
            "breakdown": {k: Decimal(str(v)) for k, v in imss_rule.data.items() if k not in ("total", "notes")},
        },
        "liquido": _round(liquido),
        "rules_applied": [
            {"rule": "isr_brackets", "effective_from": str(isr_rule.effective_from), "source": isr_rule.source},
            {"rule": "subsidio_empleo", "effective_from": str(subs_rule.effective_from), "source": subs_rule.source},
            {"rule": "imss_employee_rates", "effective_from": str(imss_rule.effective_from), "source": imss_rule.source},
        ],
    }
