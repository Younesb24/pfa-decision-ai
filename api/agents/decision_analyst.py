"""
Decision Analyst — iterative tool-use loop that produces a DecisionBrief.

Flow:
  1. System prompt + user question sent to LLM with all available tools.
  2. LLM calls tools → we execute them → append results → repeat (max 5 turns).
  3. After the loop, the LLM synthesises a structured JSON DecisionBrief.
  4. We parse + validate it via the Pydantic schema.

Provider priority: Anthropic (CLAUDE.md standard) → OpenAI fallback.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

from db import log_audit
from llm_client import complete_with_tools, get_provider, is_available
from schemas.decision_brief import (
    ChartHint,
    DecisionBrief,
    Evidence,
    RecommendedAction,
)

from agents.tools import TOOL_SCHEMAS, call_tool

MAX_ITERATIONS = 5

ANALYST_SYSTEM = """You are a senior e-commerce operations analyst for an Olist marketplace.

You have access to tools that query a pre-computed Gold analytics layer.
ALWAYS call at least one tool before drawing conclusions.
NEVER invent or extrapolate data you have not retrieved via a tool.

After gathering enough evidence, produce a JSON object with EXACTLY these fields
(no extra keys, no markdown fences):
{
  "what_happened": "One-paragraph factual summary of what the data shows.",
  "is_it_abnormal": "Whether the pattern is statistically abnormal and z-score context.",
  "why_it_matters": "Business impact for the Head of E-commerce Operations.",
  "evidence": [
    {"metric": "OTIF Rate", "value": 87.3, "source": "gold.agg_daily_ops_kpi",
     "as_of": "2018-08-15", "unit": "%"}
  ],
  "chart_hint": {
    "chart_type": "line",
    "x_key": "order_date",
    "y_key": "otif_rate",
    "title": "OTIF Rate — Last 30 Days",
    "data": [{"order_date": "2018-08-01", "otif_rate": 89.1}, ...]
  },
  "recommended_actions": [
    {"label": "Draft seller warning email", "action_type": "email",
     "urgency": "high", "payload": {"subject": "...", "seller_ids": [...]}}
  ],
  "follow_up_questions": ["...", "...", "..."]
}

Rules:
- evidence[].source must name the Gold table used (e.g. gold.agg_daily_ops_kpi)
- chart_hint.data must be actual rows from your tool results (max 30 rows)
- 2-3 recommended_actions maximum; urgency: low | medium | high
- exactly 3 follow_up_questions
- Return ONLY the JSON object — no prose before or after.
"""


def _offline_brief(question: str) -> DecisionBrief:
    """Fallback when no LLM is configured."""
    return DecisionBrief(
        question=question,
        what_happened="LLM provider not configured — no analysis available.",
        is_it_abnormal="Cannot determine without LLM.",
        why_it_matters="Configure ANTHROPIC_API_KEY or OPENAI_API_KEY to enable analysis.",
        generated_at=datetime.now(UTC).isoformat(),
    )


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from the model's text output."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Find any {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _build_brief(
    question: str,
    raw: dict,
    tool_calls_made: list[str],
    provider: str,
    model: str,
) -> DecisionBrief:
    """Construct a validated DecisionBrief from the parsed LLM JSON."""
    evidence: list[Evidence] = []
    for e in raw.get("evidence", []):
        if isinstance(e, dict):
            evidence.append(Evidence(
                metric=str(e.get("metric", "")),
                value=e.get("value", ""),
                source=str(e.get("source", "")),
                as_of=e.get("as_of"),
                unit=e.get("unit"),
            ))

    chart_hint: ChartHint | None = None
    ch = raw.get("chart_hint")
    if isinstance(ch, dict) and ch.get("x_key") and ch.get("y_key"):
        chart_hint = ChartHint(
            chart_type=ch.get("chart_type", "line"),
            x_key=str(ch["x_key"]),
            y_key=str(ch["y_key"]),
            title=ch.get("title"),
            data=ch.get("data", [])[:30],
        )

    actions: list[RecommendedAction] = []
    allowed_action_types = {"email", "webhook", "escalation", "review"}
    allowed_urgency = {"low", "medium", "high"}
    for a in raw.get("recommended_actions", [])[:3]:
        if isinstance(a, dict):
            # The model gets creative with action_type ("meeting", "call", etc.)
            # — coerce anything outside the schema enum to "review" so a single
            # vocabulary slip doesn't 500 the whole brief.
            raw_at = str(a.get("action_type", "review")).lower()
            action_type = raw_at if raw_at in allowed_action_types else "review"
            raw_u = str(a.get("urgency", "medium")).lower()
            urgency = raw_u if raw_u in allowed_urgency else "medium"
            actions.append(RecommendedAction(
                label=str(a.get("label", "Review")),
                action_type=action_type,
                urgency=urgency,
                payload=a.get("payload", {}) if isinstance(a.get("payload"), dict) else {},
            ))

    follow_ups = [str(q) for q in raw.get("follow_up_questions", []) if q][:3]

    return DecisionBrief(
        question=question,
        what_happened=raw.get("what_happened", "No summary available."),
        is_it_abnormal=raw.get("is_it_abnormal", ""),
        why_it_matters=raw.get("why_it_matters", ""),
        evidence=evidence,
        chart_hint=chart_hint,
        recommended_actions=actions,
        follow_up_questions=follow_ups,
        tool_calls_made=tool_calls_made,
        generated_at=datetime.now(UTC).isoformat(),
        provider=provider,
        model=model,
    )


def analyse(question: str) -> DecisionBrief:
    """
    Run the Decision Analyst loop and return a structured DecisionBrief.

    Records tool calls in governance.audit_log. Never raises — on error returns
    a minimal brief with error context so the API caller always gets a response.
    """
    if not is_available():
        return _offline_brief(question)

    started = time.perf_counter()
    provider = get_provider()
    model = ""
    tool_calls_made: list[str] = []

    # OpenAI-style unified message history (see llm_client._msgs_to_anthropic)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    raw_brief: dict = {}
    last_text: str = ""

    try:
        for _iteration in range(MAX_ITERATIONS):
            step = complete_with_tools(
                messages=messages,
                tools=TOOL_SCHEMAS,
                system=ANALYST_SYSTEM,
            )
            model = step.model

            if step.text:
                # Model produced text — this is the final synthesis
                last_text = step.text
                raw_brief = _extract_json(last_text)
                break

            if not step.tool_calls:
                # Model stalled with no text and no tool calls — stop
                break

            # Execute tool calls and append results
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in step.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in step.tool_calls:
                tool_calls_made.append(tc.name)
                try:
                    result, row_count = call_tool(tc.name, tc.arguments)
                    content = json.dumps(result, default=str)
                except Exception as exc:
                    result = {"error": str(exc)}
                    row_count = 0
                    content = json.dumps(result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": content,
                })

                # Audit every tool call
                log_audit(
                    endpoint="POST /api/v1/ask/agent",
                    user_input=question,
                    llm_provider=provider,
                    llm_model=model,
                    data_context={
                        "tool": tc.name,
                        "args": tc.arguments,
                        "row_count": row_count,
                    },
                )

    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_audit(
            endpoint="POST /api/v1/ask/agent",
            user_input=question,
            llm_provider=provider,
            error=str(exc),
            latency_ms=latency_ms,
        )
        return DecisionBrief(
            question=question,
            what_happened=f"Agent error: {exc}",
            is_it_abnormal="Unknown — agent did not complete.",
            why_it_matters="Check API logs for details.",
            tool_calls_made=tool_calls_made,
            generated_at=datetime.now(UTC).isoformat(),
            provider=provider,
            model=model,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    log_audit(
        endpoint="POST /api/v1/ask/agent",
        user_input=question,
        llm_provider=provider,
        llm_model=model,
        llm_output=last_text[:2000],
        data_context={"tool_calls": tool_calls_made, "iterations": len(tool_calls_made)},
        latency_ms=latency_ms,
    )

    return _build_brief(question, raw_brief, tool_calls_made, provider, model)
