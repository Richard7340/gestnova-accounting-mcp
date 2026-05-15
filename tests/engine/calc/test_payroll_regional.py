"""Regional payroll: same gross base → different IRPF by CCAA."""
from decimal import Decimal
from datetime import date
from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup
from gestnova_accounting.engine.calc.payroll import compute_payroll_es


@pytest.fixture
def lookup() -> RuleLookup:
    return RuleLookup(Path(__file__).parent.parent.parent.parent / "packs")


def test_same_base_gives_different_irpf_per_region(lookup):
    """Monthly base 2500 (= 30000 yearly) computed under national / Madrid / Cataluña.

    Expected ordering (Madrid lowest, Cataluña highest):
        Madrid IRPF < National IRPF < Cataluña IRPF
    """
    nat = compute_payroll_es(lookup=lookup, monthly_base=Decimal("2500"), extras=[], on_date=date(2026, 5, 15))
    mad = compute_payroll_es(lookup=lookup, monthly_base=Decimal("2500"), extras=[], on_date=date(2026, 5, 15), region="madrid")
    cat = compute_payroll_es(lookup=lookup, monthly_base=Decimal("2500"), extras=[], on_date=date(2026, 5, 15), region="cataluna")

    nat_irpf = nat["retencion_irpf"]["amount"]
    mad_irpf = mad["retencion_irpf"]["amount"]
    cat_irpf = cat["retencion_irpf"]["amount"]

    assert mad_irpf < nat_irpf
    assert nat_irpf < cat_irpf

    # Liquido inversely ordered
    assert mad["liquido"] > nat["liquido"]
    assert nat["liquido"] > cat["liquido"]


def test_madrid_source_cited(lookup):
    res = compute_payroll_es(lookup=lookup, monthly_base=Decimal("3000"), extras=[], on_date=date(2026, 5, 15), region="madrid")
    sources = [r["source"] for r in res["rules_applied"]]
    assert any("BOCM" in s for s in sources)


def test_unknown_region_uses_national_payroll(lookup):
    """Compute with region='galicia' (no overlay) — should match national result."""
    nat = compute_payroll_es(lookup=lookup, monthly_base=Decimal("3000"), extras=[], on_date=date(2026, 5, 15))
    gal = compute_payroll_es(lookup=lookup, monthly_base=Decimal("3000"), extras=[], on_date=date(2026, 5, 15), region="galicia")
    assert nat["liquido"] == gal["liquido"]
