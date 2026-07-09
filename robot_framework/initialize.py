"""This module defines any initial processes to run when the robot starts."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework import credentials
from robot_framework.settings import Settings


def initialize(orchestrator_connection: OrchestratorConnection) -> None:
    """Validate preconditions: configuration can be read and credentials exist."""
    orchestrator_connection.log_trace("Initializing.")

    settings = Settings.from_config()
    creds = credentials.from_orchestrator(orchestrator_connection)
    sink = "SQL Server" if creds.sql_connection_string else "SQLite (local)"
    orchestrator_connection.log_info(
        f"Configuration OK. Tenant '{settings.tenant}', "
        f"KPIs: {settings.enabled_kpis}, sink: {sink}.")
