"""
KPI endpoints — serves pre-computed Gold layer metrics.
All computations are deterministic (no LLM). LLM = narrator only.
Source of truth: agent_docs/kpi_catalog.md
"""

from datetime import UTC, datetime
from typing import Literal

from db import query_gold, query_gold_one
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ── Personas ──
# Same data, different emphasis. See docs/adr/004-single-dataset-scope.md.

Persona = Literal["ops", "finance", "supply"]
ALLOWED_PERSONAS: tuple[Persona, ...] = ("ops", "finance", "supply")

PERSONA_HIGHLIGHT_KPIS: dict[str, list[str]] = {
    "ops": ["otif_rate", "cancellation_rate", "active_sellers"],
    "finance": ["total_revenue", "avg_order_value", "nps_proxy"],
    "supply": ["otif_rate", "active_sellers", "unique_customers"],
}


def _normalize_persona(value: str | None) -> Persona:
    return value if value in ALLOWED_PERSONAS else "ops"  # type: ignore[return-value]


# ── Pydantic DTOs ──

class KPISummary(BaseModel):
    """Top-level KPI summary for dashboard overview."""
    period_start: str
    period_end: str
    total_orders: int
    total_revenue: float = Field(description="Total GMV in BRL")
    avg_order_value: float = Field(description="AOV in BRL — KPI #2")
    otif_rate: float = Field(description="On-Time In-Full % — KPI #1, target >= 92%")
    nps_proxy: float = Field(description="(% score 4-5) - (% score 1-2) — KPI #3")
    cancellation_rate: float = Field(description="% canceled orders — KPI #4, alert > 5%")
    active_sellers: int
    unique_customers: int


class DailyKPI(BaseModel):
    """Single day of operational KPIs."""
    order_date: str
    total_orders: int
    total_gmv: float
    aov: float
    otif_rate: float | None
    cancellation_rate: float
    avg_delivery_delay_days: float | None
    active_sellers: int
    unique_customers: int


class SellerScorecard(BaseModel):
    """Seller risk assessment."""
    seller_id: str
    total_orders: int
    total_revenue: float
    late_delivery_rate: float
    avg_review_score: float
    seller_risk_score: float
    cancellation_rate: float


class KPIResponse(BaseModel):
    """Wrapper for all KPI responses."""
    data: object
    generated_at: str
    source: str = "gold.agg_daily_ops_kpi"
    persona: str | None = None
    highlighted_kpis: list[str] | None = None


# ── Endpoints ──

@router.get("/kpi/summary", response_model=KPIResponse)
async def get_kpi_summary(
    persona: str = Query(default="ops", description="ops | finance | supply — controls highlighted KPIs only"),
) -> KPIResponse:
    """
    Overall KPI summary across the entire dataset.
    Computes OTIF, AOV, NPS proxy, cancellation rate from Gold layer.

    The `persona` parameter does NOT change the numbers — same data for everyone.
    It only annotates which KPIs the frontend should emphasize for that role.
    """
    p = _normalize_persona(persona)
    summary = query_gold_one("""
        SELECT
            min(order_date)::text as period_start,
            max(order_date)::text as period_end,
            sum(total_orders) as total_orders,
            round(sum(total_gmv)::numeric, 2) as total_revenue,
            round((sum(total_gmv) / nullif(sum(total_orders), 0))::numeric, 2) as avg_order_value,
            round((sum(on_time_orders)::numeric / nullif(sum(delivered_orders), 0) * 100)::numeric, 2) as otif_rate,
            round((sum(canceled_orders)::numeric / nullif(sum(total_orders), 0) * 100)::numeric, 2) as cancellation_rate,
            sum(active_sellers) as active_sellers,
            sum(unique_customers) as unique_customers
        FROM gold.agg_daily_ops_kpi
    """)

    # NPS proxy from reviews
    nps = query_gold_one("""
        SELECT
            round(
                (count(*) filter (where review_score >= 4)::numeric / nullif(count(*), 0) * 100)
                - (count(*) filter (where review_score <= 2)::numeric / nullif(count(*), 0) * 100)
            , 2) as nps_proxy
        FROM gold.fct_reviews
    """)

    return KPIResponse(
        data=KPISummary(
            period_start=summary["period_start"],
            period_end=summary["period_end"],
            total_orders=summary["total_orders"],
            total_revenue=float(summary["total_revenue"]),
            avg_order_value=float(summary["avg_order_value"]),
            otif_rate=float(summary["otif_rate"]) if summary["otif_rate"] else 0,
            nps_proxy=float(nps["nps_proxy"]) if nps and nps["nps_proxy"] else 0,
            cancellation_rate=float(summary["cancellation_rate"]),
            active_sellers=summary["active_sellers"],
            unique_customers=summary["unique_customers"],
        ),
        generated_at=datetime.now(UTC).isoformat(),
        persona=p,
        highlighted_kpis=PERSONA_HIGHLIGHT_KPIS[p],
    )


@router.get("/kpi/daily")
async def get_daily_kpis(
    days: int = Query(default=30, ge=7, le=365, description="Number of recent days"),
) -> KPIResponse:
    """Daily KPI timeseries for dashboard charts."""
    rows = query_gold("""
        SELECT
            order_date::text,
            total_orders, total_gmv,
            round(aov::numeric, 2) as aov,
            otif_rate, cancellation_rate,
            round(avg_delivery_delay_days::numeric, 2) as avg_delivery_delay_days,
            active_sellers, unique_customers
        FROM gold.agg_daily_ops_kpi
        ORDER BY order_date DESC
        LIMIT %(days)s
    """, {"days": days})

    return KPIResponse(
        data=[DailyKPI(**row) for row in rows],
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.get("/kpi/sellers")
async def get_seller_scorecard(
    limit: int = Query(default=20, ge=5, le=100),
    min_orders: int = Query(default=10, ge=1),
) -> KPIResponse:
    """Top riskiest sellers by composite risk score (KPI #5)."""
    rows = query_gold("""
        SELECT
            seller_id, total_orders,
            round(total_revenue::numeric, 2) as total_revenue,
            late_delivery_rate,
            round(avg_review_score::numeric, 2) as avg_review_score,
            round(seller_risk_score::numeric, 2) as seller_risk_score,
            cancellation_rate
        FROM gold.agg_seller_scorecard
        WHERE total_orders >= %(min_orders)s
        ORDER BY seller_risk_score DESC
        LIMIT %(limit)s
    """, {"limit": limit, "min_orders": min_orders})

    return KPIResponse(
        data=[SellerScorecard(**row) for row in rows],
        generated_at=datetime.now(UTC).isoformat(),
        source="gold.agg_seller_scorecard",
    )


@router.get("/kpi/revenue-by-category")
async def get_revenue_by_category(
    top_n: int = Query(default=15, ge=5, le=50),
) -> KPIResponse:
    """Revenue breakdown by product category (KPI #6)."""
    rows = query_gold("""
        SELECT
            coalesce(p.product_category_name, 'unknown') as category,
            count(distinct f.order_id) as order_count,
            round(sum(f.total_item_value)::numeric, 2) as total_revenue,
            round(avg(f.total_item_value)::numeric, 2) as avg_item_value
        FROM gold.fct_orders f
        JOIN gold.dim_product p ON f.product_key = p.product_key
        GROUP BY 1
        ORDER BY total_revenue DESC
        LIMIT %(top_n)s
    """, {"top_n": top_n})

    return KPIResponse(
        data=[dict(r) for r in rows],
        generated_at=datetime.now(UTC).isoformat(),
        source="gold.fct_orders + gold.dim_product",
    )
