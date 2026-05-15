"""SQLite-backed audit log for every tool calculation.

Each entry is reproducible: tool + inputs + rules_applied → result.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calculations (
    id TEXT PRIMARY KEY,
    tool TEXT NOT NULL,
    country TEXT NOT NULL,
    inputs_hash TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    rules_applied_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tool_created ON calculations(tool, created_at);
CREATE INDEX IF NOT EXISTS idx_country_created ON calculations(country, created_at);
"""


class CalculationLog:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(
        self,
        *,
        tool: str,
        country: str,
        inputs: dict[str, Any],
        rules_applied: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> str:
        cid = str(uuid.uuid4())
        inputs_json = json.dumps(inputs, sort_keys=True, default=str)
        inputs_hash = hashlib.sha256(inputs_json.encode()).hexdigest()
        with self._conn() as c:
            c.execute(
                "INSERT INTO calculations (id, tool, country, inputs_hash, inputs_json, "
                "rules_applied_json, result_json) VALUES (?,?,?,?,?,?,?)",
                (cid, tool, country, inputs_hash, inputs_json,
                 json.dumps(rules_applied, default=str), json.dumps(result, default=str)),
            )
        return cid

    def get(self, calculation_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM calculations WHERE id=?", (calculation_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "tool": row["tool"],
            "country": row["country"],
            "inputs_hash": row["inputs_hash"],
            "inputs": json.loads(row["inputs_json"]),
            "rules_applied": json.loads(row["rules_applied_json"]),
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    def list(self, *, tool: Optional[str] = None, country: Optional[str] = None) -> list[dict[str, Any]]:
        q = "SELECT id FROM calculations WHERE 1=1"
        params: list[Any] = []
        if tool:
            q += " AND tool = ?"
            params.append(tool)
        if country:
            q += " AND country = ?"
            params.append(country)
        q += " ORDER BY created_at DESC"
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [self.get(r["id"]) for r in rows]
