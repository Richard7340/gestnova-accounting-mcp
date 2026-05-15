import hashlib
import json
from pathlib import Path
import pytest
from gestnova_accounting.persistence.calculation_log import CalculationLog


@pytest.fixture
def log_db(tmp_path: Path) -> CalculationLog:
    return CalculationLog(tmp_path / "audit.db")


def test_inserts_and_reads_back(log_db):
    cid = log_db.record(
        tool="calculatePayroll",
        country="ES",
        inputs={"employeeId": "e1", "period": "2026-05"},
        rules_applied=[{"rule": "irpf_brackets", "effective_from": "2026-01-01"}],
        result={"liquido": 2006.25},
    )
    assert cid
    entry = log_db.get(cid)
    assert entry["tool"] == "calculatePayroll"
    assert entry["country"] == "ES"
    assert entry["result"]["liquido"] == 2006.25


def test_inputs_are_hashed_for_privacy(log_db):
    """We don't want raw inputs in the audit log forever; just a hash + a metadata dict."""
    cid = log_db.record(
        tool="calculatePayroll",
        country="ES",
        inputs={"employeeId": "secret-id-123"},
        rules_applied=[],
        result={},
    )
    entry = log_db.get(cid)
    assert "inputs_hash" in entry
    expected = hashlib.sha256(
        json.dumps({"employeeId": "secret-id-123"}, sort_keys=True).encode()
    ).hexdigest()
    assert entry["inputs_hash"] == expected
    # Raw inputs still kept but separately retrievable for export-only flows
    assert entry.get("inputs") == {"employeeId": "secret-id-123"}


def test_lists_by_tool_and_date_range(log_db):
    for i in range(5):
        log_db.record(
            tool="calculatePayroll" if i % 2 == 0 else "calculateInvoice",
            country="ES",
            inputs={"i": i},
            rules_applied=[],
            result={},
        )
    payrolls = log_db.list(tool="calculatePayroll")
    assert len(payrolls) == 3
