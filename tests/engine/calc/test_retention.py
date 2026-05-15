from decimal import Decimal
from datetime import date
from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup
from gestnova_accounting.engine.calc.retention import compute_retention_es


@pytest.fixture
def real_es_lookup() -> RuleLookup:
    return RuleLookup(Path(__file__).parent.parent.parent.parent / "packs")


def test_standard_professional_retention_15pct(real_es_lookup):
    """Honorarios 1000€ → retención 150€ (15% standard)."""
    res = compute_retention_es(
        lookup=real_es_lookup, base=Decimal("1000"), is_new_professional=False, on_date=date(2026, 5, 15)
    )
    assert res["rate"] == Decimal("0.15")
    assert res["amount"] == Decimal("150.00")


def test_new_professional_retention_7pct(real_es_lookup):
    """New professional first 3 years → 7%."""
    res = compute_retention_es(
        lookup=real_es_lookup, base=Decimal("1000"), is_new_professional=True, on_date=date(2026, 5, 15)
    )
    assert res["rate"] == Decimal("0.07")
    assert res["amount"] == Decimal("70.00")
