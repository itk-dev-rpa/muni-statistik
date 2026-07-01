"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.adm.aarhuskommune.dk"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"

# boost.ai OAuth2 client: username = client_id, password = client_secret.
BOOST_CREDENTIAL = "Muni Boost API"
# SQL Server login (username/password). Added in Orchestrator once the DB is ready.
SQL_CREDENTIAL = "Muni Statistik DB"


# Application config (boost.ai statistics)
# ----------------------------------------

BOOST_TENANT = "ddh"                 # -> https://ddh.boost.ai
BOOST_SCOPE = "analytics:v1"         # confirmed Statistics API v2 scope
TIMEZONE = "Europe/Copenhagen"       # Danish time for from_date/to_date
BACKFILL_DAYS = 0                    # TODO: first-run history, e.g. 365
ENABLED_KPIS = ["conversations"]
SINK_TYPE = "sqlite"                 # "sqlite" (local test) | "sqlserver" (prod)
SQLITE_PATH = "local_data.sqlite"
# SQL Server (production) — TODO: fill in
DB_DRIVER = ""
DB_SERVER = ""
DB_DATABASE = ""


# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = None

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
