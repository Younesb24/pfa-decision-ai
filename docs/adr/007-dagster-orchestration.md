# ADR 007 — Dagster as the orchestration layer

**Status:** Accepted
**Date:** 2026-05-11

## Context

v2 had no continuous data flow. `scripts/load_bronze.py` ran once from CSV;
the dashboard read whatever was in Gold the day the loader fired. That broke
the Observe leg of the OODA loop the product is built around — the system
could not show "new" anomalies because nothing new ever arrived.

v3 needs:

1. A periodic tick (15 min) that advances the data, runs dbt, and refreshes
   ML scores + briefings.
2. Source freshness signals exposed to the dashboard's Data Health page
   (Day 9) so the operator can tell when the pipeline has stalled.
3. A sensor that walks open governance decisions older than 7 synthetic-days
   and writes their realised outcome (Day 4).
4. A failure-isolation story — one bad dbt test should not silently corrupt
   the briefing cache.

That is orchestration. The question is which orchestrator.

## Decision

We adopt **Dagster Core** (OSS, self-hosted), running locally on
`localhost:3001` for the demo and inside an ECS Fargate task on AWS for the
deployed environment (Day 15–16).

Dagster, not Airflow or Prefect, for these reasons specific to this project:

| Need | Dagster behaviour |
|---|---|
| Asset graph mirrors the Bronze→Silver→Gold→ML→Briefing pipeline 1:1 | Dagster's **software-defined assets** are the native abstraction; Airflow models tasks, not data products. The metadata we want to surface (rows ingested, dbt tests passed, synthetic clock) lives naturally on `MaterializeResult`. |
| dbt integration without writing a custom operator | `dagster-dbt` turns each dbt model into its own asset (Day 3+). Airflow has `airflow-dbt-python` but it's a community package; Prefect's dbt block exists but is paid in Cloud. |
| Source freshness alerts → dashboard | Dagster's freshness policies + sensors map directly to `governance.alerts` rows. Airflow has no first-class freshness concept; you'd write a custom DAG that mostly mirrors the asset graph it already orchestrates. |
| Run from a single `dagster dev` for local development | Single command, web UI on port 3001. Airflow's local stack is 5 containers (webserver, scheduler, worker, redis, postgres). |
| Cost on AWS | One Fargate task at ~$10/month. Airflow on MWAA starts at $0.49/h (≈$360/mo) — incompatible with the free-tier story. |

This is consistent with ADR-003's reasoning ("no Airflow because we have no
cluster and a single linear DAG"). Dagster's value is not orchestrating
many DAGs; it's making one DAG's assets first-class citizens with
visible freshness and lineage. That's the demo asset for a decision-
intelligence cockpit.

## Consequences

- **New dependency.** `dagster>=1.9` plus `dagster-webserver` in
  `dagster_pipeline/requirements.txt`. This is the second net-new
  dependency v3 introduces (the first was zustand). Per `EXECUTION_HANDOFF`
  §0.4 it was already pre-approved in the build queue.
- **Two Python entry points.** The FastAPI app still runs from `api/`;
  Dagster runs from `dagster_pipeline/`. We keep them separate so the API
  doesn't accidentally import the orchestrator at module load. Shared code
  (e.g. eventually `api/services/dagster_client.py` on Day 9) talks to
  Dagster over its GraphQL API, not via Python imports.
- **Deployable as one process or two.** On AWS (Day 14–16) `dagster-svc`
  is a separate ECS service from `fastapi-svc`. Locally we use one
  `dagster dev` invocation; production splits it.
- **Subprocess pattern for Day 2.** Assets shell out to existing scripts
  (`scripts/replay_simulator.py`, `dbt`) rather than re-implementing
  logic. Day 3 will migrate dbt to `dagster-dbt` for per-model asset
  granularity, but the simulator stays a subprocess — it's already
  idempotent and testable standalone.

## Alternatives considered

- **Apache Airflow.** Heavyweight for one DAG; per-model dbt assets need
  a third-party operator; freshness has to be coded ourselves. ADR-003
  already excludes it from the v2 stack.
- **Prefect 2.x.** Single-process is fine and its UI is pleasant, but its
  asset model is bolted on after the fact ("Artifacts"), not the core
  primitive. The compelling features (workers, deployments) sit behind
  Prefect Cloud and add a hosted-SaaS dependency we don't want before
  shipping.
- **Plain cron + a shell wrapper.** Considered and rejected. We could in
  principle express the entire Day 2 graph in a cron entry, but it
  wouldn't surface dbt-test failures, source freshness, retry policy, or
  a per-run UI — all of which the OODA demo turns into a soutenance asset.
  Cron is what we'd use if we never had to *show* the pipeline running.
- **`make` targets behind `watch`.** Same drawback as cron, plus no
  per-run history.

## Trigger to revisit

If by post-soutenance the team is more than 1 person and there are more
than 5 DAGs, re-evaluate Airflow vs. Prefect Cloud. Until then, Dagster's
single-DAG-with-rich-assets shape is exactly the win we want.
