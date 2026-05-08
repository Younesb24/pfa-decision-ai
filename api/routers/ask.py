"""
Text-to-SQL endpoint — converts a natural-language question into a PostgreSQL
SELECT against the Gold schema, executes it read-only, and returns rows.

Provider: Anthropic Claude (preferred per CLAUDE.md), OpenAI GPT-4o as fallback.
See api/llm_client.py.

Safety layers (all enforced before execution):
1. The model is instructed to only emit SELECT/WITH against gold.*
2. We strip code fences and reject anything not starting with SELECT/WITH
3. We reject access to system catalogs (pg_*, information_schema)
4. We reject multi-statement input (any ';' before the trailing whitespace)
5. We cap returned rows to 50

Every request — successful or rejected — is recorded in governance.audit_log.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from db import log_audit, query_gold

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Query
from llm_client import complete, get_provider, is_available

# pyrefly: ignore [missing-import]
from pydantic import BaseModel

router = APIRouter()

# ── Semantic Layer System Prompt ──
SYSTEM_PROMPT = """You are a PostgreSQL SQL expert for an Olist e-commerce data warehouse.
You generate ONLY valid PostgreSQL SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, or ALTER.
Never reference pg_catalog, pg_*, or information_schema.

## Available Tables (all in 'gold' schema):

### gold.fct_orders (grain: 1 row per order item, ~112K rows)
- order_id (text), order_item_id (int), customer_key (int), seller_key (int)
- product_key (int), purchase_date_key (int FK to dim_date.date_key)
- order_status (text): delivered, shipped, canceled, unavailable, invoiced, processing, created, approved
- price (numeric), freight_value (numeric), total_item_value (numeric = price + freight)
- order_total_payment (numeric)
- delivery_delay_days (numeric, positive = late), is_late (boolean)
- processing_time_days, shipping_time_days, total_lead_time_days (numeric)
- order_purchase_at (timestamp), seller_id (text)

### gold.fct_reviews (grain: 1 row per review, ~99K rows)
- review_id (text), order_id (text FK), customer_id (text)
- review_score (int 1-5), has_comment (boolean)
- nps_category (text): 'promoter' (4-5), 'passive' (3), 'detractor' (1-2)
- review_created_at (timestamp)

### gold.dim_customer (~96K rows)
- customer_key (int), customer_unique_id (text), customer_state (text), customer_city (text)

### gold.dim_seller (~3K rows)
- seller_key (int), seller_id (text), seller_state (text), seller_city (text)

### gold.dim_product (~33K rows)
- product_key (int), product_id (text), product_category_name (text)
- product_weight_g, product_volume_cm3 (numeric)

### gold.dim_date (852 rows)
- date_key (int YYYYMMDD), full_date (date), year, month, quarter, week_of_year, day_of_week (int)
- is_weekend, is_brazilian_holiday (boolean)

### gold.agg_daily_ops_kpi (616 rows, 1 per day)
- order_date (date), date_key (int)
- total_orders, total_items (int)
- total_revenue, total_freight, total_gmv, aov (numeric, BRL)
- otif_rate (numeric, target >= 92%), cancellation_rate (numeric)
- avg_delivery_delay_days, active_sellers, unique_customers

### gold.agg_seller_scorecard (~3K rows, 1 per seller)
- seller_id (text), total_orders, delivered_orders, late_orders, canceled_orders (int)
- total_revenue (numeric), late_delivery_rate, cancellation_rate (numeric percent)
- avg_review_score (numeric 1-5), seller_risk_score (numeric 0-100, higher=riskier)

## Rules:
1. ALWAYS use the gold. schema prefix
2. Return ONLY the SQL query, no explanations, no code fences
3. Use CTEs for complex queries
4. Add LIMIT 50 unless the user asks for "all"
5. For "recent", use the max(order_date) from agg_daily_ops_kpi as anchor
6. Use total_item_value (price + freight) for revenue
7. Round numeric results to 2 decimals
8. count(DISTINCT order_id) for order counts (fct_orders grain is order item)
"""


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    sql: str
    data: list[dict] | None = None
    row_count: int | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None
    generated_at: str


# ── SQL safety ──

_FORBIDDEN_PATTERNS = [
    re.compile(r"\bpg_catalog\b", re.IGNORECASE),
    re.compile(r"\bpg_authid\b", re.IGNORECASE),
    re.compile(r"\bpg_shadow\b", re.IGNORECASE),
    re.compile(r"\bpg_user\b", re.IGNORECASE),
    re.compile(r"\bpg_roles\b", re.IGNORECASE),
    re.compile(r"\bpg_stat_\w*\b", re.IGNORECASE),
    re.compile(r"\binformation_schema\b", re.IGNORECASE),
    re.compile(r"\bcopy\b", re.IGNORECASE),
    re.compile(r"\bgrant\b", re.IGNORECASE),
    re.compile(r"\brevoke\b", re.IGNORECASE),
]


def _strip_fences(sql: str) -> str:
    """Remove ```sql ... ``` code fences if the model wrapped its output."""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.splitlines()
        # drop first fence line and trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        sql = "\n".join(lines).strip()
    return sql


def validate_sql(sql: str) -> str | None:
    """
    Returns an error message string if the SQL is unsafe, otherwise None.
    Pure function — easy to unit test.
    """
    cleaned = sql.strip()
    if not cleaned:
        return "Empty SQL"

    upper = cleaned.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return "Only SELECT / WITH queries are allowed"

    # Reject multi-statement: any ';' before the final trailing whitespace
    body = cleaned.rstrip().rstrip(";")
    if ";" in body:
        return "Multi-statement SQL is not allowed"

    for pat in _FORBIDDEN_PATTERNS:
        if pat.search(cleaned):
            return f"Reference to restricted object ({pat.pattern}) is not allowed"

    return None


# ── Endpoint ──

@router.post("/ask")
async def ask_question(req: AskRequest) -> AskResponse:
    """
    Natural language → SQL → results, against the Gold layer only.
    """
    started = time.perf_counter()

    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    if not is_available():
        msg = (
            "No LLM provider configured. Set ANTHROPIC_API_KEY (preferred) "
            "or OPENAI_API_KEY in your environment."
        )
        log_audit(
            endpoint="POST /api/v1/ask",
            user_input=req.question,
            error=msg,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AskResponse(
            question=req.question, sql="", error=msg, generated_at=now_iso()
        )

    # Step 1: NL → SQL
    try:
        result = complete(
            system=SYSTEM_PROMPT,
            user=f"Generate a PostgreSQL query for: {req.question}",
            max_tokens=1024,
            temperature=0.2,
        )
        sql = _strip_fences(result.text)
    except Exception as e:
        msg = f"LLM error: {e}"
        log_audit(
            endpoint="POST /api/v1/ask",
            user_input=req.question,
            llm_provider=get_provider(),
            error=msg,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AskResponse(
            question=req.question, sql="", error=msg, generated_at=now_iso()
        )

    # Step 2: validate
    safety_error = validate_sql(sql)
    if safety_error:
        log_audit(
            endpoint="POST /api/v1/ask",
            user_input=req.question,
            llm_provider=result.provider,
            llm_model=result.model,
            llm_output=sql,
            error=f"safety: {safety_error}",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AskResponse(
            question=req.question,
            sql=sql,
            error=f"Safety: {safety_error}",
            provider=result.provider,
            model=result.model,
            generated_at=now_iso(),
        )

    # Step 3: execute
    try:
        rows = query_gold(sql)
    except Exception as e:
        msg = f"SQL execution error: {e}"
        log_audit(
            endpoint="POST /api/v1/ask",
            user_input=req.question,
            llm_provider=result.provider,
            llm_model=result.model,
            llm_output=sql,
            error=msg,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AskResponse(
            question=req.question,
            sql=sql,
            error=msg,
            provider=result.provider,
            model=result.model,
            generated_at=now_iso(),
        )

    # Serialize results
    capped = rows[:50]
    serialized: list[dict] = []
    for row in capped:
        clean: dict = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            elif hasattr(v, "__float__") and not isinstance(v, bool):
                try:
                    clean[k] = float(v)
                except Exception:
                    clean[k] = str(v)
            else:
                clean[k] = v
        serialized.append(clean)

    log_audit(
        endpoint="POST /api/v1/ask",
        user_input=req.question,
        llm_provider=result.provider,
        llm_model=result.model,
        llm_output=sql,
        data_context={"row_count": len(rows)},
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    return AskResponse(
        question=req.question,
        sql=sql,
        data=serialized,
        row_count=len(rows),
        provider=result.provider,
        model=result.model,
        generated_at=now_iso(),
    )


@router.get("/ask")
async def ask_question_get(
    q: str = Query(..., description="Natural language question"),
) -> AskResponse:
    """GET version of /ask for easy browser testing."""
    return await ask_question(AskRequest(question=q))
