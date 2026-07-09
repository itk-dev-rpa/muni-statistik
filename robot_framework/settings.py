"""Typed view over the configuration constants in config.py, plus date ranges.

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
    ingest_version: int
    backfill_start: str
    chunk_days: int = 7
    sqlite_path: str = "local_data.sqlite"
    enabled_kpis: list[str] = field(default_factory=list)
    channels: list[tuple[str, bool]] = field(default_factory=list)

    @classmethod
    def from_config(cls) -> "Settings":
        """Build a Settings object from the constants in config.py."""
        return cls(
            tenant=config.BOOST_TENANT,
            scope=config.BOOST_SCOPE,
            timezone=config.TIMEZONE,
            ingest_version=config.INGEST_VERSION,
            backfill_start=config.BACKFILL_START,
            chunk_days=config.CHUNK_DAYS,
            sqlite_path=config.SQLITE_PATH,
            enabled_kpis=list(config.ENABLED_KPIS),
            channels=list(config.CHANNELS),
        )

    def parse_day(self, value: str) -> datetime:
        """Parse an ISO date/datetime into an aware datetime in the config tz."""
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self.tzinfo)
        return parsed

    def incremental_range(self, watermark: str | None) -> DateRange:
        """Range to ingest: from the watermark (else backfill start) to today."""
        start = self.parse_day(watermark or self.backfill_start)
        return DateRange(start, self.midnight_today())

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
        """Range from backfill_start (config) until today 00:00."""
        start = datetime.strptime(self.backfill_start, "%Y-%m-%d").replace(
            tzinfo=self.tzinfo)
        return DateRange(start, self.midnight_today())

    def default_range(self) -> DateRange:
        """Nightly default range: yesterday."""
        return self.yesterday_range()


def iter_days(date_range: DateRange) -> list[DateRange]:
    """Split a range into one half-open [day, day+1) range per calendar day."""
    return chunk_ranges(date_range, 1)


def chunk_ranges(date_range: DateRange, chunk_days: int) -> list[DateRange]:
    """Split a range into consecutive half-open chunks of at most chunk_days."""
    chunks = []
    current = date_range.from_dt
    while current < date_range.to_dt:
        nxt = min(current + timedelta(days=chunk_days), date_range.to_dt)
        chunks.append(DateRange(current, nxt))
        current = nxt
    return chunks
