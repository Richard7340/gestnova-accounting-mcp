from pathlib import Path
import pytest
from gestnova_accounting.engine.rule_lookup import RuleLookup
from gestnova_accounting.engine.pack_validator import (
    validate_country_pack,
    PackValidationError,
)


def test_validates_complete_pack(sample_pack_dir):
    lookup = RuleLookup(sample_pack_dir)
    # Sample pack only has payroll rules — should report missing leave/time_tracking
    with pytest.raises(PackValidationError) as exc:
        validate_country_pack(lookup, "ES")
    assert "leave" in str(exc.value).lower() or "vacation" in str(exc.value).lower()


def test_validates_against_real_es_pack(tmp_path: Path):
    """When ALL required rules are present, validation succeeds."""
    pack = tmp_path / "packs" / "es"
    (pack / "payroll").mkdir(parents=True)
    (pack / "payroll" / "2026.yaml").write_text(
        """\
- {rule: irpf_brackets, country: ES, effective_from: 2026-01-01, source: x, data: []}
- {rule: ss_employee_rates, country: ES, effective_from: 2026-01-01, source: x, data: {}}
- {rule: ss_employer_rates, country: ES, effective_from: 2026-01-01, source: x, data: {}}
""",
        encoding="utf-8",
    )
    (pack / "leave.yaml").write_text(
        """\
- {rule: vacation_days_minimum, country: ES, effective_from: 2026-01-01, source: x, data: 30}
- {rule: leave_reasons, country: ES, effective_from: 2026-01-01, source: x, data: {}}
""",
        encoding="utf-8",
    )
    (pack / "time_tracking.yaml").write_text(
        """\
- {rule: max_daily_hours, country: ES, effective_from: 2026-01-01, source: x, data: 9}
- {rule: max_weekly_hours, country: ES, effective_from: 2026-01-01, source: x, data: 40}
- {rule: max_overtime_yearly, country: ES, effective_from: 2026-01-01, source: x, data: 80}
""",
        encoding="utf-8",
    )
    lookup = RuleLookup(tmp_path / "packs")
    # No raise = ok
    validate_country_pack(lookup, "ES")
