"""Unit tests for KPI normalizers. Run offline against captured JSON shapes."""
# pylint: disable=missing-function-docstring

from robot_framework import kpis

SAMPLE_MESSAGE_HISTOGRAM = {
    "label": "MESSAGE",
    "histogram": [
        {"period": "2026-06-01T00:00:00+02:00", "conversations": 533,
         "billable_conversations": 477, "messages": 3915, "messages_bot": 2593,
         "messages_customer": 1322, "messages_human_chat": 121},
        {"period": "2026-06-02T00:00:00+02:00", "conversations": 461,
         "billable_conversations": 414, "messages": 3225, "messages_bot": 2136,
         "messages_customer": 1089, "messages_human_chat": 115},
    ],
}

SAMPLE_INTENTS = {"label": "PREDICTED_INTENT", "headers": ["id", "intent_title", "count"],
                  "values": [[2177, "Kontaktoplysninger", 63], [1621, "Få sygedagpenge", 35]]}

SAMPLE_GOALS = {"label": "GOALS_STARTED", "headers": ["id", "goal_title", "value", "count"],
                "values": [[5, "Tidsbestilling voice", "1.00", 313]]}

SAMPLE_TOKEN_USAGE = [
    {"vendor": "openai_azure_boost", "feature": "generative_action",
     "model": "gpt-4.1", "prompt_tokens": 6272555, "completion_tokens": 12626,
     "total_tokens": 6285181, "counts": 500},
]


def test_conversations_row_per_day():
    rows = kpis.get_kpi("conversations").normalize(SAMPLE_MESSAGE_HISTOGRAM)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-06-01"
    assert rows[0]["conversations"] == 533
    assert rows[1]["messages"] == 3225


def test_intents_normalizer():
    rows = kpis.get_kpi("intents").normalize(SAMPLE_INTENTS)
    assert rows[0] == {"intent_id": 2177, "intent_title": "Kontaktoplysninger", "count": 63}


def test_goals_started_has_metric():
    rows = kpis.get_kpi("goals_started").normalize(SAMPLE_GOALS)
    assert rows[0]["metric"] == "started"
    assert rows[0]["goal_id"] == 5
    assert rows[0]["count"] == 313


def test_token_usage_normalizer():
    rows = kpis.get_kpi("token_usage").normalize(SAMPLE_TOKEN_USAGE)
    assert rows[0]["model"] == "gpt-4.1"
    assert rows[0]["total_tokens"] == 6285181


def test_human_chat_skill_normalizer():
    response = {"headers": ["id", "skill", "count"],
                "values": [[3, "Voice_Aarhus", 163], [15, "Voice_Hjørring", 35]]}
    rows = kpis.get_kpi("human_chat_skill").normalize(response)
    assert rows[0] == {"skill_id": 3, "skill": "Voice_Aarhus", "count": 163}


def test_get_kpi_unknown_raises():
    try:
        kpis.get_kpi("unknown")
    except KeyError as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("Expected KeyError for unknown KPI")
