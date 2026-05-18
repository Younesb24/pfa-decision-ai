"""
LLM Narrative Generation + Anomaly Detection.

Provider: Anthropic Claude (preferred per CLAUDE.md), OpenAI GPT-4o as fallback.
The LLM never calculates — it only narrates the deterministic KPIs computed in
SQL. After generation, a Self-Critique pass verifies the narrative does not
introduce numbers that don't appear in the KPI context (cheap insurance against
hallucination, see ADR-001).

Personas (?persona=ops|finance|supply) reframe the same Olist data for
different stakeholders without re-architecting the pipeline (see ADR-004).
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, date, datetime
from typing import Literal

from db import log_audit, query_gold, query_gold_one
from fastapi import APIRouter, HTTPException, Query
from llm_client import complete, is_available
from pydantic import BaseModel

router = APIRouter()


def _validate_range(start: date | None, end: date | None) -> None:
    """Same shape as in kpi.py — reject inverted ranges with a 400."""
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=400,
            detail=f"start ({start}) must be <= end ({end})",
        )

Persona = Literal["ops", "finance", "supply"]
ALLOWED_PERSONAS: tuple[Persona, ...] = ("ops", "finance", "supply")


PERSONA_FRAMING: dict[str, dict[str, str]] = {
    "ops": {
        "role": "Head of E-commerce Operations",
        "focus": "OTIF, cancellation rate, seller risk, day-to-day operational health",
        "tone": "operational, weekly briefing style",
    },
    "finance": {
        "role": "Finance Director (DAF)",
        "focus": "GMV trend, AOV, revenue mix by category, financial impact of late deliveries",
        "tone": "financial, MoM/YoY framing, risk to top-line and margin",
    },
    "supply": {
        "role": "Supply Chain Director",
        "focus": "delivery delays, lead times, cross-state shipments, late-delivery seller concentration",
        "tone": "logistics-first, root-cause oriented",
    },
}


NARRATIVE_SYSTEM_TEMPLATE = """You are a decision analyst for Olist, a Brazilian e-commerce marketplace.
You write decision briefs for the {role}. Focus on: {focus}. Tone: {tone}.

You are a narrator, never a calculator. Every number in your brief MUST come
verbatim from the data context the user provides. Do not compute, estimate, or
infer numbers. The numeric facts are already trusted upstream.

Your brief MUST follow this exact structure with these exact headings:

**What changed**
One or two sentences naming the most important shift in the window —
prefer a comparison ("OTIF fell from X% to Y%") over a single static number.
If nothing material changed, say so explicitly.

**Why it matters**
One sentence connecting the shift to a business outcome the persona cares
about — revenue, customer trust, operational cost, marketplace health.

**Evidence**
2–3 short bullet points, each citing a specific number from the data context
and naming the seller/category/region/period it refers to. Do not restate the
full KPI table — only cite what supports the decision.

**Recommended action**
ONE concrete action a human can take this week. Name a specific subject
(seller id, category, region) when possible. Avoid generic verbs like
"investigate" or "monitor" unless paired with a specific target.

**Limitation**
One sentence on what this brief is not — e.g. "this brief reflects historical
KPIs; the late-delivery model would refine seller-specific risk." Keep it
honest, not promotional.

Hard constraints:
- Markdown only. Headings exactly as written above, bold.
- Under 200 words total.
- Never use the phrases "root cause analysis", "enhance collaboration",
  "leverage", "synergies", or other consulting filler.
- Never invent a seller id, category name, or number that isn't in the
  data context.
"""


CRITIQUE_SYSTEM = """You are a fact-checker. You receive a JSON `data_context` of allowed numbers and a `narrative`.
Your job: list any numeric claim in the narrative that does NOT appear in data_context.
Allow rounding to one decimal. Allow percentages computed trivially from the same numbers.
Do not flag qualitative phrasing like "elevated" or "on track" — only numeric claims.

Reply with strict JSON only, no prose, no fences:
{"valid": true|false, "issues": ["claim 1 not grounded", ...]}
"""


class NarrativeResponse(BaseModel):
    persona: str
    narrative: str
    data_context: dict
    self_critique: dict | None = None
    generated_at: str
    provider: str
    model: str


class AnomalyAlert(BaseModel):
    metric: str
    date: str
    value: float
    z_score: float
    direction: str   # "high" | "low"
    severity: str    # "warning" | "critical"


class AlertsResponse(BaseModel):
    alerts: list[AnomalyAlert]
    generated_at: str


# ── Helpers ──

def _gather_kpi_context(start: date | None = None, end: date | None = None) -> dict:
    """Pull the deterministic KPI bundle that grounds the narrative, optionally
    scoped to a date window. When start/end are None the legacy behaviour is
    preserved (full dataset).

    The trend block compares the requested window against an equal-length
    prior window — much more useful than the legacy "last 30 vs prior 30"
    when the user has picked a custom range."""
    params = {"start": start, "end": end}

    range_filter = """
        WHERE (%(start)s::date IS NULL OR order_date >= %(start)s::date)
          AND (%(end)s::date IS NULL OR order_date <= %(end)s::date)
    """
    summary = query_gold_one(f"""
        SELECT
            coalesce(sum(total_orders), 0)::bigint as total_orders,
            round(coalesce(sum(total_gmv), 0)::numeric, 2) as total_revenue,
            round((sum(total_gmv) / nullif(sum(total_orders), 0))::numeric, 2) as aov,
            round((sum(on_time_orders)::numeric / nullif(sum(delivered_orders), 0) * 100)::numeric, 2) as otif_rate,
            round((sum(canceled_orders)::numeric / nullif(sum(total_orders), 0) * 100)::numeric, 2) as cancel_rate,
            min(order_date)::text as period_start,
            max(order_date)::text as period_end
        FROM gold.agg_daily_ops_kpi
        {range_filter}
    """, params) or {}

    # Compare the user-picked window against the equal-length prior window.
    # When no range is given, fall back to the legacy "last 30 vs prior 30" framing.
    if start and end:
        trend = query_gold_one("""
            WITH window_days AS (
                SELECT (%(end)s::date - %(start)s::date + 1) AS days
            ),
            recent AS (
                SELECT avg(total_gmv) AS gmv, avg(total_orders) AS orders, avg(otif_rate) AS otif
                  FROM gold.agg_daily_ops_kpi
                 WHERE order_date BETWEEN %(start)s::date AND %(end)s::date
            ),
            prior AS (
                SELECT avg(total_gmv) AS gmv, avg(total_orders) AS orders, avg(otif_rate) AS otif
                  FROM gold.agg_daily_ops_kpi, window_days
                 WHERE order_date >= %(start)s::date - window_days.days * INTERVAL '1 day'
                   AND order_date <  %(start)s::date
            )
            SELECT
                round(recent.gmv::numeric, 2)    AS recent_avg_gmv,
                round(prior.gmv::numeric, 2)     AS prior_avg_gmv,
                round(recent.orders::numeric, 0) AS recent_avg_orders,
                round(prior.orders::numeric, 0)  AS prior_avg_orders,
                round(recent.otif::numeric, 2)   AS recent_otif,
                round(prior.otif::numeric, 2)    AS prior_otif
            FROM recent, prior
        """, params) or {}
    else:
        trend = query_gold_one("""
            WITH ranked AS (
                SELECT order_date, total_orders, total_gmv, otif_rate,
                       row_number() OVER (ORDER BY order_date DESC) as rn
                FROM gold.agg_daily_ops_kpi
            )
            SELECT
                round(avg(case when rn <= 30 then total_gmv end)::numeric, 2) as recent_avg_gmv,
                round(avg(case when rn > 30 and rn <= 60 then total_gmv end)::numeric, 2) as prior_avg_gmv,
                round(avg(case when rn <= 30 then total_orders end)::numeric, 0) as recent_avg_orders,
                round(avg(case when rn > 30 and rn <= 60 then total_orders end)::numeric, 0) as prior_avg_orders,
                round(avg(case when rn <= 30 then otif_rate end)::numeric, 2) as recent_otif,
                round(avg(case when rn > 30 and rn <= 60 then otif_rate end)::numeric, 2) as prior_otif
            FROM ranked WHERE rn <= 60
        """) or {}

    risky = query_gold("""
        SELECT seller_id, seller_risk_score, late_delivery_rate, avg_review_score
        FROM gold.agg_seller_scorecard
        WHERE total_orders >= 30
        ORDER BY seller_risk_score DESC LIMIT 3
    """)

    # NPS scoped to the same window using review_created_at (timestamp -> date).
    nps_range_filter = """
        WHERE (%(start)s::date IS NULL OR review_created_at::date >= %(start)s::date)
          AND (%(end)s::date IS NULL OR review_created_at::date <= %(end)s::date)
    """
    nps = query_gold_one(f"""
        SELECT
            round(avg(review_score)::numeric, 2) as avg_score,
            round((count(*) filter (where nps_category = 'detractor')::numeric / nullif(count(*), 0) * 100)::numeric, 1) as detractor_pct
        FROM gold.fct_reviews
        {nps_range_filter}
    """, params) or {}

    return {
        "summary": dict(summary),
        "trend": dict(trend),
        "top_risky_sellers": [dict(s) for s in risky],
        "nps": dict(nps),
        "window": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
    }


def _persona_user_prompt(persona: Persona, ctx: dict) -> str:
    s = ctx.get("summary", {})
    t = ctx.get("trend", {})
    n = ctx.get("nps", {})
    risky = ctx.get("top_risky_sellers", [])
    top = risky[0] if risky else {}
    return f"""Generate an executive summary for the {PERSONA_FRAMING[persona]['role']}.

DATA CONTEXT (the only numbers you may cite):
- Total orders: {s.get('total_orders', 'N/A')}
- Total revenue (BRL): {s.get('total_revenue', 'N/A')}
- AOV (BRL): {s.get('aov', 'N/A')}
- OTIF rate: {s.get('otif_rate', 'N/A')}% (target 92%)
- Cancellation rate: {s.get('cancel_rate', 'N/A')}%
- Recent 30d avg GMV (BRL): {t.get('recent_avg_gmv', 'N/A')} vs prior 30d: {t.get('prior_avg_gmv', 'N/A')}
- Recent 30d OTIF: {t.get('recent_otif', 'N/A')}% vs prior: {t.get('prior_otif', 'N/A')}%
- Avg review score: {n.get('avg_score', 'N/A')} / 5.0
- Detractor rate: {n.get('detractor_pct', 'N/A')}%
- Top risky seller: {str(top.get('seller_id', ''))[:8]}... risk={top.get('seller_risk_score', 'N/A')}, late={top.get('late_delivery_rate', 'N/A')}%

Focus on: what's working, what needs attention, recommended actions.
"""


def _self_critique(narrative: str, ctx: dict) -> dict:
    """Cheap fact-check. Returns {valid: bool, issues: [...]}.

    Best-effort: any failure (LLM error, invalid JSON) returns
    {"valid": null, "issues": ["self-critique unavailable"]} so the user-facing
    response is never blocked.
    """
    if not is_available():
        return {"valid": None, "issues": ["self-critique unavailable: no LLM"]}

    try:
        result = complete(
            system=CRITIQUE_SYSTEM,
            user=f"data_context = {json.dumps(ctx, default=str)}\n\nnarrative = {narrative}",
            max_tokens=400,
            temperature=0.0,
        )
        text = result.text.strip()
        # tolerate fenced / prefixed JSON
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"valid": None, "issues": ["self-critique returned non-JSON"]}
        parsed = json.loads(m.group(0))
        return {
            "valid": bool(parsed.get("valid", False)),
            "issues": list(parsed.get("issues", [])),
        }
    except Exception as e:
        return {"valid": None, "issues": [f"self-critique error: {e}"]}


def _template_narrative(persona: Persona, ctx: dict) -> str:
    """Fallback briefing rendered without an LLM. Mirrors the structured
    decision format the LLM is asked to produce so the surface is consistent
    whether or not ANTHROPIC_API_KEY / OPENAI_API_KEY is set."""
    s = ctx.get("summary", {})
    t = ctx.get("trend", {})
    n = ctx.get("nps", {})
    risky = ctx.get("top_risky_sellers", [])
    top = risky[0] if risky else {}

    otif = float(s.get("otif_rate") or 0)
    on_target = otif >= 92
    role = PERSONA_FRAMING[persona]["role"]

    # Build the "what changed" line from the trend block if both windows exist.
    otif_change = ""
    if t.get("recent_otif") is not None and t.get("prior_otif") is not None:
        r_otif, p_otif = float(t["recent_otif"]), float(t["prior_otif"])
        delta = r_otif - p_otif
        otif_change = f"OTIF moved from {p_otif:.1f}% to {r_otif:.1f}% ({delta:+.1f} pts)."
    else:
        otif_change = f"OTIF at {otif:.1f}% (target ≥ 92%)."

    gmv_change = ""
    if t.get("recent_avg_gmv") and t.get("prior_avg_gmv"):
        r, p = float(t["recent_avg_gmv"]), float(t["prior_avg_gmv"])
        if p > 0:
            pct = ((r - p) / p) * 100
            gmv_change = f"Daily GMV {pct:+.1f}% vs the prior equal-length window."

    why = (
        "OTIF below target erodes customer trust and increases refund exposure."
        if not on_target
        else "Operational metrics within target — focus shifts to retention quality."
    )

    sid_short = str(top.get("seller_id", ""))[:8] if top else ""
    seller_evidence = (
        f"- Riskiest seller: `{sid_short}...` with late rate "
        f"{top.get('late_delivery_rate', 'N/A')}% and composite risk "
        f"{top.get('seller_risk_score', 'N/A')}."
        if top
        else "- No risky seller detected in this window."
    )

    action = (
        f"Contact seller `{sid_short}...` this week — late rate "
        f"{top.get('late_delivery_rate', 'N/A')}% is well above the marketplace baseline."
        if top and not on_target
        else "Hold operational changes for this window — no urgent intervention."
    )

    return f"""## Decision brief — {role}

**What changed**
{otif_change} {gmv_change}

**Why it matters**
{why}

**Evidence**
- Window totals: {s.get('total_orders', 0):,} orders, R${float(s.get('total_revenue', 0)):,.0f} GMV, AOV R${float(s.get('aov', 0)):.0f}.
- Customer signal: avg review {n.get('avg_score', 'N/A')}/5.0 with {n.get('detractor_pct', 'N/A')}% detractors.
{seller_evidence}

**Recommended action**
{action}

**Limitation**
This brief is generated from historical KPIs. To rank specific sellers by
forward-looking risk, open the seller scorecard and click a row to run the
XGBoost late-delivery model.
"""


# ── Endpoint: narrative ──

@router.get("/insights/narrative")
async def get_narrative(
    persona: str = Query(default="ops", description="ops | finance | supply"),
    start: date | None = Query(
        default=None,
        description="Narrate for this window (ISO date). Omit for full dataset.",
    ),
    end: date | None = Query(
        default=None,
        description="Window end (ISO date). Omit for full dataset.",
    ),
) -> NarrativeResponse:
    """Generate an executive narrative tailored to the requested persona,
    optionally scoped to a date window so the briefing reacts to the picker."""
    started = time.perf_counter()
    if persona not in ALLOWED_PERSONAS:
        persona = "ops"
    p: Persona = persona  # type: ignore[assignment]
    _validate_range(start, end)

    data_context = _gather_kpi_context(start=start, end=end)
    framing = PERSONA_FRAMING[p]
    system = NARRATIVE_SYSTEM_TEMPLATE.format(**framing)
    user = _persona_user_prompt(p, data_context)

    if not is_available():
        narrative = _template_narrative(p, data_context)
        provider, model = "template", "fallback"
        critique = {"valid": None, "issues": ["self-critique skipped: template fallback"]}
    else:
        try:
            result = complete(system=system, user=user, max_tokens=800, temperature=0.4)
            narrative = result.text
            provider, model = result.provider, result.model
            critique = _self_critique(narrative, data_context)
        except Exception as e:
            narrative = _template_narrative(p, data_context)
            provider, model = "template", f"fallback (LLM error: {str(e)[:80]})"
            critique = {"valid": None, "issues": ["self-critique skipped: LLM error"]}

    log_audit(
        endpoint="GET /api/v1/insights/narrative",
        persona=p,
        user_input=None,
        llm_provider=provider,
        llm_model=model,
        llm_output=narrative,
        data_context=data_context,
        self_critique=critique,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    return NarrativeResponse(
        persona=p,
        narrative=narrative,
        data_context=data_context,
        self_critique=critique,
        generated_at=datetime.now(UTC).isoformat(),
        provider=provider,
        model=model,
    )


# ── Endpoint: anomaly alerts ──

@router.get("/insights/alerts")
async def get_anomaly_alerts(
    start: date | None = Query(
        default=None,
        description="Restrict alerts to this window (ISO date). Omit = last 30 days.",
    ),
    end: date | None = Query(
        default=None,
        description="Window end (ISO date). Omit = last 30 days.",
    ),
) -> AlertsResponse:
    """Detect z-score anomalies in daily KPIs (|z| >= 2 = warning, >= 3 = critical).

    Stats (mean/stddev) are always computed across the FULL dataset — that's
    the population the daily values are measured against. Only the candidate
    `recent` window is filtered by start/end so the operator sees anomalies
    inside the date range they picked, not historical noise."""
    _validate_range(start, end)
    params = {"start": start, "end": end}

    rows = query_gold("""
        WITH stats AS (
            SELECT
                avg(total_orders) as mean_orders,
                stddev(total_orders) as std_orders,
                avg(total_gmv) as mean_gmv,
                stddev(total_gmv) as std_gmv,
                avg(otif_rate) as mean_otif,
                stddev(otif_rate) as std_otif,
                avg(cancellation_rate) as mean_cancel,
                stddev(cancellation_rate) as std_cancel
            FROM gold.agg_daily_ops_kpi
        ),
        recent AS (
            SELECT order_date, total_orders, total_gmv, otif_rate, cancellation_rate
              FROM gold.agg_daily_ops_kpi
             WHERE
                 CASE
                     WHEN %(start)s::date IS NOT NULL OR %(end)s::date IS NOT NULL THEN
                         (%(start)s::date IS NULL OR order_date >= %(start)s::date) AND
                         (%(end)s::date   IS NULL OR order_date <= %(end)s::date)
                     ELSE order_date >= (SELECT max(order_date) - INTERVAL '29 days'
                                           FROM gold.agg_daily_ops_kpi)
                 END
             ORDER BY order_date DESC
        )
        SELECT
            r.order_date::text,
            r.total_orders,
            r.total_gmv::float,
            r.otif_rate::float,
            r.cancellation_rate::float,
            round(((r.total_orders - s.mean_orders) / nullif(s.std_orders, 0))::numeric, 2) as z_orders,
            round(((r.total_gmv - s.mean_gmv) / nullif(s.std_gmv, 0))::numeric, 2) as z_gmv,
            round(((r.otif_rate - s.mean_otif) / nullif(s.std_otif, 0))::numeric, 2) as z_otif,
            round(((r.cancellation_rate - s.mean_cancel) / nullif(s.std_cancel, 0))::numeric, 2) as z_cancel
        FROM recent r, stats s
        ORDER BY r.order_date DESC
    """, params)

    alerts: list[AnomalyAlert] = []
    for row in rows:
        date = row["order_date"]
        checks = [
            ("total_orders", row.get("total_orders"), row.get("z_orders")),
            ("total_gmv", row.get("total_gmv"), row.get("z_gmv")),
            ("otif_rate", row.get("otif_rate"), row.get("z_otif")),
            ("cancellation_rate", row.get("cancellation_rate"), row.get("z_cancel")),
        ]
        for metric, value, z in checks:
            if z is None:
                continue
            z_val = float(z)
            if abs(z_val) >= 2:
                alerts.append(AnomalyAlert(
                    metric=metric,
                    date=date,
                    value=float(value) if value is not None else 0.0,
                    z_score=z_val,
                    direction="high" if z_val > 0 else "low",
                    severity="critical" if abs(z_val) >= 3 else "warning",
                ))

    alerts.sort(key=lambda a: (-1 if a.severity == "critical" else 0, a.date), reverse=True)

    return AlertsResponse(
        alerts=alerts[:20],
        generated_at=datetime.now(UTC).isoformat(),
    )
