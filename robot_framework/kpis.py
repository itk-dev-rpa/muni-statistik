"""KPI registry: maps each KPI to a boost endpoint and a normalizer.

A KPI consists of:
- `fetch`: retrieves the raw JSON response from boost for a date range.
- `normalize`: pure function translating the response into rows ready for upsert.
- `table` + `key_columns`: target table and key for idempotent upsert.

Normalizers are kept pure (no I/O) so they can be unit tested offline against
captured JSON from the spike.

Start: only "conversations". Extend the registry over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from robot_framework.boost_client import BoostClient
from robot_framework.settings import DateRange

# Fields we lift out of the message histogram into the fact table.
_CONVERSATION_FIELDS = (
    "conversations", "billable_conversations", "messages",
    "messages_bot", "messages_customer", "messages_human_chat",
)


@dataclass(frozen=True)
class Kpi:
    """Definition of a single KPI."""

    name: str
    table: str
    key_columns: tuple[str, ...]
    fetch: Callable[[BoostClient, DateRange], Any]
    normalize: Callable[[Any], list[dict]]


def normalize_conversations(response: dict) -> list[dict]:
    """Translate histogram/message (group_by=day) into one row per day.

    Expected shape: {"label": ..., "histogram": [{"period": ..., ...}, ...]}.
    """
    rows = []
    for bucket in response.get("histogram", []):
        # period is e.g. '2026-06-01T00:00:00+02:00' -> use the date part as key.
        row = {"date": bucket["period"][:10]}
        for name in _CONVERSATION_FIELDS:
            row[name] = bucket.get(name)
        rows.append(row)
    return rows


CONVERSATIONS = Kpi(
    name="conversations",
    table="fact_conversations_daily",
    key_columns=("date",),
    fetch=lambda client, date_range: client.histogram(
        "message", date_range, group_by="day"),
    normalize=normalize_conversations,
)

REGISTRY: dict[str, Kpi] = {
    CONVERSATIONS.name: CONVERSATIONS,
}


def get_kpi(name: str) -> Kpi:
    """Look up a KPI in the registry; raises on unknown name."""
    try:
        return REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"Unknown KPI '{name}'. Known: {known}.") from exc
