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
# Name of the OpenOrchestrator constant holding the SQL Server connection string
# (a SQLAlchemy URL with trusted_connection). Kept in OO so the server/database can
# change without a code change. Local dev has no connection string and uses SQLite.
SQL_CONNECTION_STRING_CONSTANT = "Chat Statistics Connection String"


# Application config (boost.ai statistics)
# ----------------------------------------

BOOST_TENANT = "ddh"                 # -> https://ddh.boost.ai
BOOST_SCOPE = "analytics:v1"         # confirmed Statistics API v2 scope
TIMEZONE = "Europe/Copenhagen"       # Danish time for from_date/to_date
SQLITE_PATH = "local_data.sqlite"    # local sink when no connection string

# Muni launched February 2025; the first incremental run reaches back to here.
BACKFILL_START = "2025-02-01"

# Incremental ingest processes this many days per chunk (and per audited run),
# so a failure only re-does the current chunk on the next run.
CHUNK_DAYS = 7

# Bump when a normalizer changes so re-ingested rows are traceable.
INGEST_VERSION = 1

# Channels to split every datapoint by (name, is_voice filter value).
CHANNELS = [("chat", False), ("voice", True)]

# Datapoints to ingest. Names must exist in robot_framework.kpis.REGISTRY.
ENABLED_KPIS = [
    "conversations", "human_transfer", "sentiment", "conversation_feedback",
    "message_feedback", "conversation_insight", "token_usage",
    "goals_started", "goals_completed", "intents", "human_chat_skill",
]


# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = None

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
