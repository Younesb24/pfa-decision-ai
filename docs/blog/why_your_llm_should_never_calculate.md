---
title: "Why your LLM should never calculate"
subtitle: "Notes from building a decision-intelligence MVP on top of Claude"
author: "Bouazzaoui Younes — ENSAO MGSI 2026"
date: "2026-05-19"
tags: [llm, decision-intelligence, claude, anthropic, data-engineering, dbt]
canonical: "https://github.com/Younesb24/pfa-decision-ai/blob/main/docs/blog/why_your_llm_should_never_calculate.md"
---

I spent the last four months building **PFA Decision AI** — a decision-support
tool for a marketplace ops persona on top of the Olist Brazilian E-commerce
dataset. The stack is boring on purpose: PostgreSQL, dbt, FastAPI, Next.js,
Claude Sonnet, XGBoost, Holt-Winters. The point of the project was not the
stack. The point was *one* architectural rule:

> **The LLM is a narrator, never a calculator.**

Every number on the dashboard is computed in SQL, in a deterministic dbt
medallion pipeline, and stored in a Gold layer the API reads directly. The
LLM never touches Bronze. The LLM never re-derives a metric. The LLM only
writes English on top of numbers that already exist.

If you take one thing from this post: **the moment you ask an LLM to do
arithmetic on raw rows, you have lost the audit trail.** Everything that
follows is just unpacking that sentence.

## The pattern that doesn't work

The default agentic pipeline you see in tutorials is some version of:

1. User asks a question in natural language.
2. LLM writes a Python snippet (or a pandas call, or some SQL).
3. The snippet runs against the raw warehouse.
4. The LLM reads the result and explains it.

This works in demos. It does not work in a place where someone has to
**defend the number** to a regulator, a CFO, or a jury.

Three reasons:

**1. The LLM is non-deterministic at the metric layer.** If your KPI
definition lives inside a prompt, the "official" OTIF rate of your business
is reconstructed from a 7-billion-parameter neural network's recall every
time you ask. The number may be roughly right. It will not be the same
number twice in a row. You will not be able to git-diff what changed
between Monday's number and Tuesday's.

**2. The LLM hallucinates schema.** "What's the total order value last
month?" → the model invents a column called `order_total` that does not
exist, runs the query against your warehouse anyway because the agent
framework was helpful, and returns a confident answer of zero. Or worse,
a confident answer of something that looks plausible because the SQL
silently aggregated the wrong table.

**3. The audit trail collapses.** When an LLM derives the metric, the
prompt is the source of truth. Prompts change. Prompts are sometimes
A/B-tested. Six months later, when someone asks "why did OTIF jump 4
points in March", the answer is "we updated the prompt." Nobody can ship
that to a board.

## The pattern that does work

Split the system into two layers and never cross them:

```
┌──────────────────────────────────────────────────────┐
│   Deterministic layer (boring, audited, reproducible) │
│   - dbt medallion: bronze → silver → gold             │
│   - one definition of OTIF, in SQL, in version control │
│   - dbt tests: not_null, unique, accepted_values       │
│   - Output: a Gold table with named columns           │
└──────────────────────────────────────────────────────┘
                          │
                          ▼ (only Gold rows cross this line)
┌──────────────────────────────────────────────────────┐
│   Narrative layer (creative, persona-aware, English)  │
│   - LLM receives pre-computed rows + a persona token  │
│   - LLM writes a briefing in 4 sentences              │
│   - Every output linked to its source rows in the UI  │
│   - Every call written to governance.audit_log        │
└──────────────────────────────────────────────────────┘
```

The Gold layer is the contract. The narrative layer is decoration on top
of it. If you want to know *what* changed, you read the SQL. If you want
to know *how to explain it to ops*, you read the LLM output. The two
roles are physically separated by a router boundary in the API.

In our codebase this is enforced by three rules:

```
# CLAUDE.md — non-negotiable rules
1. LLM = narrator on pre-computed KPIs, NEVER calculator on raw data
2. Bronze raw data NEVER exposed to frontend or LLM — only validated Gold layer
3. Every LLM recommendation must display its source data
```

These are not aspirational. They are checked by the type system (the API
function that builds the LLM prompt takes a `GoldKpiRow`, never a
`BronzeOrderRow`) and by tests (the prompt-builder unit tests assert
that no Bronze table name appears anywhere in the rendered prompt).

## "But what about text-to-SQL?"

Text-to-SQL is the one place the LLM does write SQL — and it is the place
the discipline matters most. The standard pattern in 2026 (Snowflake
Cortex, AWS Bedrock, Salesforce Horizon) is the same one we use:

1. The LLM sees a **semantic layer**, not the raw warehouse. In our
   project this is a curated list of `agg_*` tables, column names, and
   prose descriptions. The LLM never sees `bronze.orders`.
2. Every generated query goes through a SQL parser before execution.
   We reject anything that isn't `SELECT` / `WITH`, anything that
   touches `pg_*` or `information_schema`, anything multi-statement,
   anything with `COPY` / `GRANT` / `REVOKE`. The validator is 50 lines
   of Python and it has caught every adversarial prompt we threw at it.
3. Every executed query writes a row to `governance.audit_log` *before*
   the result is rendered. If the call 500s mid-execution, the
   prompt+SQL pair is still on disk.

This is the same shape as the narrative pattern: the LLM proposes, the
deterministic layer enforces, the audit log remembers. The LLM never
gets a back-channel to the data.

## "Doesn't this make the LLM useless?"

The opposite. Once you stop asking it to derive numbers, you can ask it
to do the things it is *good* at, with confidence the inputs are right:

- **Personalize.** Same number, three different briefings — one for ops
  (delivery focus), one for finance (margin focus), one for supply
  (seller-tier focus). Five lines of prompt difference, three useful
  surfaces.
- **Explain.** "OTIF dropped because three sellers in the South region
  account for 60% of the late deliveries." The math came from
  `agg_seller_scorecard`. The English came from the LLM. Each is
  better at its job.
- **Connect.** "This is the third week in a row OTIF dipped on the same
  weekday." Pattern recognition on small numeric tables is something
  LLMs do well, *provided the numbers themselves are reliable*.

## What it cost us

The setup tax is real and worth naming.

- **Two days of dbt.** The full medallion (bronze → silver → gold) is
  about 16 models for our dataset. Roughly two days of focused work,
  including the test scaffolding. This is also the most reusable
  investment in the whole project — every downstream surface (API, ML,
  LLM, dashboard) consumes from Gold.
- **A prompt-shape discipline.** Every prompt-builder is a function that
  takes typed rows and returns a string. We do not let prompts grow
  imperatively across handlers. This took some refactoring to enforce.
- **One audit-log migration.** `governance.audit_log` is a single table
  with seven columns. The first migration took an hour. The discipline
  of *always* writing to it before returning the LLM output is the
  thing that took diligence — easy to forget on the happy path.

That's it. There is no fancier infrastructure required to get the
discipline. No vector store. No agent framework. No LangChain. You can
build this in pure FastAPI + dbt + the Anthropic SDK in a weekend.

## What we got

- **A demoable OODA loop in one tool.** Observe (KPIs + anomalies),
  Orient (LLM briefing), Decide (risky-seller drill-down + ML
  predictions), Act (`POST /governance/review`).
- **A defensible number every time.** Every value on the dashboard is
  reproducible from `dbt run`. Every LLM sentence is reproducible from
  the audit-log entry that produced it.
- **A model card that doesn't lie.** When the late-delivery F1 came in
  at 0.38 (because the positive class is 8% of the dataset and we used
  a default threshold), we wrote it down. When the forecast MAPE
  reported 259 262% because the eval window included near-zero
  warm-up days, we wrote a postmortem, switched to sMAPE + floored
  MAPE, added unit tests. None of this was hidden from the jury.

The decision-intelligence pitch — "your LLM helps you decide, it doesn't
decide for you, and every step is auditable" — only works if the LLM
isn't the one doing the math. Make that one architectural choice and
everything else gets easier.

---

*The repo is at <https://github.com/Younesb24/pfa-decision-ai>. The
relevant ADRs are:*

- *[ADR-001 — LLM as narrator, never calculator](../adr/001-llm-as-narrator-not-calculator.md)*
- *[ADR-002 — Medallion over a flat warehouse](../adr/002-medallion-over-flat-warehouse.md)*
- *[ADR-008 — Tool-based agent pattern](../adr/008-tool-based-agent-pattern.md)*

*If you spot a way this discipline breaks down at scale (multi-tenant,
streaming, etc.), I'd love to hear it — open an issue.*
