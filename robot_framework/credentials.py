"""Handling of secrets (client_id/secret, DB login).

Two sources with the same output: `.env` locally (dev) and OpenOrchestrator in
production. Tenant/scope are non-secret and live in config.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from robot_framework import config


@dataclass(frozen=True)
class Credentials:
    """Runtime values resolved from the environment (secrets + DB connection).

    The SQL connection string uses a trusted connection, so it carries no
    password; it is grouped here because it is resolved per environment like
    the boost secrets (OpenOrchestrator in prod, .env locally).
    """

    boost_client_id: str
    boost_client_secret: str
    sql_connection_string: str | None = None


def from_env() -> Credentials:
    """Read values from the environment (.env is loaded by the caller).

    Used for local development/testing.
    """
    missing = [name for name in ("BOOST_CLIENT_ID", "BOOST_CLIENT_SECRET")
               if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing) +
            ". Copy .env.example to .env and fill it in.")

    # No SQL connection string locally -> make_database falls back to SQLite.
    return Credentials(
        boost_client_id=os.environ["BOOST_CLIENT_ID"],
        boost_client_secret=os.environ["BOOST_CLIENT_SECRET"],
    )


def from_orchestrator(orchestrator_connection) -> Credentials:
    """Read values from OpenOrchestrator (production)."""
    boost = orchestrator_connection.get_credential(config.BOOST_CREDENTIAL)
    # The connection string is optional until the DB constant is configured.
    try:
        conn = orchestrator_connection.get_constant(
            config.SQL_CONNECTION_STRING_CONSTANT).value
    except Exception:  # pylint: disable=broad-except
        conn = None

    return Credentials(
        boost_client_id=boost.username,
        boost_client_secret=boost.password,
        sql_connection_string=conn,
    )
