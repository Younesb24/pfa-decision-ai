# Project structure

One-page map of the repo. Read this once before navigating the code; do not
edit anything tagged **DO NOT EDIT BEFORE SOUTENANCE** without a very good
reason.

```
pfa-decision-ai/
├── api/                       FastAPI backend
│   ├── main.py                Router wiring + CORS + lifespan
│   ├── db.py                  psycopg2 helpers + audit-log writer
│   ├── llm_client.py          Anthropic / OpenAI wrapper + TLS escape hatches
│   ├── routers/               One file per surface (kpi, ml, ask, insights, …)
│   ├── agents/                Tool-using Decision Analyst (structured brief)
│   ├── schemas/               Pydantic DTOs shared across routers
│   ├── services/              auth, dagster_client, dbt_artifacts_reader, profiler
│   ├── tests/                 pytest — sql safety, auth, profiler, smoke
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env                   POSTGRES_*, OPENAI_API_KEY, LLM_INSECURE_TLS (local)
│
├── dashboard/                 Next.js 16 (Turbopack) + shadcn/ui
│   ├── src/app/               Pages: /, /login, /data-health, /ingest
│   ├── src/components/        Dashboard widgets + UI primitives
│   ├── src/lib/               api client, types, auth, stores, formatters
│   └── package.json
│
├── dbt_project/               dbt Core medallion warehouse
│   ├── models/staging/        stg_* (1 row per source row, cleaned)
│   ├── models/marts/          fct_/dim_/agg_ (Gold layer, exposed to API)
│   └── dbt_project.yml
│
├── ml/                        Training scripts + trained model artifacts
│   ├── train_late_delivery.py XGBoost classifier (ROC-AUC 0.82)
│   ├── train_forecast.py      Holt-Winters (trained but not surfaced in demo)
│   └── models/                .joblib artifacts (gitignored)
│
├── scripts/                   Local utilities + SQL migrations
│   ├── load_bronze.py         Olist CSVs → bronze schema
│   ├── replay_simulator.py    Replays historical events as "live" ticks
│   ├── seed_users.py          Demo users with bcrypt-hashed passwords
│   ├── *.sql                  Schema/migration files — applied via Makefile
│   │                          (audit_log, users, governance_*, source_registry,
│   │                           replay_state, init-schemas, setup_local_postgres,
│   │                           grant_permissions)
│   └── requirements.txt
│
├── dagster_pipeline/          Orchestration (assets, schedules, sensors)
├── agent_docs/                Semantic layer reference docs
│   ├── kpi_catalog.md         Single source of truth for KPI definitions
│   ├── data_dictionary.md     Bronze/Silver/Gold column glossary
│   └── architecture.md
│
├── docs/                      Project documentation
│   ├── demo_defense.md        3-min demo script + 10 jury Q&A + numbers
│   ├── model_card.md          XGBoost late-delivery model card
│   ├── day16_deploy_runbook.md
│   ├── demo_script.md
│   ├── one_pager.md
│   ├── adr/                   Architecture Decision Records (001–008)
│   ├── blog/                  Long-form posts (currently 1)
│   ├── deck/                  Soutenance deck source
│   ├── img/                   Screenshots
│   └── archive/               Old planning/handoff docs preserved here
│       ├── handoff.md
│       ├── handoff_after_day20.md
│       ├── pfa_master_plan.md
│       ├── design-system/     Early UI design notes
│       └── research/          REPOS_INDEX.md — reference repositories
│
├── terraform/                 AWS infrastructure skeleton (ECS + RDS + ALB)
│
├── README.md                  Project overview + quick start
├── CLAUDE.md                  Project conventions (locked stack, code standards)
├── AGENTS.md                  Same content as CLAUDE.md (agentic-dev twin file)
├── PROJECT_STRUCTURE.md       This file
├── Makefile                   make up / dbt-run / replay-init / auth-init / …
├── docker-compose.yml         Local dev stack
├── docker-compose.prod.yml    Prod-parity stack (Day 14)
├── pyproject.toml             ruff + mypy config
├── .env.example               Template
└── .gitignore
```

## Folder ownership rules

| Folder | Edit freely | DO NOT EDIT BEFORE SOUTENANCE |
|---|---|---|
| `docs/` | ✅ Add/edit any docs except `demo_defense.md`, `model_card.md`, ADRs | `docs/adr/*.md`, `docs/demo_defense.md`, `docs/model_card.md` |
| `docs/archive/` | ✅ Archive only (no active reading) | Don't add new files here mid-work |
| `api/` | ✅ Small bugfixes | `auth.py`, `services/auth.py`, `routers/main.py` wiring, the prediction endpoint |
| `dashboard/src/app/page.tsx` | ⚠ Only via small, surgical edits | The 1023-line monolith — do not refactor |
| `dashboard/src/components/dashboard/seller-prediction-modal.tsx` | ⚠ Label-only edits | The dual-signal layout is final for the demo |
| `dbt_project/models/` | ❌ No edits | dbt regression risk; any edit needs `dbt test` to follow |
| `ml/train_*.py` | ❌ No edits | Models are trained; don't retrain mid-demo prep |
| `ml/models/*.joblib` | ❌ No edits | Used live by the prediction endpoint |
| `scripts/*.sql` | ❌ No edits | Migrations are applied — re-running could destroy data |
| `terraform/` | ❌ No edits | Not part of the demo |
| `agent_docs/` | ❌ No edits | Semantic layer locked for the LLM Ask Bar |

## Where the AI lives (for jury Q&A)

| Pillar | Code |
|---|---|
| XGBoost late-delivery prediction | [api/routers/ml.py](api/routers/ml.py) `/predict/late-delivery` + [ml/train_late_delivery.py](ml/train_late_delivery.py) + [dashboard/src/components/dashboard/seller-prediction-modal.tsx](dashboard/src/components/dashboard/seller-prediction-modal.tsx) |
| LLM Ask Bar (text-to-SQL) | [api/routers/ask.py](api/routers/ask.py) + [api/llm_client.py](api/llm_client.py) |
| LLM Executive Briefing + self-critique | [api/routers/insights.py](api/routers/insights.py) `/insights/narrative` |
| LLM Decision Analyst (tool-using) | [api/agents/decision_analyst.py](api/agents/decision_analyst.py) + [api/agents/tools.py](api/agents/tools.py) |

## What is intentionally NOT here

- No automated CI/CD beyond the existing `.github/workflows/` (read the file before claiming otherwise)
- No SHAP — heuristic explanation only (documented in the model card)
- No vector DB / RAG — the semantic layer fits in a system prompt
- No Kafka / Spark — see `docs/adr/003-no-kafka-no-spark.md`
- No sentiment analysis on Portuguese review text — quantitative signals only (see `docs/demo_defense.md` §6)
