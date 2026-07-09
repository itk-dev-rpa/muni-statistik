"""This module contains the main process of the robot."""

import json

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

from robot_framework import credentials
from robot_framework.boost_client import BoostApiError, BoostAuthError, BoostClient
from robot_framework.database import make_database
from robot_framework.exceptions import BusinessError
from robot_framework.ingest import run_incremental
from robot_framework.settings import DateRange, Settings


def _explicit_range(orchestrator_connection: OrchestratorConnection,
                    settings: Settings) -> DateRange | None:
    """Parse an optional {"from": ..., "to": ...} range from process arguments.

    When supplied the robot ingests exactly that period (gap-fill) without moving
    the watermark; otherwise it runs the incremental catch-up from the watermark.
    """
    raw = getattr(orchestrator_connection, "process_arguments", None)
    if not raw:
        return None
    args = json.loads(raw)
    if not args.get("from") or not args.get("to"):
        return None
    return DateRange(settings.parse_day(args["from"]), settings.parse_day(args["to"]))


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Fetch the enabled KPIs from boost.ai and upsert them into the database."""
    orchestrator_connection.log_trace("Running process.")

    settings = Settings.from_config()
    creds = credentials.from_orchestrator(orchestrator_connection)
    client = BoostClient(settings, creds)
    database = make_database(settings, creds)

    try:
        summary = run_incremental(
            client, database, settings,
            explicit_range=_explicit_range(orchestrator_connection, settings),
            log=orchestrator_connection.log_info)
    except (BoostAuthError, BoostApiError) as error:
        # Auth/scope/whitelist errors are precondition failures -> stop, no retry.
        if isinstance(error, BoostApiError) and error.status_code not in (401, 403):
            raise
        raise BusinessError(str(error)) from error
    finally:
        database.close()

    orchestrator_connection.log_info(f"Ingest done: {summary}")
