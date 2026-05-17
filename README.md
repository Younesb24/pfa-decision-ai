# PFA Decision AI

> **AI-powered decision support for e-commerce marketplace operations.**
> PFA — *Outils IA pour l'aide à la décision en entreprise*. ENSAO MGSI 2026.

End-to-end system that turns the Olist Brazilian E-Commerce dataset into KPIs,
ML predictions, anomaly alerts, persona-tailored executive narratives, and an
audited human-in-the-loop review surface — all served behind a typed FastAPI +
Next.js stack.

---

## Demo

<!-- Replace this image with a real screenshot of the OTIF dashboard once the
     live URL is up. Loom link replaces YOUR-LOOM-ID after Day-17 recording. -->

![Dashboard hero — OTIF + alerts + briefing](docs/img/hero.png)

▶ **3-min walkthrough (OTIF crisis):**
<https://www.loom.com/share/YOUR-LOOM-ID>

🌐 **Live demo:** <https://YOUR-PUBLIC-URL> · sign in with `ops@pfa.local / ops123`

The Loom narrates the full OODA loop end-to-end: anomaly fires → LLM
explains it on top of pre-computed KPIs → operator acknowledges the alert →
decision lands in the audit journal. Script in [docs/demo_script.md](docs/demo_script.md).

---

## The seven surfaces

| # | Surface | What the user sees | Built from |
|---|---|---|---|
| 1 | **KPI summary** | OTIF, AOV, NPS proxy, cancel rate — persona-highlighted | `agg_daily_ops_kpi`, `agg_seller_scorecard` |
| 2 | **Daily timeseries + chart** | One chart per KPI, replay-clock aware | `fct_orders` × `dim_date` |
| 3 | **Anomaly alerts** | Z-score breaches on the daily series | `/insights/alerts` |
| 4 | **Persona-tailored narrative** | Claude Sonnet briefing on pre-computed KPIs | `/insights/narrative?persona=ops` |
| 5 | **Risky-seller drill-down** | Composite risk score + late-delivery prob | `agg_seller_scorecard`, XGBoost |
| 6 | **Data health + ingest** | Source registry, freshness, dbt test status | `/data-health`, `/ingest/*` |
| 7 | **Governance + audit** | Mark as Reviewed → audit log → decision journal | `governance.audit_log`, `governance.review_decisions` |

Every surface honors the non-negotiable rule: **the LLM is a narrator, never
a calculator.** Numbers come from `gold.*`; the LLM only writes English.

---

## Status

| Surface | Tech | Status |
|---|---|---|
| Data pipeline | PostgreSQL + dbt Core (medallion: bronze → silver → gold) | ✅ working, dbt tests defined inline in `_stg__models.yml` / `_marts__models.yml` / `sources.yml` |
| API | FastAPI, 12 endpoints | ✅ working |
| ML — late delivery | XGBoost classifier, ROC-AUC ≈ 0.82 ; F1 = 0.38 disclosed in [model card](docs/model_card.md) | ✅ trained, model in `ml/models/` |
| ML — forecast | Holt-Winters, sMAPE ≈ 13% / MAPE ≈ 14% (orders, floored) | ✅ trained — eval bug fixed, see [model card](docs/model_card.md#the-mape--259262-caveat) |
| Text-to-SQL | Anthropic Claude (preferred) / OpenAI GPT-4o (fallback) + semantic layer | ✅ working |
| Narrative generation | LLM + Self-Critique fact-check | ✅ working |
| Anomaly alerts | Z-score on daily KPIs | ✅ working |
| Audit journal | `governance.audit_log`, populated automatically | ✅ working |
| Human review | `governance.review_decisions` via `POST /governance/review` | ✅ working |
| Multi-persona | `?persona=ops|finance|supply` on KPI summary + narrative | ✅ working |
| Dashboard | Next.js 14 + Recharts | 🟡 single-page, see roadmap |
| CI | GitHub Actions: ruff + mypy + pytest + dbt parse + Next.js build | ✅ wired |

The numeric metrics (ROC-AUC, MAPE) reflect the most recent local training run.
Re-running `python ml/train_late_delivery.py` and `python ml/train_forecast.py`
regenerates them and updates the artifacts under `ml/models/`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Next.js Dashboard  (KPIs · charts · ask · narrative)   │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI                                                │
│   /kpi/*           — deterministic, persona-annotated   │
│   /ml/*            — XGBoost + Holt-Winters             │
│   /ask             — text → SQL (validated, audited)    │
│   /insights/*      — narrative + alerts + Self-Critique │
│   /governance/*    — audit log + Mark as Reviewed       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  PostgreSQL                                             │
│   bronze (raw) → silver (stg_*) → gold (dim/fct/agg)    │
│   governance.audit_log + governance.review_decisions    │
└─────────────────────────────────────────────────────────┘
```

The non-negotiable rules — *LLM is a narrator, never a calculator*; *only Gold
is exposed to the frontend or LLM* — are documented in
[CLAUDE.md](CLAUDE.md) and formalized in
[ADR-001](docs/adr/001-llm-as-narrator-not-calculator.md).

---

## Quick start

Prereqs: Python 3.11+, Node 20+, PostgreSQL 16, an Anthropic *or* OpenAI API key.

```bash
# 1. Database
psql -U postgres -c "CREATE DATABASE pfa_olist;"
psql -U postgres -c "CREATE USER pfa WITH PASSWORD 'pfa_local_2026';"
psql -U postgres -d pfa_olist -c "GRANT ALL ON DATABASE pfa_olist TO pfa;"

# 2. Bronze layer + dbt
python scripts/load_bronze.py
cd dbt_project && dbt run && dbt test && cd ..

# 3. Governance schema (audit log)
make audit-init

# 4. ML models
python ml/train_late_delivery.py
python ml/train_forecast.py

# 5. API
cd api
cp ../.env.example .env  # add ANTHROPIC_API_KEY (or OPENAI_API_KEY)
pip install -r requirements.txt
uvicorn main:app --port 8000

# 6. Dashboard
cd ../dashboard && npm install && npm run dev
```

Then open <http://localhost:3000> (dashboard) and
<http://localhost:8000/docs> (OpenAPI).

---

## API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/kpi/summary?persona=ops|finance|supply` | GET | Global KPIs + which ones to highlight for the persona |
| `/api/v1/kpi/daily` | GET | Daily KPI timeseries |
| `/api/v1/kpi/sellers` | GET | Top-N risky sellers (composite score) |
| `/api/v1/kpi/revenue-by-category` | GET | Revenue by product category |
| `/api/v1/ml/metrics` | GET | Model performance (read from training artifacts) |
| `/api/v1/ml/forecast` | GET | 3-month forecast |
| `/api/v1/ask` | POST/GET | NL → SQL → results, with hardened safety + audit |
| `/api/v1/insights/narrative?persona=…` | GET | LLM executive briefing + Self-Critique result |
| `/api/v1/insights/alerts` | GET | Z-score anomaly alerts on daily KPIs |
| `/api/v1/governance/audit` | GET | Recent audit-journal entries |
| `/api/v1/governance/review` | POST | Mark an alert / narrative as reviewed (OODA "Act") |

### `/ask` SQL safety

Every generated query is validated before execution. We reject:

- anything that doesn't start with `SELECT` or `WITH`
- references to `pg_catalog`, `pg_authid`, `pg_shadow`, `pg_user`, `pg_roles`,
  `pg_stat_*`, or `information_schema`
- multi-statement input (any `;` other than a trailing one)
- `COPY`, `GRANT`, `REVOKE` keywords

Tested in [api/tests/test_sql_safety.py](api/tests/test_sql_safety.py).

### Governance flow (OODA "Act")

1. Anomaly fires on `/insights/alerts`.
2. Operator reviews the narrative and the data context behind it.
3. Operator calls `POST /api/v1/governance/review` with
   `{subject_type: "alert", subject_ref: "otif_rate@2018-08-31", decision: "acknowledge"}`.
4. Decision lands in `governance.review_decisions`, linked back to the
   `audit_log` entry that produced the original LLM output.

---

## KPIs

| # | KPI | Source | Target |
|---|-----|--------|--------|
| 1 | OTIF Rate | `agg_daily_ops_kpi.otif_rate` | ≥ 92% |
| 2 | AOV | `agg_daily_ops_kpi.aov` | trend |
| 3 | NPS Proxy | `fct_reviews.nps_category` | > +50 |
| 4 | Cancellation Rate | `agg_daily_ops_kpi.cancellation_rate` | < 5% |
| 5 | Seller Risk Score | `agg_seller_scorecard.seller_risk_score` | alert > 60 |
| 6 | Revenue by Category | `fct_orders × dim_product` | top 15 |

Full definitions in [agent_docs/kpi_catalog.md](agent_docs/kpi_catalog.md).

---

## Architecture Decision Records

Why we chose what we chose, and what we ruled out:

- [ADR-001 — LLM as narrator, never calculator](docs/adr/001-llm-as-narrator-not-calculator.md)
- [ADR-002 — Medallion over a flat warehouse](docs/adr/002-medallion-over-flat-warehouse.md)
- [ADR-003 — No Kafka, no Spark, no Airflow, no LangChain](docs/adr/003-no-kafka-no-spark.md)
- [ADR-004 — Olist-only scope (cut DataCo + Budget vs Actual)](docs/adr/004-single-dataset-scope.md)
- [ADR-005 — Postgres as runtime store, DuckDB optional](docs/adr/005-postgres-not-duckdb-runtime.md)
- [ADR-006 — AWS as primary deploy, Render as kill-switch](docs/adr/006-aws-over-render.md)
- [ADR-007 — Dagster for orchestration](docs/adr/007-dagster-orchestration.md)
- [ADR-008 — Tool-based agent pattern](docs/adr/008-tool-based-agent-pattern.md)

---

## Development

```bash
make install-dev    # ruff, mypy, pytest, httpx
make lint           # ruff check
make type-check     # mypy --ignore-missing-imports
make test           # pytest, skipping integration + LLM tests
```

Tests are split by marker:

- **default** — pure-function (`test_sql_safety.py`, `test_personas.py`,
  `test_llm_client.py`) and FastAPI smoke (`test_app_smoke.py`). No DB, no LLM.
- **`integration`** — needs a live Postgres with the Gold schema loaded.
- **`llm`** — hits a real provider; never run in CI.

---

## Honest disclosure

See the [model card](docs/model_card.md) for full ML performance, training
scope, and disallowed uses. Headlines:

- **Late-delivery classifier**: ROC-AUC ≈ 0.82, but F1 = 0.38 at threshold 0.5.
  Class imbalance — we ship a probability gauge, not a hard label. The UI
  threshold is set to 0.30.
- **Forecast**: previous MAPE = 259 262% was an eval-window bug (division
  by near-zero warm-up days). Fixed; current run reports sMAPE ≈ 13%, MAE
  ≈ 22 orders/day, MAPE floored at the 1-order denominator. Tests in
  [ml/tests/test_forecast_metrics.py](ml/tests/test_forecast_metrics.py).
- **LLM**: every output is auditable via `governance.audit_log`. No raw
  Bronze rows ever reach the model.

---

## Roadmap

Tracked in `CLAUDE.md` § *Future Add-ons (post-MVP, after ship)*. Highlights:

- RAG over Olist Portuguese reviews
- PDF executive report (WeasyPrint)
- Component split + multi-page dashboard
- Email/Slack alert delivery
- Multi-tenant auth + SSO

---

## License

UMP ENSA OUJDA — PFA 2025/2026.
