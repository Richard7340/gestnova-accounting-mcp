"""Regional rule lookup with national fallback."""
from datetime import date
from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup


@pytest.fixture
def lookup() -> RuleLookup:
    return RuleLookup(Path(__file__).parent.parent.parent / "packs")


def test_national_lookup_unchanged(lookup):
    """Existing callers that pass no region must still resolve to national."""
    rule = lookup.get("ES", "irpf_brackets", date(2026, 5, 15))
    assert rule.region is None
    assert "PGE 2026" in rule.source


def test_madrid_overlay_picked(lookup):
    rule = lookup.get("ES", "irpf_brackets", date(2026, 5, 15), region="madrid")
    assert rule.region == "madrid"
    assert "BOCM" in rule.source
    # Madrid first bracket = 18% (vs 19% national)
    assert rule.data[0]["rate"] == 0.18


def test_cataluna_overlay_picked(lookup):
    rule = lookup.get("ES", "irpf_brackets", date(2026, 5, 15), region="cataluna")
    assert rule.region == "cataluna"
    assert "DOGC" in rule.source
    # Cataluña first bracket = 21.5% (highest in ES)
    assert rule.data[0]["rate"] == 0.215


def test_unknown_region_falls_back_to_national(lookup):
    rule = lookup.get("ES", "irpf_brackets", date(2026, 5, 15), region="galicia")
    assert rule.region is None
    assert rule.data[0]["rate"] == 0.19


def test_no_regional_holidays_for_unrequested_region(lookup):
    """regional_holidays only exists under regions/, so requesting national raises."""
    from gestnova_accounting.engine.rule_lookup import NoRuleApplicable
    with pytest.raises(NoRuleApplicable):
        lookup.get("ES", "regional_holidays", date(2026, 5, 15))


def test_madrid_holidays_loaded(lookup):
    rule = lookup.get("ES", "regional_holidays", date(2026, 5, 15), region="madrid")
    dates = [h["date"] for h in rule.data]
    assert "2026-05-02" in dates       # Dos de Mayo
    assert "2026-05-15" in dates       # San Isidro


def test_cataluna_holidays_loaded(lookup):
    rule = lookup.get("ES", "regional_holidays", date(2026, 5, 15), region="cataluna")
    dates = [h["date"] for h in rule.data]
    assert "2026-09-11" in dates       # Diada
    assert "2026-06-24" in dates       # Sant Joan
