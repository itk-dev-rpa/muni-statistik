"""KPI registry: maps each datapoint to a boost endpoint, a target table and a
normalizer.

Each KPI declares:
- `kind`: "histogram" (daily time series in one call), "frequency" or
  "token_usage" (no group_by -> fetched per day by the ingest loop).
- `stat`: the boost stat path segment (None for token_usage).
- `table`: the SQLAlchemy fact table it writes to.
- `normalize`: pure function turning the raw response into measure rows. For
  histogram KPIs each row carries its own `date`; for per-day KPIs the ingest
  loop stamps the date. The ingest loop also stamps channel, domain, run_id.

Normalizers are pure (no I/O) so they can be unit tested offline against
captured JSON from the spike.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from robot_framework import schema

HISTOGRAM = "histogram"
FREQUENCY = "frequency"
TOKEN_USAGE = "token_usage"


@dataclass(frozen=True)
class Kpi:
    """Definition of a single datapoint."""

    name: str
    kind: str
    stat: str | None
    table: Any  # sqlalchemy.Table
    normalize: Callable[[Any], list[dict]]
    limit: int | None = None  # frequency result cap (e.g. top-N intents)


def _histogram(response: dict, mapping: dict[str, str]) -> list[dict]:
    """Turn a histogram response into one row per day using {out: in} mapping."""
    rows = []
    for bucket in response.get("histogram", []):
        row = {"date": bucket["period"][:10]}
        for out_col, src_field in mapping.items():
            row[out_col] = bucket.get(src_field)
        rows.append(row)
    return rows


def _frequency_rows(response: dict) -> list[dict]:
    """Zip a frequency response's headers + values into dicts."""
    headers = response.get("headers", [])
    return [dict(zip(headers, values)) for values in response.get("values", [])]


def _identity(*fields: str) -> dict[str, str]:
    return {field: field for field in fields}


def normalize_token_usage(response: Any) -> list[dict]:
    """Flatten the token_usage list into per (vendor, feature, model) rows."""
    fields = ("vendor", "feature", "model", "prompt_tokens",
              "completion_tokens", "total_tokens", "counts")
    return [{field: item.get(field) for field in fields}
            for item in (response or [])]


def _goals(metric: str) -> Callable[[dict], list[dict]]:
    def normalize(response: dict) -> list[dict]:
        return [{"goal_id": row["id"], "goal_title": row["goal_title"],
                 "metric": metric, "count": row["count"]}
                for row in _frequency_rows(response)]
    return normalize


def normalize_intents(response: dict) -> list[dict]:
    """Map predicted_intent frequency rows to intent facts."""
    return [{"intent_id": row["id"], "intent_title": row["intent_title"],
             "count": row["count"]}
            for row in _frequency_rows(response)]


def normalize_skills(response: dict) -> list[dict]:
    """Map human_chat_skill frequency rows (skill name encodes municipality)."""
    return [{"skill_id": row["id"], "skill": row["skill"], "count": row["count"]}
            for row in _frequency_rows(response)]


REGISTRY: dict[str, Kpi] = {kpi.name: kpi for kpi in [
    Kpi("conversations", HISTOGRAM, "message",
        schema.fact_conversations_daily,
        lambda r: _histogram(r, _identity(
            "conversations", "billable_conversations", "messages",
            "messages_bot", "messages_customer", "messages_human_chat"))),
    Kpi("human_transfer", HISTOGRAM, "human_chat",
        schema.fact_human_transfer_daily,
        lambda r: _histogram(r, _identity("va_only", "unassisted", "assisted"))),
    Kpi("sentiment", HISTOGRAM, "sentiment",
        schema.fact_sentiment_daily,
        lambda r: _histogram(r, {"positive": "sentiment_positive",
                                 "neutral": "sentiment_neutral",
                                 "negative": "sentiment_negative"})),
    Kpi("conversation_feedback", HISTOGRAM, "conversation_feedback",
        schema.fact_conversation_feedback_daily,
        lambda r: _histogram(r, _identity(
            "no_feedback", "any_feedback", "thumbs_up", "thumbs_down",
            "thumbs_up_with_message", "thumbs_down_with_message",
            "thumbs_up_on_message", "thumbs_down_on_message"))),
    Kpi("message_feedback", HISTOGRAM, "message_feedback",
        schema.fact_message_feedback_daily,
        lambda r: _histogram(r, _identity("thumbs_up", "thumbs_down"))),
    Kpi("conversation_insight", HISTOGRAM, "conversation_review",
        schema.fact_conversation_insight_daily,
        lambda r: _histogram(r, _identity(
            "automated_informational_url", "automated_informational_in_chat",
            "automated_transactional", "escalated_by_design",
            "escalated_as_fallback", "escalated_immediate_request",
            "escalated_by_request", "unsolved", "not_relevant"))),
    Kpi("token_usage", TOKEN_USAGE, None,
        schema.fact_token_usage_daily, normalize_token_usage),
    Kpi("goals_started", FREQUENCY, "goals_started",
        schema.fact_goals_daily, _goals("started")),
    Kpi("goals_completed", FREQUENCY, "goals_completed",
        schema.fact_goals_daily, _goals("completed")),
    Kpi("intents", FREQUENCY, "predicted_intent",
        schema.fact_intents_daily, normalize_intents, limit=100),
    Kpi("human_chat_skill", FREQUENCY, "human_chat_skill",
        schema.fact_human_chat_skill_daily, normalize_skills, limit=200),
]}


def get_kpi(name: str) -> Kpi:
    """Look up a KPI in the registry; raises on unknown name."""
    try:
        return REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"Unknown KPI '{name}'. Known: {known}.") from exc
