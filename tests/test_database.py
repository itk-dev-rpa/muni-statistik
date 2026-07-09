"""Tests for Database — run auditing and idempotent upsert (SQLite)."""
# pylint: disable=missing-function-docstring,protected-access,not-callable

from sqlalchemy import create_engine, func, select

from robot_framework import schema
from robot_framework.database import Database
from robot_framework.settings import DateRange, Settings

ROWS = [
    {"date": "2026-06-01", "channel": "chat", "domain": "aarhus.dk",
     "conversations": 533, "messages": 3915},
    {"date": "2026-06-02", "channel": "chat", "domain": "aarhus.dk",
     "conversations": 461, "messages": 3225},
]


def _db(tmp_path):
    return Database(create_engine(f"sqlite:///{tmp_path / 'wh.sqlite'}"))


def _count(db, table):
    with db._engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar()


def _range():
    return Settings(tenant="ddh", scope="analytics:v1", timezone="Europe/Copenhagen",
                    ingest_version=1, backfill_start="2025-02-01").yesterday_range()


def test_upsert_is_idempotent(tmp_path):
    db = _db(tmp_path)
    try:
        run_id = db.start_run(_range(), "manual", 1)
        db.upsert(schema.fact_conversations_daily, ROWS, run_id)
        db.upsert(schema.fact_conversations_daily, ROWS, run_id)  # rerun
        assert _count(db, schema.fact_conversations_daily) == 2
    finally:
        db.close()


def test_upsert_updates_existing(tmp_path):
    db = _db(tmp_path)
    try:
        run_id = db.start_run(_range(), "manual", 1)
        db.upsert(schema.fact_conversations_daily, ROWS, run_id)
        db.upsert(schema.fact_conversations_daily,
                  [{"date": "2026-06-01", "channel": "chat", "domain": "aarhus.dk",
                    "conversations": 999, "messages": 4000}], run_id)
        with db._engine.connect() as conn:
            value = conn.execute(
                select(schema.fact_conversations_daily.c.conversations).where(
                    schema.fact_conversations_daily.c.date == "2026-06-01")).scalar()
        assert value == 999
        assert _count(db, schema.fact_conversations_daily) == 2
    finally:
        db.close()


def test_watermark_from_done_incremental_runs(tmp_path):
    db = _db(tmp_path)
    s = Settings(tenant="ddh", scope="a", timezone="Europe/Copenhagen",
                 ingest_version=1, backfill_start="2025-02-01")
    try:
        assert db.watermark() is None  # empty -> no watermark
        # A completed incremental run advances the watermark.
        r1 = db.start_run(DateRange(s.parse_day("2026-06-01"), s.parse_day("2026-06-08")),
                          "incremental", 1)
        db.finish_run(r1, "done", 1)
        # A later manual (gap-fill) run must NOT move the watermark.
        r2 = db.start_run(DateRange(s.parse_day("2026-06-08"), s.parse_day("2026-06-20")),
                          "manual", 1)
        db.finish_run(r2, "done", 1)
        # A later failed incremental run must NOT move the watermark.
        r3 = db.start_run(DateRange(s.parse_day("2026-06-08"), s.parse_day("2026-06-15")),
                          "incremental", 1)
        db.finish_run(r3, "failed", 0)
        assert db.watermark().startswith("2026-06-08")
    finally:
        db.close()


def test_run_lifecycle_records_status(tmp_path):
    db = _db(tmp_path)
    try:
        run_id = db.start_run(_range(), "nightly", 1)
        db.finish_run(run_id, "done", 5)
        with db._engine.connect() as conn:
            status, rows = conn.execute(
                select(schema.meta_ingest_run.c.status,
                       schema.meta_ingest_run.c.rows_written).where(
                    schema.meta_ingest_run.c.run_id == run_id)).one()
        assert status == "done"
        assert rows == 5
    finally:
        db.close()
