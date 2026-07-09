"""Tests for credential resolution from the environment (offline)."""
# pylint: disable=missing-function-docstring

from robot_framework import credentials


def test_from_env_reads_boost_secrets(monkeypatch):
    monkeypatch.setenv("BOOST_CLIENT_ID", "id123")
    monkeypatch.setenv("BOOST_CLIENT_SECRET", "secret456")
    creds = credentials.from_env()
    assert creds.boost_client_id == "id123"
    assert creds.boost_client_secret == "secret456"
    # No SQL connection string locally -> SQLite fallback.
    assert creds.sql_connection_string is None


def test_from_env_missing_raises(monkeypatch):
    monkeypatch.delenv("BOOST_CLIENT_ID", raising=False)
    monkeypatch.delenv("BOOST_CLIENT_SECRET", raising=False)
    try:
        credentials.from_env()
    except RuntimeError as exc:
        assert "BOOST_CLIENT_ID" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing env vars")
