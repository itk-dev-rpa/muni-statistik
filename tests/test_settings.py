"""Tests for settings — Danish timezone and date ranges."""
# pylint: disable=missing-function-docstring

from robot_framework.settings import Settings


def _settings(backfill_days=0):
    return Settings(tenant="ddh", scope="analytics:v1",
                    timezone="Europe/Copenhagen", backfill_days=backfill_days)


def test_yesterday_range_is_one_day_half_open():
    settings = _settings()
    rng = settings.yesterday_range()
    assert (rng.to_dt - rng.from_dt).days == 1
    assert rng.from_dt.hour == 0 and rng.to_dt.hour == 0


def test_range_uses_danish_timezone():
    settings = _settings()
    # Danish time is +02:00 (summer) or +01:00 (winter) — never UTC/+00:00.
    offset = settings.yesterday_range().from_dt.utcoffset()
    assert offset.total_seconds() in (3600, 7200)


def test_backfill_range_spans_configured_days():
    settings = _settings(backfill_days=30)
    rng = settings.default_range()
    assert (rng.to_dt - rng.from_dt).days == 30


def test_from_config_reads_defaults():
    settings = Settings.from_config()
    assert settings.tenant == "ddh"
    assert settings.scope == "analytics:v1"
    assert "conversations" in settings.enabled_kpis
