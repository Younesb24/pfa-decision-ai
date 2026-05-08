# ADR 002 — Medallion (Bronze/Silver/Gold) over a single flat warehouse

**Status:** Accepted
**Date:** 2026-04

## Context

The Olist source is 9 CSV files with referential integrity gaps (geolocation
dedup is a known issue, customer_id is per-order rather than per-customer, etc.).
The product surface needs both ad-hoc analytics and pre-computed daily KPIs.

## Decision

Three layers, materialized through dbt:

- **Bronze (`raw` schema, Postgres tables):** as-loaded CSVs, no transforms,
  ingestion metadata (`_loaded_at`, `_source_file`).
- **Silver (`staging` schema, dbt views):** type casting, null handling,
  deduplication, business-rule renames. One `stg_*` model per source.
- **Gold (`gold` schema, dbt tables):** star-schema dims (`dim_*`), facts
  (`fct_*`), and pre-aggregated marts (`agg_*`).

The frontend and the LLM only ever read Gold. Bronze is invisible outside
the warehouse process.

## Consequences

- **Trust boundary:** any number rendered to a user has been through Silver's
  validation and Gold's aggregation. We can write tests at each boundary.
- **Re-runnability:** Gold tables are full-refresh; debugging a metric means
  re-running one model, not the whole pipeline.
- **Storage cost:** ~3× the raw size in Postgres. Acceptable at this scale
  (Olist is < 200MB).
- **Onboarding cost:** new contributors must understand which layer to read
  from. The model documentation lives in `_marts__models.yml` and
  `_stg__models.yml`, not in code comments.

## Alternatives considered

- **Single flat schema in Postgres.** Faster to start; but the moment a column
  needs cleaning, you either mutate the source table (lose lineage) or add
  views that nobody trusts.
- **Two layers (raw + reporting).** Workable, but conflates "is this clean?"
  with "is this aggregated?". Medallion separates the two questions, which
  makes test failures point at the right layer.
