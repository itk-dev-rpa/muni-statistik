"""Tests for settings — Danish timezone, date ranges and day iteration."""
# pylint: disable=missing-function-docstring

from datetime import datetime
from zoneinfo import ZoneInfo

from robot_framework.settings import DateRange, Settings, iter_days


def _settings():
    return Settings(tenant="ddh", scope="analytics:v1", timezone="Europe/Copenhagen",
                    ingest_version=1, backfill_start="2025-02-01")


def test_yesterday_range_is_one_day_half_open():
    rng = _settings().yesterday_range()
    assert (rng.to_dt - rng.from_dt).days == 1
    assert rng.from_dt.hour == 0 and rng.to_dt.hour == 0


def test_range_uses_danish_timezone():
    offset = _settings().yesterday_range().from_dt.utcoffset()
    # Danish time is +02:00 (summer) or +01:00 (winter) — never UTC.
    assert offset.total_seconds() in (3600, 7200)


def test_backfill_range_starts_at_configured_date():
    rng = _settings().backfill_range()
    assert rng.from_dt.strftime("%Y-%m-%d") == "2025-02-01"


def test_iter_days_splits_into_single_days():
    tz = ZoneInfo("Europe/Copenhagen")
    rng = DateRange(datetime(2026, 6, 1, tzinfo=tz), datetime(2026, 6, 4, tzinfo=tz))
    days = iter_days(rng)
    assert len(days) == 3
    assert days[0].from_dt.strftime("%Y-%m-%d") == "2026-06-01"
    assert (days[0].to_dt - days[0].from_dt).days == 1
    assert days[-1].to_dt == rng.to_dt


def test_from_config_reads_defaults():
    settings = Settings.from_config()
    assert settings.tenant == "ddh"
    assert settings.scope == "analytics:v1"
    assert "conversations" in settings.enabled_kpis
    assert ("voice", True) in settings.channels
