"""Database access via SQLAlchemy — same code for local SQLite and SQL Server.

Wraps one engine, ensures the relational schema (see schema.py), records an
ingest run for auditing, and upserts fact rows idempotently (delete-by-key +
insert, which works on both dialects).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Table, and_, create_engine, func, select

from robot_framework import schema
from robot_framework.settings import DateRange, Settings

# meta_ingest_run.mode value that advances the incremental watermark. Explicit
# gap-fill / manual runs use a different mode and never move the frontier.
INCREMENTAL_MODE = "incremental"


def _now() -> datetime:
    """Naive UTC timestamp for audit columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Database:
    """Relational warehouse for the statistics facts."""

    def __init__(self, engine):
        self._engine = engine
        schema.ensure_schema(engine)
        schema.seed(engine)

    # --- Ingest run auditing ----------------------------------------------

    def start_run(self, date_range: DateRange, mode: str,
                  ingest_version: int) -> int:
        """Open a meta_ingest_run row and return its run_id."""
        with self._engine.begin() as conn:
            result = conn.execute(schema.meta_ingest_run.insert().values(
                started_at=_now(), from_date=date_range.iso_from,
                to_date=date_range.iso_to, mode=mode,
                ingest_version=ingest_version, status="running", rows_written=0))
            return result.inserted_primary_key[0]

    def finish_run(self, run_id: int, status: str, rows_written: int,
                   error: str | None = None) -> None:
        """Close a run with its final status and row count."""
        with self._engine.begin() as conn:
            conn.execute(schema.meta_ingest_run.update()
                         .where(schema.meta_ingest_run.c.run_id == run_id)
                         .values(finished_at=_now(), status=status,
                                 rows_written=rows_written, error=error))

    def watermark(self) -> str | None:
        """Latest `to_date` of a completed incremental run, or None.

        Derived from meta_ingest_run — the single source of truth. Explicit
        (manual) runs use another mode and are excluded, so they never move the
        frontier. ISO datetimes at midnight sort correctly by their date prefix.
        """
        with self._engine.connect() as conn:
            return conn.execute(
                select(func.max(schema.meta_ingest_run.c.to_date)).where(
                    schema.meta_ingest_run.c.status == "done",
                    schema.meta_ingest_run.c.mode == INCREMENTAL_MODE)).scalar()

    # --- Writing ----------------------------------------------------------

    def write_raw(self, run_id: int, kpi: str, channel: str, domain: str,
                  *, date_range: DateRange, payload: Any) -> None:
        """Store a raw API response for traceability/re-ingestion."""
        with self._engine.begin() as conn:
            conn.execute(schema.stg_raw_response.insert().values(
                run_id=run_id, kpi=kpi, channel=channel, domain=domain,
                from_date=date_range.iso_from, to_date=date_range.iso_to,
                fetched_at=_now(),
                payload_json=json.dumps(payload, ensure_ascii=False)))

    def upsert(self, table: Table, rows: list[dict], run_id: int) -> int:
        """Idempotent upsert: delete rows sharing the primary key, then insert."""
        if not rows:
            return 0
        key_cols = [c.name for c in table.primary_key.columns]
        loaded_at = _now()
        stamped = [{**row, "run_id": run_id, "loaded_at": loaded_at}
                   for row in rows]
        with self._engine.begin() as conn:
            for row in stamped:
                conn.execute(table.delete().where(
                    and_(*[table.c[k] == row[k] for k in key_cols])))
            conn.execute(table.insert(), stamped)
        return len(stamped)

    def close(self) -> None:
        """Dispose of the engine."""
        self._engine.dispose()


def make_database(settings: Settings, credentials=None) -> Database:
    """Build a Database from a connection string (prod) or SQLite path (local)."""
    connection_string = getattr(credentials, "sql_connection_string", None)
    if connection_string:
        return Database(create_engine(connection_string))
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    return Database(create_engine(f"sqlite:///{settings.sqlite_path}"))
