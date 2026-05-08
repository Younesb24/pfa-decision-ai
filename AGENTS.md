# PFA — Outil IA pour l'Aide à la Décision en Entreprise

## Context
- PFA MGSI ENSAO 2026 — AI-powered decision support for e-commerce marketplace operations
- Dataset: Olist Brazilian E-Commerce (8 relational CSV tables, ~100K orders)
- Solo student project, 4-month timeline, must ship a working MVP

## Persona
- Responsable Opérations E-Commerce (Head of E-commerce Ops)
- Needs: weekly operational briefing, KPI monitoring, anomaly alerts, delivery risk management

## Stack (LOCKED — do not suggest alternatives)
- Storage: PostgreSQL 16 (Docker)
- Analytics: DuckDB (in-process OLAP)
- Transform: dbt Core (staging → intermediate → marts)
- Backend: FastAPI + Pydantic v2 + SQLAlchemy
- Frontend: Next.js 14 App Router + Shadcn/UI + Recharts + TypeScript strict
- LLM: Anthropic API (Codex Sonnet) — text-to-SQL + narrative generation
- ML: scikit-learn + XGBoost (classification) + Prophet (forecasting)
- Container: Docker Compose
- CI/CD: GitHub Actions

## Non-Negotiable Rules
1. LLM = narrator on pre-computed KPIs, NEVER calculator on raw data
2. Bronze raw data NEVER exposed to frontend or LLM — only validated Gold layer
3. Every LLM recommendation must display its source data
4. Deterministic computations separated from narrative layer
5. All KPIs defined in `agent_docs/kpi_catalog.md` — check before creating new ones

## Code Standards
- Python 3.11+, type hints mandatory, ruff + mypy
- dbt models: snake_case, layer prefixes (stg_/int_/fct_/dim_/agg_)
- SQL: PostgreSQL dialect, never SELECT *, always explicit columns
- API: FastAPI + Pydantic v2 DTOs, dependency injection for DB, OpenAPI auto-doc
- Frontend: Next.js 14 App Router, Shadcn/UI, TypeScript strict, no `any`
- Tests: pytest for Python, dbt tests for models, Vitest for Next.js

## NEVER Suggest (during MVP)
- Kafka, LangChain, Airflow, Spark (distributed)
- Multiple datasets (DataCo, Budget vs Actual) — Olist only

## Future Add-ons (post-MVP, after ship)
- ChromaDB + RAG on Olist reviews (~99K PT comments)
- SpringBoot backend for ERP/CRM integration layer & Multi-tenant auth, enterprise SSO, mobile app
- Azure Data Factory + Databricks (cloud-native orchestration)
- Celery + Redis (async job queue)
- Snowflake free trial (cloud mirror of Gold layer)
- Self-Critique LLM (second pass verification)
- Sentiment NLP on Portuguese reviews

## Definition of Done
- Code on feature/ branch, tests pass
- dbt tests green for any SQL changes
- OpenAPI docs updated for API changes
- README updated if needed
- No secrets in code (use .env.example)
