# Architecture Decision Records

ADRs document the *why* behind structural choices, especially the ones that look
unusual or that we deliberately ruled out.

| # | Title | Status |
|---|---|---|
| [001](./001-llm-as-narrator-not-calculator.md) | LLM as narrator, never calculator | Accepted |
| [002](./002-medallion-over-flat-warehouse.md) | Medallion (Bronze/Silver/Gold) over a single flat warehouse | Accepted |
| [003](./003-no-kafka-no-spark.md) | No Kafka, no Spark, no Airflow | Accepted |
| [004](./004-single-dataset-scope.md) | Olist-only scope (cut DataCo + Budget vs Actual) | Accepted |
| [005](./005-postgres-not-duckdb-runtime.md) | Postgres as runtime store, DuckDB optional | Accepted |

## Format

Each ADR follows a minimal template:

- **Context** — what's the situation?
- **Decision** — what did we choose?
- **Consequences** — what does this enable, what does it cost?
- **Alternatives considered** — what we did *not* pick, and why.

ADRs are append-only. If a decision is reversed, write a new ADR that supersedes
the old one rather than editing history.
