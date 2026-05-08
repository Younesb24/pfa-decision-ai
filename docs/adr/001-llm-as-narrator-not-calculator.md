# ADR 001 — LLM as narrator, never calculator

**Status:** Accepted
**Date:** 2026-04
**Supersedes:** —

## Context

The product surfaces business KPIs (OTIF, AOV, NPS proxy, cancellation rate,
seller risk) and an executive narrative on top of them. Two architectures were
on the table:

1. **LLM-as-calculator** — feed raw rows into an LLM, ask it to compute the KPI
   and write the narrative in one pass.
2. **LLM-as-narrator** — compute every KPI deterministically in SQL (Gold layer),
   pass the *result* to the LLM, ask it only for prose.

## Decision

We use approach (2). All numbers in the dashboard, in the narrative, and in any
alert come from `gold.agg_*` tables. The LLM never receives a raw `fct_orders`
row, never receives free-form numeric ranges, and is prompted with the explicit
rule *"NEVER invent numbers — only reference what's provided in the data
context"* (see `api/routers/insights.py`).

## Consequences

- **Reliability:** the OTIF figure shown to a user can be reproduced exactly by
  re-running the SQL. There is no hallucination surface for numbers.
- **Auditability:** every LLM response is paired with the `data_context` that
  produced it; the audit journal stores both (see ADR-006 once written).
- **Cost:** roughly 5–10× cheaper than putting raw rows in context, since we
  send tens of pre-aggregated numbers, not 100K orders.
- **Cost we accept:** the LLM cannot answer questions like *"what's the median
  delivery time for São Paulo customers?"* unless we add that column to a Gold
  aggregate or expose the text-to-SQL path. That's by design.

## Alternatives considered

- **Calculator pattern with a verifier pass.** Lower bound on hallucination is
  still non-zero, and the verifier is itself an LLM. Defers the problem.
- **Pure deterministic templates (no LLM).** Loses the differentiator.
  Templates exist as a fallback when the LLM is unavailable; they are not the
  primary path.
