# ADR-008 — Tool-Based Agent Pattern for the Decision Analyst

**Status:** Accepted  
**Date:** 2026-05-16  
**Context:** Day 7 of the 20-day PFA sprint  

---

## Context

Until Day 6, the `/ask` endpoint used a single-shot text-to-SQL pattern: one
LLM call generates a SELECT query, we execute it, and return raw rows. This
works for factual lookups ("top 5 sellers by revenue") but fails for
interpretive questions ("why did OTIF drop last week?") because:

1. A single SQL query cannot aggregate across multiple Gold tables in one shot.
2. The LLM must invent SQL syntax for logic it hasn't seen — hallucination risk.
3. There is no structured output contract; the frontend parses raw rows.

The OODA-Learn architecture requires an **Orient** step that interprets data,
not just retrieves it. We need a pattern that lets the model iteratively gather
evidence before synthesising a narrative.

---

## Decision

Implement a **tool-use loop** (also called "function calling" or "ReAct" in
the literature) as the primary question-answering path:

1. Six pre-defined tools map to Gold-layer queries: `get_kpi_summary`,
   `get_kpi_timeseries`, `get_anomalies`, `get_seller_risk`,
   `get_revenue_by_category`, `get_recent_alerts`.
2. The LLM is given all tools and a structured system prompt on the first
   turn. It selects which tools to call.
3. We execute the tools, feed results back, and iterate (up to
   `MAX_ITERATIONS = 5` turns).
4. When the model produces text instead of tool calls, we treat it as the
   final synthesis and parse it as JSON matching the `DecisionBrief` schema.

The new endpoint is `POST /api/v1/ask/agent`. The legacy `POST /api/v1/ask`
(text-to-SQL) remains in place for one release as a backward-compatibility
fallback.

---

## Alternatives Rejected

### Single-shot LLM with multi-table prompt

The system prompt could include all six table schemas and ask the model to
produce a multi-table SQL join. Rejected because:

- Anthropic's text-to-SQL accuracy degrades sharply on multi-table joins
  over 4+ tables when the schema is injected into the prompt.
- We cannot cap row access: the model might produce cartesian products.
- No incremental evidence gathering — the model must commit up front.

### LangChain SQL agent

Rejected per `CLAUDE.md` ("NEVER Suggest: LangChain"). The tool-use loop
is implemented directly against the provider SDKs with ~150 lines of code,
giving us full observability and no hidden abstraction layer.

### Single structured prompt (no tools)

Ask the model to produce the `DecisionBrief` JSON in one shot, injecting
pre-fetched KPI context into the prompt. Rejected because:

- We would need to fetch ALL possible data on every request (wasteful).
- The model cannot ask follow-up questions when the first fetch reveals
  an anomaly that needs drilling into.

---

## Why Max 5 Iterations

Five tool-call turns is enough to:
- Call `get_kpi_summary` (1) to establish the baseline.
- Call `get_anomalies` (2) to identify what's unusual.
- Call `get_kpi_timeseries` (3) for chart data.
- Call `get_seller_risk` (4) to find the root cause.
- Synthesise text (5 = iteration where the model writes the brief).

Beyond 5, the pattern has been observed to loop on ambiguous questions rather
than converging. Cost also scales linearly with iterations; 5 is the sweet
spot for our GPT-4o / Claude Sonnet budgets.

---

## Why a Strict Pydantic Schema

`DecisionBrief` defines five required sections: `what_happened`,
`is_it_abnormal`, `why_it_matters`, `evidence`, `recommended_actions`.

- Forces the model to produce complete, structured output rather than prose.
- Frontend `DecisionBriefCard` can render each section independently.
- Evidence pills require `metric`, `value`, `source`, `as_of` — without the
  schema, the model would omit source citations (ADR-001 requirement: every
  recommendation must display its source data).
- Pydantic validation at the API boundary means the frontend never receives
  a malformed brief.

---

## What Happens When the Model Doesn't Call a Tool

The loop exits early if the model returns text without calling any tools.
`_build_brief` still constructs a `DecisionBrief` from whatever fields the
model produced; missing fields get safe defaults. The `tool_calls_made` list
in the response will be empty, signalling to the operator that the brief is
not evidence-backed.

This beats a hard error: the operator still gets a response, and the audit
log captures `tool_calls: []` so the gap is visible in governance.

---

## Consequences

- **Provider compatibility:** Both Anthropic and OpenAI tool-use APIs are
  supported. `llm_client.complete_with_tools` converts the neutral schema
  format and message history to each provider's wire format.
- **Audit trail:** Every tool call is recorded in `governance.audit_log`
  with `endpoint='POST /api/v1/ask/agent'` and a `data_context` JSON
  containing the tool name, args, and row count. This satisfies the
  auditability requirement in ADR-001.
- **No raw data to LLM:** Tool implementations query only Gold-layer
  aggregates, never Bronze or Silver tables. Consistent with ADR-001.
- **Iteration cap risk:** A pathological question could exhaust all 5 turns
  without producing a synthesis. The fallback brief (`tool_calls_made` with
  no text) prevents a 500 but may produce an incomplete answer.
