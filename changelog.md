# Changelog

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
