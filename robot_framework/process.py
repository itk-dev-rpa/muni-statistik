"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

from robot_framework import credentials
from robot_framework.boost_client import BoostApiError, BoostAuthError, BoostClient
from robot_framework.exceptions import BusinessError
from robot_framework.ingest import run_ingest
from robot_framework.settings import Settings
from robot_framework.sinks import make_sink


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Fetch the selected KPIs from boost.ai and upsert them into the database."""
    orchestrator_connection.log_trace("Running process.")

    settings = Settings.from_config()
    creds = credentials.from_orchestrator(orchestrator_connection)
    client = BoostClient(settings, creds)
    sink = make_sink(settings, creds)

    date_range = settings.default_range()
    try:
        summary = run_ingest(client, sink, settings, date_range,
                             log=orchestrator_connection.log_info)
    except (BoostAuthError, BoostApiError) as error:
        # Auth/scope/whitelist errors are precondition failures -> stop, no retry.
        if isinstance(error, BoostApiError) and error.status_code not in (401, 403):
            raise
        raise BusinessError(str(error)) from error
    finally:
        sink.close()

    orchestrator_connection.log_info(f"Ingest done: {summary}")
