"""Output sinks: where normalized rows + raw JSON land.

Two implementations behind the same protocol:
- `SqliteSink`: local SQLite file for development/testing. Provides real
  idempotent upsert (INSERT OR REPLACE), so re-running the same range does not
  duplicate.
- `SqlServerSink`: production (MS SQL Server). Stub until DB details are known.

The sink creates tables dynamically from the row fields, so the schema follows
the KPI normalizers while the model matures.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from robot_framework.settings import DateRange, Settings

RAW_TABLE = "stg_raw_response"


class Sink(Protocol):
    """Common contract for output targets."""

    def write_raw(self, stat: str, date_range: DateRange, payload: Any) -> None:
        """Store the raw API response for traceability/re-ingestion."""

    def upsert(self, table: str, rows: list[dict],
               key_columns: tuple[str, ...]) -> int:
        """Idempotent upsert of rows. Returns the number of rows written."""

    def close(self) -> None:
        """Close any resources."""


def _sql_type(value: Any) -> str:
    """Simple type mapping from a Python value to a SQLite column type."""
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


class SqliteSink:
    """Local SQLite sink for development and testing."""

    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._ensure_raw_table()

    def _ensure_raw_table(self) -> None:
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {RAW_TABLE} ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "stat TEXT, from_date TEXT, to_date TEXT, "
            "fetched_at TEXT DEFAULT CURRENT_TIMESTAMP, payload_json TEXT)")
        self._conn.commit()

    def _ensure_table(self, table: str, row: dict,
                      key_columns: tuple[str, ...]) -> None:
        columns = [f'"{name}" {_sql_type(value)}' for name, value in row.items()]
        pk = ", ".join(f'"{col}"' for col in key_columns)
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{table}" '
            f"({', '.join(columns)}, PRIMARY KEY ({pk}))")
        self._conn.commit()

    def write_raw(self, stat: str, date_range: DateRange, payload: Any) -> None:
        """Store raw JSON in the staging table."""
        self._conn.execute(
            f"INSERT INTO {RAW_TABLE} (stat, from_date, to_date, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (stat, date_range.iso_from, date_range.iso_to,
             json.dumps(payload, ensure_ascii=False)))
        self._conn.commit()

    def upsert(self, table: str, rows: list[dict],
               key_columns: tuple[str, ...]) -> int:
        """Idempotent upsert via INSERT OR REPLACE. Returns the row count."""
        if not rows:
            return 0
        self._ensure_table(table, rows[0], key_columns)
        columns = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in columns)
        col_list = ", ".join(f'"{col}"' for col in columns)
        self._conn.executemany(
            f'INSERT OR REPLACE INTO "{table}" ({col_list}) '
            f"VALUES ({placeholders})",
            [tuple(row[col] for col in columns) for row in rows])
        self._conn.commit()
        return len(rows)

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()


class SqlServerSink:  # pylint: disable=too-few-public-methods
    """Production sink for MS SQL Server. [TO BE FILLED IN: DB details + pyodbc]."""

    def __init__(self, settings: Settings, credentials):
        raise NotImplementedError(
            "SqlServerSink is not implemented yet. Set SINK_TYPE='sqlite' in "
            "config.py for local testing. To be implemented once SQL Server "
            "details and pyodbc are in place (see PDD.md section 10).")


def make_sink(settings: Settings, credentials=None) -> Sink:
    """Select the sink implementation based on configuration."""
    if settings.sink_type == "sqlite":
        return SqliteSink(settings.sqlite_path)
    if settings.sink_type == "sqlserver":
        return SqlServerSink(settings, credentials)
    raise ValueError(f"Unknown sink.type: '{settings.sink_type}'")
