"""Relational schema (SQLAlchemy Core) for the statistics warehouse.

One MetaData drives both the local SQLite database and production SQL Server.
Dimensions are seeded; facts share the grain date x channel x source and carry
audit metadata (run_id, loaded_at). Frequency/aggregate facts add their own
sub-dimension (goal, intent, model) to the key.
"""

from __future__ import annotations

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey,
                        Integer, MetaData, String, Table, select)

metadata = MetaData()

# Sentinel source used for the unfiltered "grand total" pass.
ALL_SOURCE = "(alle)"

# Registrable domain -> municipality label. Extend freely; unknown domains are
# stored with the domain as their own label (nothing is lost).
SOURCE_SEED: list[tuple[str, str]] = [
    ("aarhus.dk", "Aarhus"),
    ("holbaek.dk", "Holbæk"),
    ("hjoerring.dk", "Hjørring"),
    ("viborg.dk", "Viborg"),
    ("norddjurs.dk", "Norddjurs"),
    ("horsens.dk", "Horsens"),
    ("vesthimmerland.dk", "Vesthimmerland"),
    ("fredensborg.dk", "Fredensborg"),
    ("jammerbugt.dk", "Jammerbugt"),
    ("favrskov.dk", "Favrskov"),
    ("furesoe.dk", "Furesø"),
    ("syddjurs.dk", "Syddjurs"),
    ("odder.dk", "Odder"),
    ("skanderborg.dk", "Skanderborg"),
    ("randers.dk", "Randers"),
    ("dendigitalehotline.dk", "DDH-portal"),
]

CHANNEL_SEED = ["chat", "voice"]


def registrable_domain(host: str) -> str:
    """Reduce a URL host to its registrable domain (last two labels).

    Strips scheme/path/port and a leading 'www.' so subdomains collapse, e.g.
    'https://muni.favrskov.dk/x' -> 'favrskov.dk', 'www.aarhus.dk' -> 'aarhus.dk'.
    """
    host = host.strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0].split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    return ".".join(labels[-2:])


# --- Dimensions ----------------------------------------------------------

dim_channel = Table(
    "dim_channel", metadata,
    Column("channel", String(16), primary_key=True),
)

dim_source = Table(
    "dim_source", metadata,
    Column("domain", String(255), primary_key=True),
    Column("municipality", String(255), nullable=False),
    # True for the "(alle)" grand-total row; PowerBI must not sum it with the
    # per-municipality rows (that would double count).
    Column("is_total", Boolean, nullable=False, default=False),
)

# --- Audit ---------------------------------------------------------------

meta_ingest_run = Table(
    "meta_ingest_run", metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
    Column("from_date", String(32), nullable=False),
    Column("to_date", String(32), nullable=False),
    Column("mode", String(16), nullable=False),
    Column("ingest_version", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("rows_written", Integer, default=0),
    Column("error", String(4000)),
)

stg_raw_response = Table(
    "stg_raw_response", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("meta_ingest_run.run_id")),
    Column("kpi", String(64)),
    Column("channel", String(16)),
    Column("domain", String(255)),
    Column("from_date", String(32)),
    Column("to_date", String(32)),
    Column("fetched_at", DateTime),
    Column("payload_json", String),
)


def _fact(name: str, *measure_columns: Column, extra_key: list[Column] | None = None) -> Table:
    """Define a fact table with the shared grain, keys and audit columns."""
    extra_key = extra_key or []
    return Table(
        name, metadata,
        Column("date", String(10), primary_key=True),
        Column("channel", String(16), ForeignKey("dim_channel.channel"),
               primary_key=True),
        Column("domain", String(255), ForeignKey("dim_source.domain"),
               primary_key=True),
        *[Column(c.name, c.type, primary_key=True) for c in extra_key],
        *measure_columns,
        Column("run_id", Integer, ForeignKey("meta_ingest_run.run_id")),
        Column("loaded_at", DateTime),
    )


def _m(name: str) -> Column:
    """A measure column (nullable big integer)."""
    return Column(name, BigInteger)


fact_conversations_daily = _fact(
    "fact_conversations_daily",
    _m("conversations"), _m("billable_conversations"), _m("messages"),
    _m("messages_bot"), _m("messages_customer"), _m("messages_human_chat"))

fact_human_transfer_daily = _fact(
    "fact_human_transfer_daily",
    _m("va_only"), _m("unassisted"), _m("assisted"))

fact_sentiment_daily = _fact(
    "fact_sentiment_daily",
    _m("positive"), _m("neutral"), _m("negative"))

fact_conversation_feedback_daily = _fact(
    "fact_conversation_feedback_daily",
    _m("no_feedback"), _m("any_feedback"), _m("thumbs_up"), _m("thumbs_down"),
    _m("thumbs_up_with_message"), _m("thumbs_down_with_message"),
    _m("thumbs_up_on_message"), _m("thumbs_down_on_message"))

fact_message_feedback_daily = _fact(
    "fact_message_feedback_daily",
    _m("thumbs_up"), _m("thumbs_down"))

fact_conversation_insight_daily = _fact(
    "fact_conversation_insight_daily",
    _m("automated_informational_url"), _m("automated_informational_in_chat"),
    _m("automated_transactional"), _m("escalated_by_design"),
    _m("escalated_as_fallback"), _m("escalated_immediate_request"),
    _m("escalated_by_request"), _m("unsolved"), _m("not_relevant"))

fact_token_usage_daily = _fact(
    "fact_token_usage_daily",
    _m("prompt_tokens"), _m("completion_tokens"), _m("total_tokens"), _m("counts"),
    extra_key=[Column("vendor", String(128)), Column("feature", String(128)),
               Column("model", String(255))])

fact_goals_daily = _fact(
    "fact_goals_daily",
    Column("goal_title", String(512)), _m("count"),
    extra_key=[Column("goal_id", Integer), Column("metric", String(16))])

fact_intents_daily = _fact(
    "fact_intents_daily",
    Column("intent_title", String(512)), _m("count"),
    extra_key=[Column("intent_id", Integer)])

# Human-chat skills encode the municipality for voice (e.g. "Voice_Aarhus"),
# which cannot be derived from source_url for phone traffic.
fact_human_chat_skill_daily = _fact(
    "fact_human_chat_skill_daily",
    Column("skill", String(255)), _m("count"),
    extra_key=[Column("skill_id", Integer)])


def ensure_schema(engine) -> None:
    """Create all tables that do not yet exist."""
    metadata.create_all(engine)


def seed(engine) -> None:
    """Insert seed dimension rows if they are missing (idempotent)."""
    with engine.begin() as conn:
        existing = set(conn.execute(select(dim_channel.c.channel)).scalars())
        rows = [{"channel": name} for name in CHANNEL_SEED if name not in existing]
        if rows:
            conn.execute(dim_channel.insert(), rows)

        seen = set(conn.execute(select(dim_source.c.domain)).scalars())
        wanted = [(d, m, False) for d, m in SOURCE_SEED]
        wanted.append((ALL_SOURCE, ALL_SOURCE, True))
        rows = [{"domain": d, "municipality": m, "is_total": is_total}
                for d, m, is_total in wanted if d not in seen]
        if rows:
            conn.execute(dim_source.insert(), rows)
