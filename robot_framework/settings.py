"""Typed view over the configuration in config.py, plus date ranges.

Non-secret configuration lives in `config.py`. Secrets are handled in
`credentials.py`. Date ranges are computed in the configured timezone (Danish
time by default), since boost.ai interprets dates in the tenant's timezone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from robot_framework import config


@dataclass(frozen=True)
class DateRange:
    """Half-open date range [from, to) with timezone, as boost expects."""

    from_dt: datetime
    to_dt: datetime

    @property
    def iso_from(self) -> str:
        """ISO-8601 with timezone, e.g. '2026-06-01T00:00:00+02:00'."""
        return self.from_dt.isoformat()

    @property
    def iso_to(self) -> str:
        """ISO-8601 with timezone."""
        return self.to_dt.isoformat()

    def __str__(self) -> str:
        return f"[{self.iso_from}, {self.iso_to})"


@dataclass(frozen=True)
class Settings:  # pylint: disable=too-many-instance-attributes
    """Typed view over the configuration constants in config.py."""

    tenant: str
    scope: str
    timezone: str
    backfill_days: int
    enabled_kpis: list[str] = field(default_factory=list)
    sink_type: str = "sqlite"
    sqlite_path: str = "local_data.sqlite"
    db_driver: str = ""
    db_server: str = ""
    db_database: str = ""

    @classmethod
    def from_config(cls) -> "Settings":
        """Build a Settings object from the constants in config.py."""
        return cls(
            tenant=config.BOOST_TENANT,
            scope=config.BOOST_SCOPE,
            timezone=config.TIMEZONE,
            backfill_days=config.BACKFILL_DAYS,
            enabled_kpis=list(config.ENABLED_KPIS),
            sink_type=config.SINK_TYPE,
            sqlite_path=config.SQLITE_PATH,
            db_driver=config.DB_DRIVER,
            db_server=config.DB_SERVER,
            db_database=config.DB_DATABASE,
        )

    @property
    def base_url(self) -> str:
        """Statistics API v2 base URL for the tenant."""
        return f"https://{self.tenant}.boost.ai/api/external/statistics/v2"

    @property
    def token_url(self) -> str:
        """OAuth2 token endpoint for the tenant."""
        return f"https://{self.tenant}.boost.ai/api/oauth2/v1/token"

    @property
    def tzinfo(self) -> ZoneInfo:
        """tzinfo object for the configured timezone."""
        return ZoneInfo(self.timezone)

    def midnight_today(self) -> datetime:
        """Midnight today in the configured timezone."""
        now = datetime.now(self.tzinfo)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def yesterday_range(self) -> DateRange:
        """Range for yesterday: [yesterday 00:00, today 00:00)."""
        today = self.midnight_today()
        return DateRange(today - timedelta(days=1), today)

    def backfill_range(self) -> DateRange:
        """Range from backfill_days ago until today 00:00."""
        today = self.midnight_today()
        return DateRange(today - timedelta(days=self.backfill_days), today)

    def default_range(self) -> DateRange:
        """Default range: backfill if backfill_days > 0, otherwise yesterday."""
        if self.backfill_days > 0:
            return self.backfill_range()
        return self.yesterday_range()
