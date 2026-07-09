"""End-to-end ingest test with a fake boost client and a local SQLite DB."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access
# pylint: disable=too-few-public-methods,unused-argument,not-callable

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select

from robot_framework import schema
from robot_framework.database import Database
from robot_framework.ingest import run_incremental, run_ingest
from robot_framework.settings import DateRange, Settings

TZ = ZoneInfo("Europe/Copenhagen")

MESSAGE_HISTOGRAM = {"label": "MESSAGE", "histogram": [
    {"period": "2026-06-01T00:00:00+02:00", "conversations": 10, "messages": 50},
    {"period": "2026-06-02T00:00:00+02:00", "conversations": 20, "messages": 90},
]}
INTENTS = {"headers": ["id", "intent_title", "count"], "values": [[1, "Hej", 7]]}


class FakeClient:
    def __init__(self):
        self.filters_seen = []

    def histogram(self, stat, date_range, group_by="day", **filters):
        self.filters_seen.append(filters)
        return MESSAGE_HISTOGRAM

    def frequency(self, stat, date_range, limit=None, **filters):
        self.filters_seen.append(filters)
        return INTENTS


def _settings():
    return Settings(tenant="ddh", scope="analytics:v1", timezone="Europe/Copenhagen",
                    ingest_version=1, backfill_start="2025-02-01",
                    enabled_kpis=["conversations", "intents"],
                    channels=[("chat", False)])


def _range():
    return DateRange(datetime(2026, 6, 1, tzinfo=TZ), datetime(2026, 6, 3, tzinfo=TZ))


def _count(db, table):
    with db._engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar()


def test_run_ingest_writes_and_stamps(tmp_path):
    db = Database(create_engine(f"sqlite:///{tmp_path / 'wh.sqlite'}"))
    client = FakeClient()
    try:
        summary = run_ingest(client, db, _settings(), _range(),
                             mode="manual", sources=["aarhus.dk"])
        # conversations: histogram -> 2 daily rows for the single channel/source.
        assert summary["conversations"] == 2
        # intents: frequency fetched per day (2 days) -> 2 rows.
        assert summary["intents"] == 2
        with db._engine.connect() as conn:
            channel, domain = conn.execute(select(
                schema.fact_conversations_daily.c.channel,
                schema.fact_conversations_daily.c.domain).limit(1)).one()
        assert channel == "chat"
        assert domain == "aarhus.dk"
        # The municipality filter was injected into the request.
        assert any(f.get("visited_url_text") == "aarhus.dk" for f in client.filters_seen)
        # Idempotent rerun.
        run_ingest(client, db, _settings(), _range(), mode="manual", sources=["aarhus.dk"])
        assert _count(db, schema.fact_conversations_daily) == 2
    finally:
        db.close()


def test_run_incremental_explicit_range_keeps_watermark_unset(tmp_path):
    db = Database(create_engine(f"sqlite:///{tmp_path / 'wh.sqlite'}"))
    try:
        # explicit range -> manual runs -> watermark must stay unset
        run_incremental(FakeClient(), db, _settings(), explicit_range=_range())
        assert db.watermark() is None
    finally:
        db.close()


def test_run_ingest_records_run(tmp_path):
    db = Database(create_engine(f"sqlite:///{tmp_path / 'wh.sqlite'}"))
    try:
        run_ingest(FakeClient(), db, _settings(), _range(), mode="nightly",
                   sources=["aarhus.dk"])
        with db._engine.connect() as conn:
            status = conn.execute(select(schema.meta_ingest_run.c.status)).scalars().all()
        assert status and all(s == "done" for s in status)
    finally:
        db.close()
