"""Core orchestration: fetch the enabled KPIs per channel and source, and write
them to the database inside one audited ingest run.

For each KPI we loop over channels (voice/chat via `is_voice`) and sources
(municipality domain via `visited_url_text`), stamping `channel` + `domain` on
every row. Histogram KPIs cover the whole range in one call; frequency and
token_usage KPIs are fetched per day.

Reused by both `process.py` (production) and `local_run.py` (local testing);
it receives a ready-made client and database.
"""

from __future__ import annotations

from typing import Callable

from robot_framework import kpis
from robot_framework.boost_client import BoostClient
from robot_framework.database import INCREMENTAL_MODE, Database
from robot_framework.schema import ALL_SOURCE, SOURCE_SEED
from robot_framework.settings import DateRange, Settings, chunk_ranges, iter_days

Logger = Callable[[str], None]


def _slicing_sources() -> list[str]:
    """Registrable domains to slice by, plus the unfiltered total."""
    return [domain for domain, _ in SOURCE_SEED] + [ALL_SOURCE]


def _stamp(rows: list[dict], **columns) -> list[dict]:
    """Add the given dimension columns to every row."""
    return [{**row, **columns} for row in rows]


def _fetch_kpi(client: BoostClient, kpi: kpis.Kpi, date_range: DateRange,
               filters: dict) -> list[tuple[DateRange, object]]:
    """Fetch a KPI, returning (period, raw_response) pairs.

    Histogram KPIs return a single pair covering the whole range; frequency and
    token_usage KPIs return one pair per day.
    """
    if kpi.kind == kpis.HISTOGRAM:
        return [(date_range,
                 client.histogram(kpi.stat, date_range, group_by="day", **filters))]
    results = []
    for day in iter_days(date_range):
        if kpi.kind == kpis.TOKEN_USAGE:
            raw = client.token_usage(day, **filters)
        else:
            raw = client.frequency(kpi.stat, day, limit=kpi.limit, **filters)
        results.append((day, raw))
    return results


def _rows_for(kpi: kpis.Kpi, period: DateRange, raw: object) -> list[dict]:
    """Normalize a raw response and ensure every row has a `date`."""
    rows = kpi.normalize(raw)
    if kpi.kind != kpis.HISTOGRAM:
        rows = _stamp(rows, date=period.iso_from[:10])
    return _drop_empty(kpi.table, rows)


def _drop_empty(table, rows: list[dict]) -> list[dict]:
    """Drop rows whose measures are all None.

    boost returns a histogram bucket with empty measures when a filter (e.g. a
    municipality domain on voice traffic) matches nothing; those carry no signal.
    """
    measures = [c.name for c in table.columns
                if not c.primary_key and c.name not in ("run_id", "loaded_at")]
    return [row for row in rows
            if any(row.get(m) is not None for m in measures)]


def run_ingest(client: BoostClient, database: Database, settings: Settings,
               date_range: DateRange, *, mode: str = "manual",
               kpi_names: list[str] | None = None,
               sources: list[str] | None = None,
               log: Logger = print) -> dict:
    """Run one audited ingest: fetch every KPI x channel x source and upsert."""
    names = kpi_names if kpi_names is not None else settings.enabled_kpis
    sources = sources if sources is not None else _slicing_sources()
    run_id = database.start_run(date_range, mode, settings.ingest_version)
    summary: dict[str, int] = {}
    total = 0
    try:
        for name in names:
            kpi = kpis.get_kpi(name)
            written = 0
            for channel_name, is_voice in settings.channels:
                for domain in sources:
                    filters = {"is_voice": is_voice}
                    if domain != ALL_SOURCE:
                        filters["visited_url_text"] = domain
                        filters["visited_url_criteria"] = "contains"
                    for period, raw in _fetch_kpi(client, kpi, date_range, filters):
                        database.write_raw(run_id, name, channel_name, domain,
                                           date_range=period, payload=raw)
                        rows = _stamp(_rows_for(kpi, period, raw),
                                      channel=channel_name, domain=domain)
                        written += database.upsert(kpi.table, rows, run_id)
            summary[name] = written
            total += written
            log(f"  {name}: {written} rows -> {kpi.table.name}")
        database.finish_run(run_id, "done", total)
    except Exception as error:
        database.finish_run(run_id, "failed", total, repr(error))
        raise
    return summary


def run_incremental(client: BoostClient, database: Database, settings: Settings,
                    *, explicit_range: DateRange | None = None,
                    kpi_names: list[str] | None = None,
                    log: Logger = print) -> dict:
    """Ingest in weekly chunks, resuming from the meta_ingest_run watermark.

    Default (no explicit_range): ingest from the watermark (or backfill start on
    a fresh database) up to today, as `incremental` runs that advance the
    watermark chunk by chunk. Pass explicit_range to (re)ingest a specific gap
    as `manual` runs, which do NOT move the watermark.
    """
    if explicit_range is not None:
        chunks = chunk_ranges(explicit_range, settings.chunk_days)
        mode = "manual"
    else:
        chunks = chunk_ranges(settings.incremental_range(database.watermark()),
                              settings.chunk_days)
        mode = INCREMENTAL_MODE

    if not chunks:
        log("Nothing to ingest (already up to date).")
        return {}

    summary: dict[str, int] = {}
    for chunk in chunks:
        log(f"Chunk {chunk} ({mode})")
        for name, written in run_ingest(client, database, settings, chunk,
                                        mode=mode, kpi_names=kpi_names,
                                        log=log).items():
            summary[name] = summary.get(name, 0) + written
    return summary
