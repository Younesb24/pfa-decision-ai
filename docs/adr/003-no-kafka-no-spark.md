# ADR 003 — No Kafka, no Spark, no Airflow, no LangChain

**Status:** Accepted
**Date:** 2026-04

## Context

A common failure mode for student data projects (and a common red flag in
interviews) is a stack that signals seniority by inclusion — Kafka because
"streaming," Spark because "big data," Airflow because "orchestration," LangChain
because "agents." None of those are justified by the workload here.

The workload:

- ~100K orders, ~112K order items, ~99K reviews. Total Olist footprint < 200MB.
- Batch ingestion, daily at most. No event sources.
- A linear DAG: Bronze → Silver → Gold → API → Dashboard.
- One LLM provider, two endpoints, no tool-use chains.

## Decision

We exclude:

| Tool | Why excluded |
|---|---|
| **Apache Kafka** | We have no event stream. All sources are CSV exports. Adding Kafka would mean publishing a single batch event per ingestion, which is `INSERT INTO bronze.* SELECT FROM csv` with extra steps. |
| **Apache Spark** | DuckDB on a single laptop processes Olist in seconds. Spark is a cluster product; we have no cluster, and at this scale we wouldn't fill one. |
| **Apache Airflow** | A Make target (`make dbt-run`) and a cron (later) cover scheduling. Airflow is 5 Docker services to gain a UI we don't need yet. |
| **MLflow** | Two models, versioned via Git and a `metrics.json` artifact. MLflow wins when teams retrain frequently and compare runs — we ship one classifier and one forecaster. |
| **LangChain / LlamaIndex** | The LLM call is a single completion with a system prompt. Direct SDK calls (`anthropic.messages.create` or `openai.chat.completions.create`) are clearer and have one less version to pin. |

## Consequences

- The CV and the report can name only what we used. We trade flashy keywords
  for defensibility under questioning.
- If the project ever hits scale where one of these *is* justified, it goes
  in as a new ADR with a measurable trigger (e.g. "ingestion exceeds N rows/sec
  → Kafka"), not because someone asked.

## Alternatives considered

- **"Include Kafka anyway, for the resume."** Rejected. An interviewer asking
  *"why Kafka here?"* would catch it inside 30 seconds. Better to defend a
  smaller, honest stack.
