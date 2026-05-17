---
title: "PFA Decision AI — One-pager"
subtitle: "AI-powered decision support for e-commerce marketplace operations"
author: "Bouazzaoui Younes — ENSAO MGSI 2026"
date: "2026-05-17"
geometry: "margin=1.6cm"
colorlinks: true
linkcolor: NavyBlue
urlcolor: NavyBlue
fontsize: 10pt
mainfont: "Inter"
---

<!--
Render with:
  pandoc docs/one_pager.md -o docs/one_pager.pdf --pdf-engine=xelatex
This file is the LaTeX/PDF source. Keep it to a single A4 page when rendered.
-->

## The problem

The head of e-commerce ops at a marketplace operator opens five tools every
morning — BI dashboard, ML notebook, Slack alerts, the data team's freshness
report, the order-management console — and *manually* stitches the answer to
one question: **what should I do today, and why.**

That stitch is where decisions go wrong. The dashboard shows OTIF is down,
but not which sellers are pulling it down. The ML team has a late-delivery
model, but its top-5 list lives in a notebook the operator can't access.
Slack has the alerts but no audit trail.

## The system

**PFA Decision AI** collapses those five tools into one OODA-loop console
on top of the Olist Brazilian E-commerce dataset (100 000 real orders,
8 relational tables, 99 000 reviews).

```
┌─ Observe ─┐  ┌─ Orient ──┐  ┌─ Decide ──┐  ┌─ Act ─────┐
│  KPIs +   │→ │  Narrative │→ │  Risky    │→ │  Audit +  │
│  Anomalies│  │  (LLM)     │  │  sellers  │  │  Govern.  │
└───────────┘  └────────────┘  └───────────┘  └───────────┘
```

The non-negotiable rule: **the LLM is a narrator, never a calculator.**
Every number is pre-computed in the dbt Gold layer; the LLM only converts
that numeric truth into prose, with the source rows displayed alongside.

## Architecture (locked stack)

| Layer | Tech |
|---|---|
| Ingestion | Python CSV loader → PostgreSQL 16 `bronze` schema |
| Transform | dbt Core — `bronze → silver → gold` medallion |
| Serving | FastAPI (Python 3.11, Pydantic v2), Next.js 14 App Router + Shadcn/UI |
| ML | scikit-learn / XGBoost (late-delivery), Holt-Winters (forecast) |
| LLM | Anthropic Claude Sonnet — text-to-SQL on a semantic layer, narrative gen |
| Orchestration | Dagster Core (replay clock, dbt schedule) |
| Infra | Docker Compose dev, ECS Fargate + RDS Postgres + ALB on AWS prod |
| CI / quality | ruff + mypy + 118 pytest tests + dbt tests + Next.js typecheck |

## Decision-intelligence guarantees

1. **Deterministic KPIs.** Every metric on the dashboard is computed in
   SQL inside the Gold layer. Reproducible from `dbt run`.
2. **Auditable LLM.** Every Claude call writes a row to
   `governance.audit_log` linking the prompt, the response, the SQL it
   produced, and the operator's review decision.
3. **Pipeline isolation.** Bronze raw rows never reach the LLM or the
   frontend. The API only reads from `gold.*`.
4. **Human-in-the-loop.** Every alert resolves through
   `POST /governance/review` — the OODA "Act" beat is a real database
   write, not a UI toast.

## What's shipped

- **API** — 14 endpoints, OpenAPI auto-docs, JWT auth (bcrypt + PyJWT),
  role-gated routes (`admin > ops > analyst > viewer`).
- **Dashboard** — 4 pages: console, data-health, ingest, login.
- **Pipeline** — bronze loader, 16 dbt models (staging, intermediate,
  marts), replay simulator that advances a synthetic clock.
- **ML** — XGBoost late-delivery classifier (ROC-AUC ≈ 0.82) + Holt-Winters
  forecast. Model card discloses the late-delivery F1 = 0.38 (imbalanced
  positive class) and recommends shipping a probability gauge, not a hard
  classifier, in production.
- **Infra** — Docker images for api / dashboard / dagster; Terraform
  skeleton for ECS Fargate + RDS + ALB + EventBridge replay loop on AWS.
- **Tests** — 118 pytest, ruff + mypy clean, dbt tests green, Next.js
  build green on CI.

## Demo

3-minute Loom — OTIF crisis end-to-end:
<https://www.loom.com/share/YOUR-LOOM-ID>

Live URL — <https://YOUR-PUBLIC-URL> · `ops@pfa.local / ops123`

Source — <https://github.com/Younesb24/pfa-decision-ai>

## What this project deliberately is **not**

- **Not a fully-autonomous agent.** The LLM never executes side effects;
  every "act" is initiated by a human.
- **Not a generic Text-to-SQL tool.** Queries are constrained to a
  semantic layer over Gold; arbitrary `SELECT` against Bronze is denied.
- **Not multi-tenant.** Single dataset, single persona, single org.
  SSO and per-tenant data partitioning are post-MVP.

---

*Stack locked, scope locked, ship locked.*
