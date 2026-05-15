"""ES payroll calculator — IRPF brackets, SS employee, net pay.

Note: this is a SIMPLE annualization approach (monthly base × 12). Real-world
payroll uses regularization formulas that account for variable concepts and
mid-year adjustments — those go in Plan 4 (production refinement).
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Any
from ..rule_lookup import RuleLookup


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_irpf_tax(*, yearly_base: Decimal, brackets: list[dict]) -> Decimal:
    """Apply progressive IRPF brackets to a yearly taxable base."""
    tax = Decimal("0")
    for entry in brackets:
        lo, hi = entry["bracket"]
        rate = Decimal(str(entry["rate"]))
        lo_d = Decimal(str(lo))
        hi_d = Decimal(str(hi)) if hi is not None else None
        if yearly_base <= lo_d:
            break
        taxable_in_bracket = (
            yearly_base - lo_d if hi_d is None else min(yearly_base, hi_d) - lo_d
        )
        tax += taxable_in_bracket * rate
    return _round(tax)


def compute_ss_employee(*, monthly_base: Decimal, rates: dict) -> Decimal:
    """SS employee contribution on monthly cotization base."""
    total_rate = Decimal(str(rates["total"]))
    return _round(monthly_base * total_rate)


def compute_payroll_es(
    *,
    lookup: RuleLookup,
    monthly_base: Decimal,
    extras: list[dict[str, Any]] | None = None,
    on_date: date,
    region: str | None = None,
) -> dict[str, Any]:
    """Full ES payroll computation for one month.

    `extras`: list of {code, amount, exempt: bool}. Exempt extras add to bruto
    but not to taxable base or SS base.

    `region`: optional CCAA code (e.g. 'madrid', 'cataluna'). When provided,
    the IRPF brackets are looked up with regional overlay (falls back to
    national if no region-specific rule exists). SS rates are common to all
    of Spain so they're always looked up nationally.
    """
    extras = extras or []
    irpf_rule = lookup.get("ES", "irpf_brackets", on_date, region=region)
    ss_rule = lookup.get("ES", "ss_employee_rates", on_date)

    taxable_extras = sum(
        (Decimal(str(e["amount"])) for e in extras if not e.get("exempt", False)),
        Decimal("0"),
    )
    exempt_extras = sum(
        (Decimal(str(e["amount"])) for e in extras if e.get("exempt", False)),
        Decimal("0"),
    )

    monthly_taxable_base = monthly_base + taxable_extras
    yearly_taxable_base = monthly_taxable_base * 12
    yearly_irpf = compute_irpf_tax(
        yearly_base=yearly_taxable_base, brackets=irpf_rule.data
    )
    monthly_irpf = _round(yearly_irpf / 12)
    effective_rate = _round(yearly_irpf / yearly_taxable_base) if yearly_taxable_base else Decimal("0")

    ss_employee = compute_ss_employee(monthly_base=monthly_taxable_base, rates=ss_rule.data)

    bruto = monthly_taxable_base + exempt_extras
    liquido = bruto - monthly_irpf - ss_employee

    return {
        "bruto": _round(bruto),
        "conceptos": [
            {"code": "salario_base", "amount": _round(monthly_base), "exempt": False},
            *[{"code": e["code"], "amount": _round(Decimal(str(e["amount"]))), "exempt": bool(e.get("exempt"))} for e in extras],
        ],
        "retencion_irpf": {
            "amount": monthly_irpf,
            "yearly_amount": yearly_irpf,
            "effective_rate": effective_rate,
        },
        "ss_empleado": {
            "amount": ss_employee,
            "total_rate": Decimal(str(ss_rule.data["total"])),
            "breakdown": {k: Decimal(str(v)) for k, v in ss_rule.data.items() if k != "total"},
        },
        "liquido": _round(liquido),
        "rules_applied": [
            {"rule": "irpf_brackets", "effective_from": str(irpf_rule.effective_from), "source": irpf_rule.source},
            {"rule": "ss_employee_rates", "effective_from": str(ss_rule.effective_from), "source": ss_rule.source},
        ],
    }
