"""Shared pytest fixtures."""
from datetime import date
from pathlib import Path
import pytest


@pytest.fixture
def sample_pack_dir(tmp_path: Path) -> Path:
    """Build a minimal ES pack on disk for tests."""
    pack = tmp_path / "packs" / "es"
    (pack / "payroll").mkdir(parents=True)

    payroll_2026 = pack / "payroll" / "2026.yaml"
    payroll_2026.write_text(
        """\
- rule: irpf_brackets
  country: ES
  effective_from: 2026-01-01
  effective_until: null
  source: "BOE 2025-12-31 RD 1234/2025 (fixture)"
  data:
    - bracket: [0, 12450]
      rate: 0.19
    - bracket: [12450, 20200]
      rate: 0.24
- rule: ss_employee_rates
  country: ES
  effective_from: 2026-01-01
  effective_until: null
  source: "Orden PCM/.../2025 (fixture)"
  data:
    common_contingencies: 0.047
    unemployment: 0.0155
    professional_training: 0.001
    mei: 0.001
    total: 0.0645
""",
        encoding="utf-8",
    )

    # Historical pack (2025) to test vigencia overlap
    payroll_2025 = pack / "payroll" / "2025.yaml"
    payroll_2025.write_text(
        """\
- rule: irpf_brackets
  country: ES
  effective_from: 2025-01-01
  effective_until: 2025-12-31
  source: "BOE 2024-12-31 (fixture)"
  data:
    - bracket: [0, 12450]
      rate: 0.19
""",
        encoding="utf-8",
    )

    return tmp_path / "packs"


@pytest.fixture
def today() -> date:
    return date(2026, 5, 15)
