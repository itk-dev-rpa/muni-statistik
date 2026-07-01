"""Core orchestration: fetch the selected KPIs and write them to a sink.

Reused by both `process.py` (production via OpenOrchestrator) and `local_run.py`
(local testing). It knows nothing about OpenOrchestrator or the credential
source — it receives a ready-made client and sink.
"""

from __future__ import annotations

from typing import Callable

from robot_framework import kpis
from robot_framework.boost_client import BoostClient
from robot_framework.settings import DateRange, Settings
from robot_framework.sinks import Sink

# Simple logger type: a function that takes a string.
Logger = Callable[[str], None]


def run_ingest(client: BoostClient, sink: Sink, settings: Settings,
               date_range: DateRange, *, kpi_names: list[str] | None = None,
               log: Logger = print) -> dict[str, int]:
    """Fetch each selected KPI for the range and upsert it into the sink.

    Returns a summary dict {kpi_name: row_count}.
    """
    names = kpi_names if kpi_names is not None else settings.enabled_kpis
    summary: dict[str, int] = {}

    for name in names:
        kpi = kpis.get_kpi(name)
        log(f"Fetching '{name}' for {date_range} ...")
        raw = kpi.fetch(client, date_range)
        sink.write_raw(name, date_range, raw)
        rows = kpi.normalize(raw)
        written = sink.upsert(kpi.table, rows, kpi.key_columns)
        summary[name] = written
        log(f"  {name}: {written} rows -> {kpi.table}")

    return summary
