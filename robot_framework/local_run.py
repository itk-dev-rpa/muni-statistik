"""Local test entry — run ingest without OpenOrchestrator.

Reads secrets from .env and writes to the configured sink (SQLite by default).
Used to test against boost.ai during development.

Examples:
    uv run python -m robot_framework.local_run
    uv run python -m robot_framework.local_run --from 2026-06-01 --to 2026-06-08
    uv run python -m robot_framework.local_run --kpi conversations
"""

from __future__ import annotations

import argparse
from datetime import datetime

from dotenv import load_dotenv

from robot_framework import credentials
from robot_framework.boost_client import BoostApiError, BoostAuthError, BoostClient
from robot_framework.ingest import run_ingest
from robot_framework.settings import DateRange, Settings
from robot_framework.sinks import make_sink


def _parse_date(value: str, settings: Settings) -> datetime:
    """Parse 'YYYY-MM-DD' or full ISO-8601 in the configured timezone."""
    if len(value) == 10:  # bare date -> midnight in Danish time
        naive = datetime.strptime(value, "%Y-%m-%d")
        return naive.replace(tzinfo=settings.tzinfo)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=settings.tzinfo)
    return parsed


def main() -> None:
    """Run ingest locally based on command-line arguments."""
    parser = argparse.ArgumentParser(description="Local ingest test (without Orchestrator).")
    parser.add_argument("--from", dest="from_date", help="Start date (incl.), e.g. 2026-06-01")
    parser.add_argument("--to", dest="to_date", help="End date (excl.), e.g. 2026-06-08")
    parser.add_argument("--kpi", action="append", dest="kpis",
                        help="KPI to fetch (repeatable). Default: from config.")
    args = parser.parse_args()

    load_dotenv()
    settings = Settings.from_config()
    creds = credentials.from_env()

    if args.from_date and args.to_date:
        date_range = DateRange(_parse_date(args.from_date, settings),
                               _parse_date(args.to_date, settings))
    else:
        date_range = settings.default_range()

    client = BoostClient(settings, creds)
    sink = make_sink(settings, creds)
    try:
        summary = run_ingest(client, sink, settings, date_range, kpi_names=args.kpis)
    except BoostAuthError as error:
        raise SystemExit(f"Auth error: {error}") from error
    except BoostApiError as error:
        if error.status_code == 403:
            raise SystemExit(
                "403 Forbidden from the API. Are you on an internal IP? boost.ai "
                "requires a whitelisted IP — VPN without internal access is blocked."
            ) from error
        raise SystemExit(f"API error {error.status_code}: {error.body[:200]}") from error
    finally:
        sink.close()

    print(f"\nDone. Summary: {summary}")


if __name__ == "__main__":
    main()
