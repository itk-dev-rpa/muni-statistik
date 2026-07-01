"""Tests for SqliteSink — including that upsert is idempotent (no duplicates)."""
# pylint: disable=missing-function-docstring

from robot_framework.settings import Settings
from robot_framework.sinks import SqliteSink

KEY = ("date",)
ROWS = [
    {"date": "2026-06-01", "conversations": 533, "messages": 3915},
    {"date": "2026-06-02", "conversations": 461, "messages": 3225},
]


def _row_count(sink: SqliteSink, table: str) -> int:
    cur = sink._conn.execute(f'SELECT COUNT(*) FROM "{table}"')  # pylint: disable=protected-access
    return cur.fetchone()[0]


def test_upsert_then_rerun_is_idempotent(tmp_path):
    sink = SqliteSink(str(tmp_path / "test.sqlite"))
    try:
        sink.upsert("fact_conversations_daily", ROWS, KEY)
        # Re-running the same range must not duplicate.
        sink.upsert("fact_conversations_daily", ROWS, KEY)
        assert _row_count(sink, "fact_conversations_daily") == 2
    finally:
        sink.close()


def test_upsert_updates_existing_row(tmp_path):
    sink = SqliteSink(str(tmp_path / "test.sqlite"))
    try:
        sink.upsert("fact_conversations_daily", ROWS, KEY)
        updated = [{"date": "2026-06-01", "conversations": 999, "messages": 4000}]
        sink.upsert("fact_conversations_daily", updated, KEY)
        cur = sink._conn.execute(  # pylint: disable=protected-access
            'SELECT conversations FROM "fact_conversations_daily" WHERE date = ?',
            ("2026-06-01",))
        assert cur.fetchone()[0] == 999
        assert _row_count(sink, "fact_conversations_daily") == 2
    finally:
        sink.close()


def test_write_raw_stored(tmp_path):
    sink = SqliteSink(str(tmp_path / "test.sqlite"))
    settings = Settings(tenant="ddh", scope="analytics:v1",
                        timezone="Europe/Copenhagen", backfill_days=0)
    date_range = settings.yesterday_range()
    try:
        sink.write_raw("conversations", date_range, {"label": "MESSAGE"})
        cur = sink._conn.execute("SELECT stat, payload_json FROM stg_raw_response")  # pylint: disable=protected-access
        stat, payload = cur.fetchone()
        assert stat == "conversations"
        assert "MESSAGE" in payload
    finally:
        sink.close()
