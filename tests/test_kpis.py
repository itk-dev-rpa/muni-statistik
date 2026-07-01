"""Unit tests for KPI normalizers. Run offline against a captured JSON shape."""
# pylint: disable=missing-function-docstring

from robot_framework import kpis

# Excerpt of a real histogram/message response (group_by=day) from the spike.
SAMPLE_MESSAGE_HISTOGRAM = {
    "label": "MESSAGE",
    "histogram": [
        {
            "period": "2026-06-01T00:00:00+02:00",
            "conversations": 533,
            "billable_conversations": 477,
            "messages": 3915,
            "messages_bot": 2593,
            "messages_customer": 1322,
            "messages_human_chat": 121,
        },
        {
            "period": "2026-06-02T00:00:00+02:00",
            "conversations": 461,
            "billable_conversations": 414,
            "messages": 3225,
            "messages_bot": 2136,
            "messages_customer": 1089,
            "messages_human_chat": 115,
        },
    ],
}


def test_normalize_conversations_row_per_day():
    rows = kpis.normalize_conversations(SAMPLE_MESSAGE_HISTOGRAM)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-06-01"
    assert rows[0]["conversations"] == 533
    assert rows[1]["date"] == "2026-06-02"
    assert rows[1]["messages"] == 3225


def test_normalize_conversations_empty():
    assert not kpis.normalize_conversations({"label": "MESSAGE", "histogram": []})


def test_get_kpi_unknown_raises():
    try:
        kpis.get_kpi("unknown")
    except KeyError as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("Expected KeyError for unknown KPI")
