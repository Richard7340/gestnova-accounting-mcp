"""Validates that each country pack defines the minimum required rules."""
from datetime import date
from .rule_lookup import RuleLookup, NoRuleApplicable


# A country must define at least one rule from each REQUIRED_OR group.
REQUIRED_KEYS: dict[str, list[list[str]]] = {
    "payroll": [
        ["irpf_brackets", "isr_brackets"],   # ES uses irpf, MX uses isr
        ["ss_employee_rates", "imss_employee_rates"],
        ["ss_employer_rates", "imss_employer_rates"],
    ],
    "leave": [
        ["vacation_days_minimum"],
        ["leave_reasons"],
    ],
    "time_tracking": [
        ["max_daily_hours"],
        ["max_weekly_hours"],
        ["max_overtime_yearly"],
    ],
}


class PackValidationError(Exception):
    def __init__(self, country: str, missing: list[str]):
        self.country = country
        self.missing = missing
        super().__init__(
            f"Pack '{country}' is missing required rules: {missing}. "
            f"Each area must define at least one of the grouped keys."
        )


def validate_country_pack(lookup: RuleLookup, country: str, on_date: date | None = None) -> None:
    on_date = on_date or date.today()
    missing: list[str] = []
    for area, groups in REQUIRED_KEYS.items():
        for group in groups:
            found = False
            for key in group:
                try:
                    lookup.get(country, key, on_date)
                    found = True
                    break
                except NoRuleApplicable:
                    continue
            if not found:
                missing.append(f"{area}: one of {group}")
    if missing:
        raise PackValidationError(country, missing)
