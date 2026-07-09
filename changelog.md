# Changelog

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] - 2026-07-09

### Added
- Resumable incremental ingest (`run_incremental`): each nightly run processes
  from the watermark up to today in weekly chunks, so a failed/stopped run is
  caught up automatically on the next run. On a fresh database this also performs
  the initial backfill from `BACKFILL_START`.
- The watermark is **derived from `meta_ingest_run`** (max `to_date` of a `done`
  run with `mode='incremental'`) — no separate state table. Explicit gap-fill
  runs use `mode='manual'` and never move the watermark.
- `process()` accepts an optional `{"from": ..., "to": ...}` argument
  (OpenOrchestrator process arguments) to re-ingest a specific gap on demand.
- `CHUNK_DAYS` config (default 7) controls chunk size / resume granularity.

### Changed
- `local_run` runs the incremental catch-up by default; `--from/--to` ingests an
  explicit range (manual, does not move the watermark). Removed `--backfill`.

## [0.3.0] - 2026-07-08

### Added
- Full datapoint coverage: conversations/messages, human transfer, sentiment,
  conversation + message feedback, conversation insight (conversation_review),
  token usage, goals (started/completed) and intents.
- Two dimensions on every fact: **channel** (voice/chat via `is_voice`) and
  **source/municipality** (via `visited_url_text` + a `dim_source` lookup that
  keeps the domain and maps it to a municipality label).
- `human_chat_skill` KPI — carries the municipality for voice traffic (e.g.
  "Voice_Aarhus"), which has no source_url to slice on.
- `dim_source.is_total` flag marking the "(alle)" grand-total row so PowerBI can
  avoid double counting it against the per-municipality breakdown.
- Ingest drops histogram rows whose measures are all null (empty buckets boost
  returns when a filter matches nothing, e.g. voice per municipality).
- Relational warehouse (`schema.py`, SQLAlchemy): dimensions, fact tables, an
  audit table `meta_ingest_run` (ingest version, timestamps, status) and
  `stg_raw_response`. `database.py` runs the same code on SQLite (local) and SQL
  Server (prod), with idempotent delete-by-key + insert upserts.
- Backfill to `BACKFILL_START` (2025-02-01) via the incremental catch-up.

### Changed
- `kpis.py` registry now declares `kind`/`stat`/`table` per KPI; `ingest.py`
  loops KPI × channel × source, stamps dimensions + `run_id`, and runs per-day
  for frequency/token_usage (histogram covers the whole range in one call).
- Replaced the hand-rolled SQLite/SQL Server sinks with the SQLAlchemy `Database`.

## [0.2.0] - 2026-07-08

### Added
- `SqlServerSink` (MS SQL Server via SQLAlchemy) with idempotent upsert
  (delete-by-key + insert) and dynamic table creation.
- Connection string is read from the OpenOrchestrator constant
  "Chat Statistics Connection String" (referenced by name in `config.py`), so
  the server/database can change without a code change.

### Changed
- `make_sink` selects `SqlServerSink` when a connection string is available and
  falls back to `SqliteSink` (local dev) otherwise.
- `credentials.Credentials` now carries `sql_connection_string` instead of DB
  username/password (the connection uses a trusted connection).
- Config cleanup: replaced `DB_DRIVER`/`DB_SERVER`/`DB_DATABASE`/`SINK_TYPE`
  with the single OO connection-string constant name.
- Dependencies: added `SQLAlchemy` and `pyodbc`.

## [0.1.0] - 2026-07-01

### Added
- Discovery spike (`spike/probe_stats.py`) that probes the boost.ai Statistics
  API v2 and dumps JSON + a report. Confirmed scope `analytics:v1`.
- PDD (`PDD.md`) with KPI → endpoint mapping and a proposed data model.
- Testable robot skeleton (Linear framework):
  - `config.py` — all configuration (framework + app: tenant, scope, KPIs,
    backfill, sink/DB target) as Python constants.
  - `settings.py` — typed view over `config.py` (`Settings.from_config()`),
    Danish timezone, date ranges (yesterday / backfill).
  - `credentials.py` — secrets from `.env` (dev) or OpenOrchestrator (prod).
  - `boost_client.py` — OAuth2 client_credentials with token cache + endpoint wrappers.
  - `kpis.py` — KPI registry; first KPI: `conversations`.
  - `sinks.py` — `SqliteSink` (local test, idempotent upsert) + `SqlServerSink` stub.
  - `ingest.py` — core orchestration, reused by process and local_run.
  - `local_run.py` — local test entry without OpenOrchestrator.
- Unit tests for normalizers, sink idempotency and date ranges (run offline).

### Changed
- `__main__.py` now uses `linear_framework`.
- `process.py`/`initialize.py` fetch KPIs and validate preconditions.
- Dependencies: added `requests`, `python-dotenv`, `tzdata` (+ `pytest` in dev).
