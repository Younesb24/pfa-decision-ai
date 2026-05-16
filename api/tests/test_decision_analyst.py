"""
Unit tests for the Decision Analyst agent — pure function logic only.
No DB calls, no LLM calls.

Markers:
  (none) — runs in all test modes
  integration — needs a live Postgres + LLM (excluded by default)
  llm — needs a live LLM (excluded by default)
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Make api/ importable without an installed package ─────────────────────────
API_DIR = Path(__file__).parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Stub out db so we can import without a real Postgres connection
_db_stub = types.ModuleType("db")
_db_stub.query_gold = MagicMock(return_value=[])          # type: ignore[attr-defined]
_db_stub.query_gold_one = MagicMock(return_value=None)    # type: ignore[attr-defined]
_db_stub.log_audit = MagicMock(return_value=None)         # type: ignore[attr-defined]
sys.modules.setdefault("db", _db_stub)
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extras", MagicMock())

from datetime import UTC  # noqa: E402

from agents.decision_analyst import (  # noqa: E402
    _build_brief,
    _extract_json,
    _offline_brief,
)
from agents.tools import TOOL_SCHEMAS, _serialize, call_tool  # noqa: E402
from schemas.decision_brief import DecisionBrief, Evidence  # noqa: E402

# ── TOOL_SCHEMAS tests ─────────────────────────────────────────────────────────


def test_tool_schemas_required_fields():
    """Every tool schema must have name, description, and parameters."""
    for schema in TOOL_SCHEMAS:
        assert "name" in schema, f"Missing 'name' in {schema}"
        assert "description" in schema, f"Missing 'description' in {schema}"
        assert "parameters" in schema, f"Missing 'parameters' in {schema}"
        assert schema["parameters"]["type"] == "object"


def test_tool_schemas_has_four_required_tools():
    """The four required tools from the handoff must be present."""
    names = {s["name"] for s in TOOL_SCHEMAS}
    for required in ("get_kpi_summary", "get_kpi_timeseries", "get_anomalies", "get_seller_risk"):
        assert required in names, f"Required tool missing: {required}"


# ── call_tool dispatch tests ───────────────────────────────────────────────────


def test_call_tool_unknown_raises_key_error():
    with pytest.raises(KeyError, match="unknown_tool"):
        call_tool("unknown_tool", {})


def test_call_tool_get_kpi_summary_dispatches(monkeypatch):
    """call_tool routes to _get_kpi_summary and returns a (dict, 1) tuple."""
    fake_row = {"period_start": "2018-01-01", "total_orders": 100}
    monkeypatch.setattr("agents.tools.query_gold_one", lambda *a, **kw: fake_row)

    result, count = call_tool("get_kpi_summary", {})
    assert count == 1
    assert result["total_orders"] == 100


def test_call_tool_get_kpi_timeseries_dispatches(monkeypatch):
    fake_rows = [{"order_date": "2018-01-01", "otif_rate": 90.0}]
    monkeypatch.setattr("agents.tools.query_gold", lambda *a, **kw: fake_rows)

    result, count = call_tool("get_kpi_timeseries", {})
    assert count == 1
    assert isinstance(result, list)


def test_call_tool_get_seller_risk_dispatches(monkeypatch):
    fake_rows = [{"seller_id": "abc", "seller_risk_score": 75.0}]
    monkeypatch.setattr("agents.tools.query_gold", lambda *a, **kw: fake_rows)

    result, count = call_tool("get_seller_risk", {"limit": 5})
    assert count == 1
    assert result[0]["seller_id"] == "abc"


def test_call_tool_filters_none_args(monkeypatch):
    """None-valued kwargs must not be forwarded to the function."""
    monkeypatch.setattr("agents.tools.query_gold_one", lambda *a, **kw: {})
    # start=None, end=None — should not cause a TypeError
    result, _ = call_tool("get_kpi_summary", {"start": None, "end": None})
    assert isinstance(result, dict)


# ── _serialize tests ───────────────────────────────────────────────────────────


def test_serialize_handles_datetime():
    from datetime import datetime, timezone

    dt = datetime(2018, 8, 15, 12, 0, 0, tzinfo=UTC)
    rows = [{"ts": dt, "val": 1}]
    out = _serialize(rows)
    assert isinstance(out[0]["ts"], str)
    assert "2018-08-15" in out[0]["ts"]


def test_serialize_handles_decimal_like():
    """Objects with __float__ (e.g. psycopg2 Decimal) are coerced to float."""

    class FakeDecimal:
        def __float__(self):
            return 3.14

    rows = [{"price": FakeDecimal()}]
    out = _serialize(rows)
    assert isinstance(out[0]["price"], float)
    assert abs(out[0]["price"] - 3.14) < 1e-9


# ── _extract_json tests ────────────────────────────────────────────────────────


def test_extract_json_plain():
    raw = '{"what_happened": "OTIF dropped"}'
    assert _extract_json(raw) == {"what_happened": "OTIF dropped"}


def test_extract_json_fenced():
    raw = '```json\n{"what_happened": "test"}\n```'
    assert _extract_json(raw) == {"what_happened": "test"}


def test_extract_json_returns_empty_on_garbage():
    assert _extract_json("no json here at all") == {}


# ── _offline_brief tests ───────────────────────────────────────────────────────


def test_offline_brief_returns_valid_brief():
    brief = _offline_brief("Why did OTIF drop?")
    assert isinstance(brief, DecisionBrief)
    assert brief.question == "Why did OTIF drop?"
    assert "not configured" in brief.what_happened.lower()


# ── _build_brief tests ─────────────────────────────────────────────────────────


def test_build_brief_minimal_raw():
    raw: dict = {
        "what_happened": "OTIF dropped to 85%.",
        "is_it_abnormal": "Yes, z-score = -2.3.",
        "why_it_matters": "Below 92% SLA threshold.",
    }
    brief = _build_brief("test question", raw, ["get_kpi_summary"], "anthropic", "claude-sonnet")
    assert brief.what_happened == "OTIF dropped to 85%."
    assert brief.provider == "anthropic"
    assert brief.tool_calls_made == ["get_kpi_summary"]


def test_build_brief_evidence_parsed():
    raw = {
        "what_happened": "test",
        "is_it_abnormal": "yes",
        "why_it_matters": "impact",
        "evidence": [
            {"metric": "OTIF Rate", "value": 87.3, "source": "gold.agg_daily_ops_kpi",
             "as_of": "2018-08-15", "unit": "%"}
        ],
    }
    brief = _build_brief("q", raw, [], "openai", "gpt-4o")
    assert len(brief.evidence) == 1
    assert brief.evidence[0].metric == "OTIF Rate"
    assert brief.evidence[0].unit == "%"


def test_build_brief_chart_hint_missing_keys_skipped():
    """chart_hint with missing x_key or y_key is silently dropped."""
    raw = {
        "what_happened": "test",
        "is_it_abnormal": "yes",
        "why_it_matters": "impact",
        "chart_hint": {"chart_type": "line"},  # missing x_key / y_key
    }
    brief = _build_brief("q", raw, [], "openai", "gpt-4o")
    assert brief.chart_hint is None


def test_build_brief_capped_at_three_actions():
    raw = {
        "what_happened": "test",
        "is_it_abnormal": "yes",
        "why_it_matters": "impact",
        "recommended_actions": [
            {"label": f"Action {i}", "action_type": "review", "urgency": "low"}
            for i in range(5)
        ],
    }
    brief = _build_brief("q", raw, [], "openai", "gpt-4o")
    assert len(brief.recommended_actions) <= 3
