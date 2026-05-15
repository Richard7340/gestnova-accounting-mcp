from decimal import Decimal
from datetime import date
from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup
from gestnova_accounting.engine.calc.payroll import (
    compute_irpf_tax,
    compute_ss_employee,
    compute_payroll_es,
)


@pytest.fixture
def real_es_lookup() -> RuleLookup:
    """Load the real ES pack we just committed."""
    return RuleLookup(Path(__file__).parent.parent.parent.parent / "packs")


def test_irpf_first_bracket_only(real_es_lookup):
    """Yearly base 10000 → entirely in 19% bracket → 1900."""
    tax = compute_irpf_tax(
        yearly_base=Decimal("10000"),
        brackets=real_es_lookup.get("ES", "irpf_brackets", date(2026, 5, 15)).data,
    )
    assert tax == Decimal("1900.00")


def test_irpf_spans_two_brackets(real_es_lookup):
    """Yearly base 15000:
    - 0..12450 at 19% = 2365.50
    - 12450..15000 (2550) at 24% = 612.00
    - total = 2977.50"""
    tax = compute_irpf_tax(
        yearly_base=Decimal("15000"),
        brackets=real_es_lookup.get("ES", "irpf_brackets", date(2026, 5, 15)).data,
    )
    assert tax == Decimal("2977.50")


def test_irpf_top_bracket_open_ended(real_es_lookup):
    """Yearly 400000 reaches the open-ended top bracket at 47%."""
    tax = compute_irpf_tax(
        yearly_base=Decimal("400000"),
        brackets=real_es_lookup.get("ES", "irpf_brackets", date(2026, 5, 15)).data,
    )
    # 12450*.19 + 7750*.24 + 15000*.30 + 24800*.37 + 240000*.45 + 100000*.47
    # = 2365.5 + 1860 + 4500 + 9176 + 108000 + 47000 = 172901.5
    assert tax == Decimal("172901.50")


def test_ss_employee_645_total(real_es_lookup):
    """SS employee on monthly 2500 base: 2500 * 6.45% = 161.25."""
    ss = compute_ss_employee(
        monthly_base=Decimal("2500"),
        rates=real_es_lookup.get("ES", "ss_employee_rates", date(2026, 5, 15)).data,
    )
    assert ss == Decimal("161.25")


def test_compute_payroll_es_end_to_end(real_es_lookup):
    """Employee with monthly base 2500, no extras, 12-month year → 30000.
    IRPF 30000:
      12450 * .19 = 2365.50
      7750 * .24 = 1860.00
      9800 * .30 = 2940.00  (20200..30000)
      total = 7165.50 yearly
      monthly = 597.13 (round)
    SS 2500 * 6.45% = 161.25
    Líquido = 2500 - 597.13 - 161.25 = 1741.62
    """
    res = compute_payroll_es(
        lookup=real_es_lookup,
        monthly_base=Decimal("2500"),
        extras=[],
        on_date=date(2026, 5, 15),
    )
    assert res["bruto"] == Decimal("2500.00")
    assert res["retencion_irpf"]["amount"] == Decimal("597.13")
    assert res["ss_empleado"]["amount"] == Decimal("161.25")
    assert res["liquido"] == Decimal("1741.62")
    rules = [r["rule"] for r in res["rules_applied"]]
    assert "irpf_brackets" in rules
    assert "ss_employee_rates" in rules


def test_exempt_extra_does_not_add_to_taxable_base(real_es_lookup):
    """Plus transporte 80€ exento should add to bruto but NOT to taxable base."""
    res = compute_payroll_es(
        lookup=real_es_lookup,
        monthly_base=Decimal("2500"),
        extras=[{"code": "plus_transport", "amount": Decimal("80"), "exempt": True}],
        on_date=date(2026, 5, 15),
    )
    # Bruto includes the 80
    assert res["bruto"] == Decimal("2580.00")
    # But IRPF retention is the same as without the extra (because exempt)
    assert res["retencion_irpf"]["amount"] == Decimal("597.13")
    # SS is on taxable base only (2500 still — exempt doesn't cotize either)
    assert res["ss_empleado"]["amount"] == Decimal("161.25")
    # Líquido = 2580 - 597.13 - 161.25 = 1821.62
    assert res["liquido"] == Decimal("1821.62")
