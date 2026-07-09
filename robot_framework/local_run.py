"""Local test entry — run ingest without OpenOrchestrator.

Reads secrets from .env and writes to the local SQLite database. Used to test
against boost.ai during development.

Examples:
    uv run python -m robot_framework.local_run                       # incremental (from watermark)
    uv run python -m robot_framework.local_run --from 2026-06-01 --to 2026-06-08
    uv run python -m robot_framework.local_run --kpi conversations

Without --from/--to it runs the incremental catch-up (which backfills from
BACKFILL_START on an empty database — potentially long). Use --from/--to for a
short, explicit range while developing.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from robot_framework import credentials
from robot_framework.boost_client import BoostApiError, BoostAuthError, BoostClient
from robot_framework.database import make_database
from robot_framework.ingest import run_incremental
from robot_framework.settings import DateRange, Settings


def main() -> None:
    """Run ingest locally based on command-line arguments."""
    parser = argparse.ArgumentParser(description="Local ingest test (without Orchestrator).")
    parser.add_argument("--from", dest="from_date", help="Start date (incl.), e.g. 2026-06-01")
    parser.add_argument("--to", dest="to_date", help="End date (excl.), e.g. 2026-06-08")
    parser.add_argument("--kpi", action="append", dest="kpis",
                        help="KPI to fetch (repeatable). Default: all enabled.")
    args = parser.parse_args()

    load_dotenv()
    settings = Settings.from_config()
    creds = credentials.from_env()

    explicit_range = None
    if args.from_date and args.to_date:
        explicit_range = DateRange(settings.parse_day(args.from_date),
                                   settings.parse_day(args.to_date))

    client = BoostClient(settings, creds)
    database = make_database(settings, creds)
    try:
        summary = run_incremental(client, database, settings,
                                  explicit_range=explicit_range, kpi_names=args.kpis)
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
        database.close()

    print(f"\nDone. Summary: {summary}")


if __name__ == "__main__":
    main()
