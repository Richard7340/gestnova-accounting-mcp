from decimal import Decimal
from datetime import date
from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup
from gestnova_accounting.engine.calc.payroll_mx import (
    compute_isr_mx,
    compute_payroll_mx,
)


@pytest.fixture
def lookup() -> RuleLookup:
    return RuleLookup(Path(__file__).parent.parent.parent.parent / "packs")


def test_isr_bracket_lookup_15000(lookup):
    """Monthly base 15000 falls in 12935.83 - 15487.71 bracket:
    cuota_fija 1182.88 + (15000 - 12935.83) × 0.1792
    = 1182.88 + (2064.17 × 0.1792)
    = 1182.88 + 369.899264
    = 1552.779264 → ROUND_HALF_UP at cent = 1552.78"""
    tax = compute_isr_mx(
        monthly_base=Decimal("15000"),
        brackets=lookup.get("MX", "isr_brackets", date(2026, 5, 15)).data,
    )
    assert tax == Decimal("1552.78")


def test_isr_top_bracket(lookup):
    """Monthly base 400000 falls in top bracket (limite_inferior 375975.62):
    117912.32 + (400000 - 375975.62) × 0.35 = 117912.32 + 8408.53 = 126320.85"""
    tax = compute_isr_mx(
        monthly_base=Decimal("400000"),
        brackets=lookup.get("MX", "isr_brackets", date(2026, 5, 15)).data,
    )
    assert tax == Decimal("126320.85")


def test_payroll_mx_with_subsidio(lookup):
    """Monthly base 7000 (low income) qualifies for subsidio para empleo.
    Should reduce ISR retained or even pay employee back."""
    res = compute_payroll_mx(
        lookup=lookup,
        monthly_base=Decimal("7000"),
        extras=[],
        on_date=date(2026, 5, 15),
    )
    # Subsidio should be > 0 for income in this range
    assert res["isr"]["subsidio_empleo"] > 0


def test_payroll_mx_high_income_no_subsidio(lookup):
    """Monthly base 50000 (high income) has no subsidio."""
    res = compute_payroll_mx(
        lookup=lookup,
        monthly_base=Decimal("50000"),
        extras=[],
        on_date=date(2026, 5, 15),
    )
    assert res["isr"]["subsidio_empleo"] == Decimal("0.00")
    # ISR retained should be > 0 and substantial
    assert res["isr"]["retenido"] > Decimal("5000")


def test_payroll_mx_imss_employee_2375pct(lookup):
    """IMSS employee 50000 × 2.375% = 1187.50"""
    res = compute_payroll_mx(
        lookup=lookup,
        monthly_base=Decimal("50000"),
        extras=[],
        on_date=date(2026, 5, 15),
    )
    assert res["imss_empleado"]["amount"] == Decimal("1187.50")
    rules = [r["rule"] for r in res["rules_applied"]]
    assert "isr_brackets" in rules
    assert "imss_employee_rates" in rules


def test_payroll_mx_exempt_extra(lookup):
    """Despensa exenta 1000 should add to bruto but not to taxable base."""
    res = compute_payroll_mx(
        lookup=lookup,
        monthly_base=Decimal("20000"),
        extras=[{"code": "despensa", "amount": Decimal("1000"), "exempt": True}],
        on_date=date(2026, 5, 15),
    )
    # Bruto includes exempt
    assert res["bruto"] == Decimal("21000.00")
    # IMSS is on 20000 only (taxable base, not 21000)
    expected_imss = Decimal("20000") * Decimal("0.02375")
    assert res["imss_empleado"]["amount"] == expected_imss.quantize(Decimal("0.01"))
