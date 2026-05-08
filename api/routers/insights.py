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
from datetime import UTC, datetime
from typing import Literal

from db import log_audit, query_gold, query_gold_one
from fastapi import APIRouter, Query
from llm_client import complete, is_available
from pydantic import BaseModel

router = APIRouter()

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


NARRATIVE_SYSTEM_TEMPLATE = """You are a senior business analytics consultant for Olist, a Brazilian e-commerce marketplace.
You write executive-level insights for the {role}. Focus on: {focus}. Tone: {tone}.

Rules:
1. NEVER invent numbers — only reference numbers that appear in the data context below
2. Highlight anomalies and trends explicitly
3. Provide 2-3 actionable recommendations matched to this persona
4. Use markdown: bold for KPIs, bullet points for actions
5. Keep it under 300 words
6. Reference Brazilian-market context when relevant
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

def _gather_kpi_context() -> dict:
    """Pull the deterministic KPI bundle that grounds the narrative."""
    summary = query_gold_one("""
        SELECT
            sum(total_orders) as total_orders,
            round(sum(total_gmv)::numeric, 2) as total_revenue,
            round((sum(total_gmv) / nullif(sum(total_orders), 0))::numeric, 2) as aov,
            round((sum(on_time_orders)::numeric / nullif(sum(delivered_orders), 0) * 100)::numeric, 2) as otif_rate,
            round((sum(canceled_orders)::numeric / nullif(sum(total_orders), 0) * 100)::numeric, 2) as cancel_rate
        FROM gold.agg_daily_ops_kpi
    """) or {}

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

    nps = query_gold_one("""
        SELECT
            round(avg(review_score)::numeric, 2) as avg_score,
            round((count(*) filter (where nps_category = 'detractor')::numeric / count(*) * 100)::numeric, 1) as detractor_pct
        FROM gold.fct_reviews
    """) or {}

    return {
        "summary": dict(summary),
        "trend": dict(trend),
        "top_risky_sellers": [dict(s) for s in risky],
        "nps": dict(nps),
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
    s = ctx.get("summary", {})
    t = ctx.get("trend", {})
    n = ctx.get("nps", {})
    otif = float(s.get("otif_rate") or 0)
    otif_status = "**on track**" if otif >= 92 else "**below target**"
    role = PERSONA_FRAMING[persona]["role"]

    gmv_change = ""
    if t.get("recent_avg_gmv") and t.get("prior_avg_gmv"):
        r, p = float(t["recent_avg_gmv"]), float(t["prior_avg_gmv"])
        if p > 0:
            pct = ((r - p) / p) * 100
            gmv_change = f"{'+' if pct > 0 else ''}{pct:.1f}% vs prior 30 days"

    return f"""## Olist — Briefing for {role}

**Revenue:** R${float(s.get('total_revenue', 0)):,.0f} across **{s.get('total_orders', 0):,}** orders (AOV: R${float(s.get('aov', 0)):.0f}). {gmv_change}

**OTIF Rate:** {otif:.1f}% — {otif_status} (target ≥ 92%).

**Customer satisfaction:** Avg review {n.get('avg_score', 'N/A')}/5.0; {n.get('detractor_pct', 'N/A')}% detractors.

**Cancellation rate:** {s.get('cancel_rate', 'N/A')}%.

### Recommended actions
- {"Investigate top late-delivery sellers" if otif < 92 else "Maintain current logistics performance"}
- Monitor seller risk scorecard weekly for early intervention
- Track detractor reviews for product quality issues
"""


# ── Endpoint: narrative ──

@router.get("/insights/narrative")
async def get_narrative(
    persona: str = Query(default="ops", description="ops | finance | supply"),
) -> NarrativeResponse:
    """Generate an executive narrative tailored to the requested persona."""
    started = time.perf_counter()
    if persona not in ALLOWED_PERSONAS:
        persona = "ops"
    p: Persona = persona  # type: ignore[assignment]

    data_context = _gather_kpi_context()
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
async def get_anomaly_alerts() -> AlertsResponse:
    """Detect z-score anomalies in recent daily KPIs (|z| >= 2 = warning, >= 3 = critical)."""
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
            ORDER BY order_date DESC
            LIMIT 30
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
    """)

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
