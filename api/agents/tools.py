"""
Tool registry for the Decision Analyst agent.

Each entry has:
  - A provider-neutral JSON Schema ("parameters" key) used for both Anthropic
    (converted to "input_schema") and OpenAI (wrapped in {"type":"function"}).
  - A Python callable that queries only the Gold layer.

call_tool(name, arguments) is the single dispatch point used by
decision_analyst.py — it handles errors and returns (result, row_count).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from db import query_gold, query_gold_one

# ── Provider-neutral tool schemas ─────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_kpi_summary",
        "description": (
            "Returns aggregated KPI summary (total orders, GMV, AOV, OTIF rate, "
            "cancellation rate, active sellers) for a date range. "
            "Use when the question is about overall performance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": "ISO date (YYYY-MM-DD). Defaults to 30 days before latest data.",
                },
                "end": {
                    "type": "string",
                    "description": "ISO date (YYYY-MM-DD). Defaults to latest data date.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_kpi_timeseries",
        "description": (
            "Returns daily KPI rows (order_date, total_orders, total_gmv, otif_rate, "
            "cancellation_rate, aov, active_sellers) for trend analysis. "
            "Use for 'how has X changed over time' questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
                "end": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return. Defaults to 30.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_anomalies",
        "description": (
            "Detects anomaly alerts via z-score on daily KPI metrics. "
            "Use for 'what dropped / spiked' questions or to explain alerts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": (
                        "Filter by metric name: otif_rate, cancellation_rate, "
                        "total_orders, total_gmv, aov. Leave empty for all metrics."
                    ),
                },
                "days": {
                    "type": "integer",
                    "description": "Look-back window in days. Defaults to 30.",
                },
                "min_z": {
                    "type": "number",
                    "description": "Minimum absolute z-score to include. Defaults to 2.0.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_seller_risk",
        "description": (
            "Returns top sellers ranked by risk score (0-100, higher = riskier), "
            "computed from late_delivery_rate, cancellation_rate, avg_review_score. "
            "Use for seller health, logistics, or escalation questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of sellers to return. Defaults to 10.",
                },
                "min_orders": {
                    "type": "integer",
                    "description": "Minimum total orders to filter noise. Defaults to 5.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_revenue_by_category",
        "description": (
            "Returns total revenue and order count broken down by product category. "
            "Use for category performance, product mix, or revenue mix questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
                "end": {"type": "string", "description": "ISO date (YYYY-MM-DD)."},
                "limit": {
                    "type": "integer",
                    "description": "Number of categories to return. Defaults to 10.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_recent_alerts",
        "description": (
            "Returns unresolved governance alerts (source freshness failures, "
            "dbt test failures) from governance.alerts. "
            "Use when diagnosing pipeline or data quality issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of alerts to return. Defaults to 5.",
                },
            },
            "required": [],
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────


def _serialize(rows: list[dict]) -> list[dict]:
    """Coerce psycopg2 Decimal/date/datetime to JSON-safe Python types."""
    out = []
    for row in rows:
        clean: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            elif hasattr(v, "__float__") and not isinstance(v, (bool, str)):
                try:
                    clean[k] = round(float(v), 4)
                except Exception:
                    clean[k] = str(v)
            else:
                clean[k] = v
        out.append(clean)
    return out


def _get_kpi_summary(start: str | None = None, end: str | None = None) -> dict:
    row = query_gold_one(
        """
        SELECT
            MIN(order_date)::text                        AS period_start,
            MAX(order_date)::text                        AS period_end,
            SUM(total_orders)::bigint                    AS total_orders,
            ROUND(SUM(total_gmv)::numeric, 2)            AS total_gmv,
            ROUND(AVG(aov)::numeric, 2)                  AS avg_order_value,
            ROUND(AVG(otif_rate)::numeric, 2)            AS otif_rate,
            ROUND(AVG(cancellation_rate)::numeric, 2)    AS cancellation_rate,
            MAX(active_sellers)::int                     AS peak_active_sellers
        FROM gold.agg_daily_ops_kpi
        WHERE (%(start)s IS NULL OR order_date >= %(start)s::date)
          AND (%(end)s   IS NULL OR order_date <= %(end)s::date)
        """,
        {"start": start, "end": end},
    )
    return dict(row) if row else {}


def _get_kpi_timeseries(
    start: str | None = None,
    end: str | None = None,
    limit: int = 30,
) -> list[dict]:
    rows = query_gold(
        """
        SELECT
            order_date::text,
            total_orders,
            ROUND(total_gmv::numeric, 2)          AS total_gmv,
            ROUND(aov::numeric, 2)                AS aov,
            ROUND(otif_rate::numeric, 2)          AS otif_rate,
            ROUND(cancellation_rate::numeric, 2)  AS cancellation_rate,
            active_sellers
        FROM gold.agg_daily_ops_kpi
        WHERE (%(start)s IS NULL OR order_date >= %(start)s::date)
          AND (%(end)s   IS NULL OR order_date <= %(end)s::date)
        ORDER BY order_date DESC
        LIMIT %(limit)s
        """,
        {"start": start, "end": end, "limit": limit},
    )
    return _serialize(rows)


def _get_anomalies(
    metric: str | None = None,
    days: int = 30,
    min_z: float = 2.0,
) -> list[dict]:
    """Z-score anomaly detection on daily KPI metrics.

    col is validated against a fixed allowlist before interpolation — safe
    from SQL injection. days/min_z are typed int/float.
    """
    metric_cols = ["otif_rate", "cancellation_rate", "total_orders", "total_gmv", "aov"]
    cols = [metric] if (metric and metric in metric_cols) else metric_cols

    results: list[dict] = []
    for col in cols:
        sql = f"""
            WITH window_data AS (
                SELECT
                    order_date::text AS order_date,
                    {col}::numeric   AS value
                FROM gold.agg_daily_ops_kpi
                WHERE order_date >= (
                    SELECT MAX(order_date) - ({days} * INTERVAL '1 day')
                    FROM gold.agg_daily_ops_kpi
                )
            ),
            stats AS (
                SELECT AVG(value) AS mean_val, STDDEV(value) AS stddev_val
                FROM window_data
            ),
            scored AS (
                SELECT
                    order_date,
                    '{col}' AS metric_name,
                    value,
                    CASE WHEN s.stddev_val > 0
                         THEN ROUND((value - s.mean_val) / s.stddev_val, 2)
                         ELSE 0
                    END AS z_score
                FROM window_data, stats s
            )
            SELECT * FROM scored
            WHERE ABS(z_score) >= {min_z}
            ORDER BY ABS(z_score) DESC
            LIMIT 10
        """
        rows = query_gold(sql)
        results.extend(_serialize(rows))

    results.sort(key=lambda r: abs(r.get("z_score", 0) or 0), reverse=True)
    return results[:20]


def _get_seller_risk(limit: int = 10, min_orders: int = 5) -> list[dict]:
    rows = query_gold(
        """
        SELECT
            seller_id,
            total_orders,
            ROUND(total_revenue::numeric, 2)       AS total_revenue,
            ROUND(late_delivery_rate::numeric, 2)  AS late_delivery_rate,
            ROUND(cancellation_rate::numeric, 2)   AS cancellation_rate,
            ROUND(avg_review_score::numeric, 2)    AS avg_review_score,
            ROUND(seller_risk_score::numeric, 2)   AS seller_risk_score
        FROM gold.agg_seller_scorecard
        WHERE total_orders >= %(min_orders)s
        ORDER BY seller_risk_score DESC
        LIMIT %(limit)s
        """,
        {"limit": limit, "min_orders": min_orders},
    )
    return _serialize(rows)


def _get_revenue_by_category(
    start: str | None = None,
    end: str | None = None,
    limit: int = 10,
) -> list[dict]:
    rows = query_gold(
        """
        SELECT
            p.product_category_name                     AS category,
            COUNT(DISTINCT o.order_id)                  AS total_orders,
            ROUND(SUM(o.total_item_value)::numeric, 2)  AS total_revenue
        FROM gold.fct_orders o
        JOIN gold.dim_product p USING (product_key)
        WHERE p.product_category_name IS NOT NULL
          AND (%(start)s IS NULL OR o.order_purchase_at::date >= %(start)s::date)
          AND (%(end)s   IS NULL OR o.order_purchase_at::date <= %(end)s::date)
        GROUP BY p.product_category_name
        ORDER BY total_revenue DESC
        LIMIT %(limit)s
        """,
        {"start": start, "end": end, "limit": limit},
    )
    return _serialize(rows)


def _get_recent_alerts(limit: int = 5) -> list[dict]:
    try:
        rows = query_gold(
            """
            SELECT
                id,
                created_at::text,
                kind,
                severity,
                source_ref,
                LEFT(message, 200) AS message,
                resolved_at::text
            FROM governance.alerts
            WHERE resolved_at IS NULL
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
        return _serialize(rows)
    except Exception:
        return []


# ── Dispatch map ───────────────────────────────────────────────────────────────

_TOOL_FN_MAP: dict[str, Any] = {
    "get_kpi_summary": _get_kpi_summary,
    "get_kpi_timeseries": _get_kpi_timeseries,
    "get_anomalies": _get_anomalies,
    "get_seller_risk": _get_seller_risk,
    "get_revenue_by_category": _get_revenue_by_category,
    "get_recent_alerts": _get_recent_alerts,
}


def call_tool(name: str, arguments: dict) -> tuple[Any, int]:
    """
    Dispatch a tool call by name. Returns (result, row_count).
    Raises KeyError for unknown tools — the caller should log and continue.
    """
    fn = _TOOL_FN_MAP.get(name)
    if fn is None:
        raise KeyError(f"Unknown tool: {name!r}")

    # Filter None values so optional params use their defaults
    clean_args = {k: v for k, v in arguments.items() if v is not None}
    result = fn(**clean_args)

    if isinstance(result, list):
        return result, len(result)
    if isinstance(result, dict):
        return result, 1
    return result, 0
