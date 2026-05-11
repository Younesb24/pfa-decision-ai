"""
KPI endpoints — serves pre-computed Gold layer metrics.
All computations are deterministic (no LLM). LLM = narrator only.
Source of truth: agent_docs/kpi_catalog.md
"""

from datetime import UTC, date, datetime
from typing import Literal

from db import query_gold, query_gold_one
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


def _validate_range(start: date | None, end: date | None) -> None:
    """Reject inverted ranges early so the SQL layer never sees them."""
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=400,
            detail=f"start ({start}) must be <= end ({end})",
        )


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
    data_as_of: str | None = Field(
        default=None,
        description="max(order_date) in gold.agg_daily_ops_kpi — the actual data cutoff",
    )
    requested_start: str | None = Field(
        default=None,
        description="Echoed ?start= if provided, else null",
    )
    requested_end: str | None = Field(
        default=None,
        description="Echoed ?end= if provided, else null",
    )
    is_partial_period: bool = Field(
        default=False,
        description=(
            "True when the requested window extends beyond the actual data range "
            "(common for Olist replay/historical demos). UI should label the delta "
            "chip as 'partial period' rather than imply a recent collapse."
        ),
    )


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
    start: date | None = Query(
        default=None,
        description="Filter on order_date >= start (ISO date). Omit for full dataset.",
    ),
    end: date | None = Query(
        default=None,
        description="Filter on order_date <= end (ISO date). Omit for full dataset.",
    ),
) -> KPIResponse:
    """
    KPI summary for the requested window (or the full dataset if no window given).
    Computes OTIF, AOV, NPS proxy, cancellation rate from Gold layer.

    The `persona` parameter does NOT change the numbers — same data for everyone.
    It only annotates which KPIs the frontend should emphasize for that role.

    When `start`/`end` extend beyond the actual data range, `is_partial_period`
    flips to `true` so the UI can label deltas accordingly (Olist data ends
    around 2018-09; a window anchored on "today" otherwise looks like a crash).
    """
    p = _normalize_persona(persona)
    _validate_range(start, end)

    # Single window filter applied to both the ops aggregate and the NPS query.
    range_filter = """
        WHERE (%(start)s::date IS NULL OR order_date >= %(start)s::date)
          AND (%(end)s::date IS NULL OR order_date <= %(end)s::date)
    """
    params = {"start": start, "end": end}

    summary = query_gold_one(f"""
        SELECT
            min(order_date)::text as period_start,
            max(order_date)::text as period_end,
            coalesce(sum(total_orders), 0)::bigint as total_orders,
            coalesce(round(sum(total_gmv)::numeric, 2), 0) as total_revenue,
            round((sum(total_gmv) / nullif(sum(total_orders), 0))::numeric, 2) as avg_order_value,
            round((sum(on_time_orders)::numeric / nullif(sum(delivered_orders), 0) * 100)::numeric, 2) as otif_rate,
            round((sum(canceled_orders)::numeric / nullif(sum(total_orders), 0) * 100)::numeric, 2) as cancellation_rate,
            coalesce(sum(active_sellers), 0)::bigint as active_sellers,
            coalesce(sum(unique_customers), 0)::bigint as unique_customers
        FROM gold.agg_daily_ops_kpi
        {range_filter}
    """, params)

    # fct_reviews exposes review_created_at (timestamp); cast to date for window filter.
    nps_range_filter = """
        WHERE (%(start)s::date IS NULL OR review_created_at::date >= %(start)s::date)
          AND (%(end)s::date IS NULL OR review_created_at::date <= %(end)s::date)
    """
    nps = query_gold_one(f"""
        SELECT
            round(
                (count(*) filter (where review_score >= 4)::numeric / nullif(count(*), 0) * 100)
                - (count(*) filter (where review_score <= 2)::numeric / nullif(count(*), 0) * 100)
            , 2) as nps_proxy
        FROM gold.fct_reviews
        {nps_range_filter}
    """, params)

    # Dataset cutoff — used to detect "partial period" when the requested window
    # either extends past the data OR ends inside the source's data-thinning
    # tail. Olist's last 3 days fall from ~370 orders/day to 1 — windows ending
    # there would otherwise compute a misleading negative delta in the UI.
    # NOTE: psycopg2 treats `%` as the start of a format placeholder, so any
    # literal percent sign in the SQL (including comments) must be escaped as
    # `%%`. The SQL below has none — see commit notes if you re-introduce one.
    cutoff_row = query_gold_one("""
        WITH bounds AS (
            SELECT max(order_date) AS data_as_of,
                   max(order_date) - INTERVAL '30 days' AS look_back_30
              FROM gold.agg_daily_ops_kpi
        ),
        recent AS (
            SELECT k.order_date, k.total_orders
              FROM gold.agg_daily_ops_kpi k, bounds b
             WHERE k.order_date >= b.look_back_30
        ),
        median_calc AS (
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_orders) AS median_orders
              FROM recent
        )
        SELECT
            (SELECT data_as_of::text FROM bounds) AS data_as_of,
            -- First day (walking backwards from the cutoff) where daily volume
            -- is < one-quarter of the trailing-30 median. Anything from this
            -- day onwards is unreliable and gets the partial-period label.
            (
                SELECT min(r.order_date)::text
                  FROM recent r, median_calc m, bounds b
                 WHERE r.total_orders < 0.25 * m.median_orders
                   AND r.order_date >= b.data_as_of - INTERVAL '7 days'
            ) AS data_thinning_starts_at
    """)
    data_as_of = cutoff_row["data_as_of"] if cutoff_row else None
    thinning_starts = cutoff_row["data_thinning_starts_at"] if cutoff_row else None

    is_partial = bool(
        data_as_of
        and end is not None
        and (
            # Window extends past the actual cutoff
            end.isoformat() > data_as_of
            # OR window reaches into the data-thinning tail
            or (thinning_starts is not None and end.isoformat() >= thinning_starts)
        )
    )

    return KPIResponse(
        data=KPISummary(
            period_start=summary["period_start"] or (start.isoformat() if start else ""),
            period_end=summary["period_end"] or (end.isoformat() if end else ""),
            total_orders=summary["total_orders"] or 0,
            total_revenue=float(summary["total_revenue"] or 0),
            avg_order_value=float(summary["avg_order_value"] or 0),
            otif_rate=float(summary["otif_rate"]) if summary["otif_rate"] else 0,
            nps_proxy=float(nps["nps_proxy"]) if nps and nps["nps_proxy"] else 0,
            cancellation_rate=float(summary["cancellation_rate"] or 0),
            active_sellers=summary["active_sellers"] or 0,
            unique_customers=summary["unique_customers"] or 0,
            data_as_of=data_as_of,
            requested_start=start.isoformat() if start else None,
            requested_end=end.isoformat() if end else None,
            is_partial_period=is_partial,
        ),
        generated_at=datetime.now(UTC).isoformat(),
        persona=p,
        highlighted_kpis=PERSONA_HIGHLIGHT_KPIS[p],
    )


@router.get("/kpi/daily")
async def get_daily_kpis(
    days: int = Query(
        default=30,
        ge=7,
        le=365,
        description="Trailing N days from the data cutoff (ignored when start/end are set).",
    ),
    start: date | None = Query(
        default=None,
        description="Filter on order_date >= start (ISO date). Takes precedence over days.",
    ),
    end: date | None = Query(
        default=None,
        description="Filter on order_date <= end (ISO date). Takes precedence over days.",
    ),
) -> KPIResponse:
    """Daily KPI timeseries for dashboard charts.

    Two modes:
      * `start`/`end` set → return every day in [start, end].
      * neither set → return the trailing `days` rows (legacy behavior).
    """
    _validate_range(start, end)

    if start is not None or end is not None:
        rows = query_gold("""
            SELECT
                order_date::text,
                total_orders, total_gmv,
                round(aov::numeric, 2) as aov,
                otif_rate, cancellation_rate,
                round(avg_delivery_delay_days::numeric, 2) as avg_delivery_delay_days,
                active_sellers, unique_customers
            FROM gold.agg_daily_ops_kpi
            WHERE (%(start)s::date IS NULL OR order_date >= %(start)s::date)
              AND (%(end)s::date IS NULL OR order_date <= %(end)s::date)
            ORDER BY order_date ASC
        """, {"start": start, "end": end})
    else:
        rows = query_gold("""
            SELECT * FROM (
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
            ) recent
            ORDER BY order_date ASC
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
