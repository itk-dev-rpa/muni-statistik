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
    """Secrets the robot needs."""

    boost_client_id: str
    boost_client_secret: str
    db_username: str | None = None
    db_password: str | None = None


def from_env() -> Credentials:
    """Read secrets from the environment (.env is loaded by the caller).

    Used for local development/testing.
    """
    missing = [name for name in ("BOOST_CLIENT_ID", "BOOST_CLIENT_SECRET")
               if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing) +
            ". Copy .env.example to .env and fill it in.")

    return Credentials(
        boost_client_id=os.environ["BOOST_CLIENT_ID"],
        boost_client_secret=os.environ["BOOST_CLIENT_SECRET"],
        db_username=os.environ.get("SQL_USERNAME"),
        db_password=os.environ.get("SQL_PASSWORD"),
    )


def from_orchestrator(orchestrator_connection) -> Credentials:
    """Read secrets from OpenOrchestrator credentials (production)."""
    boost = orchestrator_connection.get_credential(config.BOOST_CREDENTIAL)
    creds = Credentials(
        boost_client_id=boost.username,
        boost_client_secret=boost.password,
    )
    # The DB credential is optional until SQL Server is set up.
    try:
        sql = orchestrator_connection.get_credential(config.SQL_CREDENTIAL)
        creds = Credentials(
            boost_client_id=creds.boost_client_id,
            boost_client_secret=creds.boost_client_secret,
            db_username=sql.username,
            db_password=sql.password,
        )
    except Exception:  # pylint: disable=broad-except
        pass
    return creds
