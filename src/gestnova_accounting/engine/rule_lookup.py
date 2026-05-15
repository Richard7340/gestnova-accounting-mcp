"""Versioned legal-rules resolver.

Loads YAML packs from disk and resolves rules by (country, key, date) using
effective_from / effective_until vigencias. If two rules overlap, the one with
the most recent effective_from wins.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel
from ruamel.yaml import YAML


class Rule(BaseModel):
    rule: str
    country: str
    effective_from: date
    effective_until: Optional[date] = None
    source: str
    data: Any
    # Plan 7 — optional sub-national scope. None = national-level rule.
    # When set, e.g. 'madrid' or 'cataluna' (ES) or 'cdmx' (MX), the rule
    # only applies if the caller passes the matching region. RuleLookup
    # falls back to the national rule when no region-specific match exists.
    region: Optional[str] = None


class NoRuleApplicable(Exception):
    def __init__(self, country: str, key: str, on_date: date, hint: str = ""):
        self.country = country
        self.key = key
        self.on_date = on_date
        self.hint = hint
        super().__init__(
            f"No rule '{key}' applicable for country={country} on {on_date.isoformat()}. {hint}"
        )


class RuleLookup:
    """Loads YAML packs from `packs/<country>/**/*.yaml` and resolves rules."""

    def __init__(self, packs_root: Path):
        self._packs_root = Path(packs_root)
        self._rules: dict[tuple[str, str], list[Rule]] = {}
        self._countries: set[str] = set()
        self._load()

    def _load(self) -> None:
        yaml = YAML(typ="safe")
        if not self._packs_root.exists():
            return
        for country_dir in self._packs_root.iterdir():
            if not country_dir.is_dir():
                continue
            country = country_dir.name.upper()
            self._countries.add(country)
            for yaml_path in country_dir.rglob("*.yaml"):
                # Infer region from path: packs/<country>/regions/<region>/...yaml
                parts = yaml_path.relative_to(country_dir).parts
                inferred_region = None
                if len(parts) >= 2 and parts[0] == "regions":
                    inferred_region = parts[1]

                raw = yaml.load(yaml_path.read_text(encoding="utf-8"))
                if not raw:
                    continue
                for entry in raw:
                    # If YAML didn't specify region but path is under regions/, infer it.
                    if "region" not in entry and inferred_region:
                        entry["region"] = inferred_region
                    rule = Rule(**entry)
                    key = (rule.country, rule.rule)
                    self._rules.setdefault(key, []).append(rule)
        # Sort each rule list by effective_from descending (most-recent first)
        for k in self._rules:
            self._rules[k].sort(key=lambda r: r.effective_from, reverse=True)

    def supported_countries(self) -> list[str]:
        return sorted(self._countries)

    def get(self, country: str, key: str, on_date: date, region: Optional[str] = None) -> Rule:
        """Resolve a rule for (country, key, date) with optional region override.

        When `region` is provided, FIRST try to find a region-specific rule whose
        vigencia covers `on_date`. If none, fall back to the national rule
        (region=None) for the same key. Raises NoRuleApplicable if nothing
        applies.
        """
        candidates = self._rules.get((country, key), [])
        if not candidates:
            if country not in self._countries:
                raise NoRuleApplicable(country, key, on_date, hint=f"Country '{country}' not loaded.")
            raise NoRuleApplicable(country, key, on_date, hint=f"Rule '{key}' not defined for {country}.")

        # First pass: region-specific match (if region was requested)
        if region:
            for rule in candidates:
                if rule.region == region and rule.effective_from <= on_date and (
                    rule.effective_until is None or on_date <= rule.effective_until
                ):
                    return rule

        # Second pass: national fallback (region is None)
        for rule in candidates:
            if rule.region is None and rule.effective_from <= on_date and (
                rule.effective_until is None or on_date <= rule.effective_until
            ):
                return rule

        raise NoRuleApplicable(
            country, key, on_date,
            hint=(
                f"No vigencia covers {on_date.isoformat()} for region={region or 'national'}. "
                f"Most recent rule starts {candidates[0].effective_from.isoformat()}."
            ),
        )

    def get_all_for_area(self, country: str, key_prefix: str, on_date: date) -> list[Rule]:
        """Return all currently-applicable rules whose key starts with `key_prefix`."""
        result = []
        for (c, k), rules in self._rules.items():
            if c == country and k.startswith(key_prefix):
                try:
                    result.append(self.get(c, k, on_date))
                except NoRuleApplicable:
                    continue
        return result
