from datetime import date
import pytest
from gestnova_accounting.engine.rule_lookup import (
    RuleLookup,
    NoRuleApplicable,
)


def test_loads_pack_from_disk(sample_pack_dir):
    lookup = RuleLookup(sample_pack_dir)
    countries = lookup.supported_countries()
    assert "ES" in countries


def test_gets_currently_effective_rule(sample_pack_dir, today):
    lookup = RuleLookup(sample_pack_dir)
    rule = lookup.get("ES", "irpf_brackets", today)
    assert rule.country == "ES"
    assert rule.effective_from == date(2026, 1, 1)
    assert rule.effective_until is None
    assert len(rule.data) == 2


def test_gets_historical_rule_by_date(sample_pack_dir):
    """Asking for 2025 should give us the 2025 pack, not the 2026."""
    lookup = RuleLookup(sample_pack_dir)
    rule = lookup.get("ES", "irpf_brackets", date(2025, 6, 15))
    assert rule.effective_from == date(2025, 1, 1)
    assert rule.effective_until == date(2025, 12, 31)


def test_raises_when_rule_not_found(sample_pack_dir):
    lookup = RuleLookup(sample_pack_dir)
    with pytest.raises(NoRuleApplicable) as exc:
        lookup.get("ES", "does_not_exist", date(2026, 5, 15))
    assert "does_not_exist" in str(exc.value)
    assert "ES" in str(exc.value)


def test_raises_when_country_not_supported(sample_pack_dir):
    lookup = RuleLookup(sample_pack_dir)
    with pytest.raises(NoRuleApplicable) as exc:
        lookup.get("FR", "irpf_brackets", date(2026, 5, 15))
    assert "FR" in str(exc.value)


def test_picks_most_recent_when_multiple_match(sample_pack_dir):
    """If 2025 was effective_until 2025-12-31 and 2026 starts 2026-01-01,
    a query for 2026-05-15 must pick the 2026 version, not 2025."""
    lookup = RuleLookup(sample_pack_dir)
    rule = lookup.get("ES", "irpf_brackets", date(2026, 5, 15))
    assert rule.effective_from.year == 2026
