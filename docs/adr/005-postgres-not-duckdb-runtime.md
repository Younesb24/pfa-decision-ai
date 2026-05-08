# ADR 005 — Postgres as runtime store, DuckDB optional

**Status:** Accepted
**Date:** 2026-04

## Context

CLAUDE.md lists both Postgres and DuckDB. Two questions had to be answered:

1. Where does the API read from at runtime?
2. Where does dbt materialize Gold tables?

DuckDB is genuinely faster on analytical aggregations (10–1000× on large
groupbys), but it is single-process: every API worker holds its own connection
to the file, which makes write-conflict handling and concurrent reads
non-trivial in production.

## Decision

- **Bronze + Silver + Gold all live in Postgres** at runtime. The API
  (`api/db.py`) reads only from `gold.*`.
- **DuckDB is an optional analyst-mode tool** for ad-hoc exploration of the
  Olist files outside the pipeline (notebooks, ML feature engineering during
  training). Not on the request path.

## Consequences

- One connection model, one auth model, one backup story.
- We give up DuckDB's analytical speed, which we don't need at this scale —
  Olist Gold tables fit in Postgres shared buffers and aggregations return in
  milliseconds.
- The API stays trivially horizontally scalable (n stateless workers, one
  Postgres pool).

## Alternatives considered

- **DuckDB as the API's read store.** Tested mentally; concurrent writes
  during ingestion would block reads, and the lock semantics are different
  from Postgres in ways that would surprise users.
- **Postgres for OLTP-shape data, DuckDB for the Gold marts.** Two systems to
  keep in sync, two query dialects in the codebase. Cost outweighed benefit
  at our row counts.
