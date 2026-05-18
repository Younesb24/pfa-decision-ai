"""
ML endpoints — serves predictions from trained XGBoost models.

The /predict/late-delivery endpoint is the project's hero AI surface:
given a seller_id, it loads that seller's historical scorecard, fills the
rest of the feature vector with dataset medians (modelling "next typical
order"), runs the XGBoost classifier, and returns the late-delivery
probability plus the top contributing factors. Factor contributions use a
lightweight importance x deviation heuristic — SHAP would be more rigorous
but adds install weight; the heuristic is documented in the model card.
"""

import os
from datetime import UTC, datetime

import joblib
from db import query_gold_one
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ml", "models")

# Lazy cache — populated on first /predict call.
_MODEL_CACHE: dict | None = None


class MLMetrics(BaseModel):
    """Model performance metrics."""
    model: str
    f1_score: float | None = None
    roc_auc: float | None = None
    mape: float | None = None
    threshold: float | None = None
    trained_at: str


class ForecastPoint(BaseModel):
    month: str
    value: float


class ForecastResponse(BaseModel):
    orders: list[ForecastPoint]
    orders_mape: float
    revenue: list[ForecastPoint]
    revenue_mape: float


@router.get("/ml/metrics")
async def get_ml_metrics():
    """Returns performance metrics for all trained models."""
    metrics = {}

    # Late delivery model
    ld_path = os.path.join(ML_DIR, "late_delivery_metrics.joblib")
    if os.path.exists(ld_path):
        ld = joblib.load(ld_path)
        metrics["late_delivery"] = MLMetrics(
            model=ld["model"],
            f1_score=ld["f1_score"],
            roc_auc=ld["roc_auc"],
            threshold=ld.get("threshold"),
            trained_at=ld["trained_at"],
        )

    # Forecast model
    fc_path = os.path.join(ML_DIR, "forecast_results.joblib")
    if os.path.exists(fc_path):
        fc = joblib.load(fc_path)
        metrics["forecast"] = MLMetrics(
            model="Holt-Winters ExponentialSmoothing",
            mape=fc["orders"]["mape"],
            trained_at=fc["trained_at"],
        )

    return {
        "data": metrics,
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.get("/ml/forecast")
async def get_forecast():
    """Returns the 3-month sales and revenue forecast."""
    fc_path = os.path.join(ML_DIR, "forecast_results.joblib")
    if not os.path.exists(fc_path):
        return {"error": "No forecast model found. Run: python ml/train_forecast.py"}

    fc = joblib.load(fc_path)
    return {
        "data": ForecastResponse(
            orders=[ForecastPoint(**p) for p in fc["orders"]["forecast"]],
            orders_mape=fc["orders"]["mape"],
            revenue=[ForecastPoint(**p) for p in fc["revenue"]["forecast"]],
            revenue_mape=fc["revenue"]["mape"],
        ),
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ─── Late delivery prediction ───────────────────────────────────────────────
#
# Marketplace reference values used as the "typical order" baseline when
# computing per-feature contributions. Derived from EDA on the Olist Gold
# layer (~96K delivered orders). They serve two purposes:
#   1. Fill non-seller features when scoring a hypothetical "next order"
#      for a given seller — we model a representative order, not a real one.
#   2. Provide the centering point for the importance x deviation explanation
#      heuristic: a feature far from its baseline AND with high model
#      importance is shown as a top contributing factor.

REFERENCE_VALUES: dict[str, float] = {
    "price": 120.0,
    "freight_value": 20.0,
    "total_item_value": 140.0,
    "order_item_id": 1.0,
    "processing_time_days": 2.0,
    "freight_to_price_ratio": 0.20,
    "order_total_payment": 160.0,
    "product_weight_g": 800.0,
    "product_volume_cm3": 8000.0,
    "product_photos_qty": 2.0,
    "product_name_length": 50.0,
    "product_description_length": 600.0,
    "seller_late_rate": 8.0,
    "seller_avg_review": 4.0,
    "seller_total_orders": 50.0,
    "seller_risk": 30.0,
    "purchase_day_of_week": 3.0,
    "purchase_month": 6.0,
    "purchase_hour": 14.0,
    "is_weekend": 0.0,
    "is_holiday": 0.0,
    "payment_count": 1.0,
    "max_installments": 3.0,
    "cross_state": 0.0,
}

# Brazilian state names so the one-hot encoded features that survive the
# explanation step render in something a Moroccan jury can read. Olist is a
# Brazilian dataset; the codes are 2-letter UF abbreviations.
BR_STATE_NAMES: dict[str, str] = {
    "SP": "São Paulo",
    "RJ": "Rio de Janeiro",
    "MG": "Minas Gerais",
    "RS": "Rio Grande do Sul",
    "PR": "Paraná",
    "SC": "Santa Catarina",
    "BA": "Bahia",
    "DF": "Distrito Federal",
    "GO": "Goiás",
    "PE": "Pernambuco",
    "ES": "Espírito Santo",
    "CE": "Ceará",
}

# Human-readable labels surfaced in the top-factors UI. Anything not in this
# map falls back to the prefix-expanding logic in _human_label() — that keeps
# the response honest instead of silently dropping unknown features.
FEATURE_LABELS: dict[str, str] = {
    "seller_late_rate": "Historical late delivery rate",
    "seller_avg_review": "Average review score",
    "seller_risk": "Composite seller risk score",
    "seller_total_orders": "Seller order volume",
    "cross_state": "Cross-state shipping (seller ≠ customer)",
    "freight_to_price_ratio": "Freight cost relative to price",
    "processing_time_days": "Order processing time",
    "price": "Order price",
    "freight_value": "Freight cost",
    "product_weight_g": "Product weight",
    "product_volume_cm3": "Product volume",
    "is_weekend": "Weekend purchase",
    "is_holiday": "Holiday purchase",
    "payment_count": "Number of payment splits",
    "max_installments": "Maximum installments",
}


def _human_label(feature: str) -> str:
    """Render any feature name as a human-readable label.

    Handles three cases: explicit FEATURE_LABELS map; one-hot encoded state
    columns (`seller_is_SP`, `customer_is_RJ`) which get expanded with the
    Brazilian state name; everything else falls back to a title-cased
    underscore split.
    """
    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]
    for prefix, who in (("seller_is_", "Seller"), ("customer_is_", "Customer")):
        if feature.startswith(prefix):
            code = feature.removeprefix(prefix).upper()
            full = BR_STATE_NAMES.get(code)
            return f"{who} in {full} ({code})" if full else f"{who} in {code}"
    return feature.replace("_", " ").title()


class PredictLateDeliveryRequest(BaseModel):
    seller_id: str = Field(min_length=1, description="Olist seller_id to score")
    customer_state: str | None = Field(
        default=None,
        description="Destination state (2-letter code). Defaults to same as seller (no cross-state risk).",
    )


class FactorContribution(BaseModel):
    feature: str
    label: str
    value: float
    contribution_pct: float = Field(description="Relative contribution to the prediction, %")
    direction: str = Field(description="'increases' or 'decreases' the risk")


class PredictLateDeliveryResponse(BaseModel):
    seller_id: str
    probability: float
    threshold: float
    predicted_late: bool
    risk_label: str = Field(description="Forward-looking: risk of a typical NEXT order being late")
    historical_risk_label: str = Field(description="Backward-looking: derived from the scorecard composite")
    seller_context: dict
    top_factors: list[FactorContribution]
    recommendation: str
    model: dict


def _load_model() -> dict:
    """Lazy-load the XGBoost model. Cached after first hit."""
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        model_path = os.path.join(ML_DIR, "late_delivery_xgb.joblib")
        if not os.path.exists(model_path):
            raise HTTPException(
                status_code=503,
                detail="Late-delivery model not available. Train it with: python ml/train_late_delivery.py",
            )
        _MODEL_CACHE = joblib.load(model_path)
    return _MODEL_CACHE


def _fetch_seller_context(seller_id: str) -> dict:
    """Pull seller scorecard + state. 404 if the seller is unknown."""
    row = query_gold_one(
        """
        SELECT
            sc.seller_id,
            sc.total_orders,
            sc.late_delivery_rate,
            sc.avg_review_score,
            sc.seller_risk_score,
            ds.seller_state
        FROM gold.agg_seller_scorecard sc
        LEFT JOIN gold.dim_seller ds ON ds.seller_id = sc.seller_id
        WHERE sc.seller_id = %(sid)s
        """,
        {"sid": seller_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Seller not found: {seller_id}")
    return row


def _build_feature_vector(features: list[str], seller: dict, customer_state: str | None) -> list[float]:
    """Construct the feature vector in the exact order the model expects.

    Seller-specific features come from the scorecard; order-specific features
    use marketplace reference values; one-hot state encodings are derived
    from the seller's state and the (optional) customer state.
    """
    seller_state = (seller.get("seller_state") or "SP").upper()
    cust_state = (customer_state or seller_state).upper()

    overrides: dict[str, float] = {
        "seller_late_rate": float(seller["late_delivery_rate"] or 0),
        "seller_avg_review": float(seller["avg_review_score"] or 0),
        "seller_total_orders": float(seller["total_orders"] or 0),
        "seller_risk": float(seller["seller_risk_score"] or 0),
        "cross_state": 1.0 if seller_state != cust_state else 0.0,
    }

    vector: list[float] = []
    for feat in features:
        if feat in overrides:
            vector.append(overrides[feat])
        elif feat.startswith("seller_is_"):
            state = feat.removeprefix("seller_is_").upper()
            vector.append(1.0 if seller_state == state else 0.0)
        elif feat.startswith("customer_is_"):
            state = feat.removeprefix("customer_is_").upper()
            vector.append(1.0 if cust_state == state else 0.0)
        else:
            vector.append(REFERENCE_VALUES.get(feat, 0.0))
    return vector


def _explain(features: list[str], vector: list[float], importances) -> list[FactorContribution]:
    """Top-3 factor attribution via importance x normalized-deviation.

    For each feature, score = importance * |value - reference| / max(|reference|, 1).
    Direction is signed by whether the feature is above (increases) or below
    (decreases) its reference. This is not SHAP — it is a transparent,
    cheap-to-compute heuristic documented in the model card.
    """
    contributions: list[tuple[str, float, float, str]] = []
    for feat, val, imp in zip(features, vector, importances, strict=True):
        ref = REFERENCE_VALUES.get(feat, 0.0)
        scale = max(abs(ref), 1.0)
        deviation = (val - ref) / scale
        score = float(imp) * abs(deviation)
        if score <= 0:
            continue
        direction = "increases" if deviation > 0 else "decreases"
        contributions.append((feat, val, score, direction))

    if not contributions:
        return []

    total = sum(s for _, _, s, _ in contributions) or 1.0
    contributions.sort(key=lambda t: t[2], reverse=True)
    top = contributions[:3]

    return [
        FactorContribution(
            feature=feat,
            label=_human_label(feat),
            value=round(float(val), 4),
            contribution_pct=round(score / total * 100, 1),
            direction=direction,
        )
        for feat, val, score, direction in top
    ]


def _risk_label(p: float, threshold: float) -> str:
    if p >= max(threshold, 0.5):
        return "high"
    if p >= threshold * 0.6:
        return "medium"
    return "low"


def _historical_risk_label(seller: dict) -> str:
    """Backward-looking risk derived from the scorecard. Matches the colour
    logic the Seller Risk Scorecard uses on the dashboard so the two surfaces
    cannot contradict each other visually."""
    late_pct = float(seller.get("late_delivery_rate") or 0)
    review = float(seller.get("avg_review_score") or 0)
    risk = float(seller.get("seller_risk_score") or 0)
    if late_pct > 20 or risk > 50 or review < 3:
        return "high"
    if late_pct > 10 or risk > 30 or review < 4:
        return "medium"
    return "low"


def _recommendation(seller: dict, probability: float, predicted_label: str, historical_label: str) -> str:
    """Concrete action phrased for an ops manager — no generic consulting filler.

    Cross-references the *historical* risk (scorecard composite) with the
    *predicted* probability for a typical next order. The two can diverge: a
    seller with a poor track record can still get a low prediction under safe
    default conditions (same-state, typical product). The recommendation
    surfaces that nuance instead of papering over it.
    """
    late_pct = float(seller.get("late_delivery_rate") or 0)
    review = float(seller.get("avg_review_score") or 0)
    sid_short = str(seller["seller_id"])[:8]

    # Both signals red — clear call to act.
    if historical_label == "high" and predicted_label in ("high", "medium"):
        return (
            f"Contact seller {sid_short}... before the next batch ships. "
            f"History is poor ({late_pct:.1f}% late rate, {review:.1f}/5 review) "
            f"and the model predicts {probability:.0%} probability for a typical "
            f"next order — consider routing through a faster carrier or adding "
            f"2 days of buffer to the estimated delivery date."
        )

    # History bad but prediction low — the divergence case the user just hit.
    # Be explicit about it instead of hiding behind the prediction.
    if historical_label == "high":
        return (
            f"Watch seller {sid_short}... — historical late rate of {late_pct:.1f}% "
            f"is well above the 8% marketplace baseline, even though a typical "
            f"next order predicts only {probability:.0%}. The prediction assumes "
            f"safe defaults (same-state, average product); monitor any cross-state "
            f"or heavy-item shipments closely."
        )

    # Prediction elevated but history clean — flag the unusual scenario.
    if predicted_label == "high":
        return (
            f"Unusual — seller {sid_short}... has clean history ({late_pct:.1f}% "
            f"late, {review:.1f}/5) but the model predicts {probability:.0%} for a "
            f"typical next order. Check whether order conditions changed."
        )

    if predicted_label == "medium" or historical_label == "medium":
        return (
            f"Monitor seller {sid_short}... — predicted {probability:.0%} late, "
            f"historical {late_pct:.1f}%. Flag for the weekly seller-ops review."
        )

    return (
        f"No immediate action — seller {sid_short}... clean history "
        f"({late_pct:.1f}% late, {review:.1f}/5) and {probability:.0%} predicted "
        f"probability on a typical next order."
    )


@router.post("/ml/predict/late-delivery", response_model=PredictLateDeliveryResponse)
async def predict_late_delivery(req: PredictLateDeliveryRequest):
    """Score a representative next order for a given seller.

    Returns the late-delivery probability, the model's tuned decision threshold,
    a low/medium/high label, the top-3 contributing factors, and an actionable
    recommendation. The seller_context block surfaces the raw scorecard fields
    so the UI can show evidence alongside the prediction.
    """
    bundle = _load_model()
    model = bundle["model"]
    features: list[str] = bundle["features"]
    threshold = float(bundle.get("threshold", 0.5))

    seller = _fetch_seller_context(req.seller_id)
    vector = _build_feature_vector(features, seller, req.customer_state)

    proba = float(model.predict_proba([vector])[0][1])
    top_factors = _explain(features, vector, model.feature_importances_)
    predicted_label = _risk_label(proba, threshold)
    historical_label = _historical_risk_label(seller)

    return PredictLateDeliveryResponse(
        seller_id=req.seller_id,
        probability=round(proba, 4),
        threshold=round(threshold, 4),
        predicted_late=bool(proba >= threshold),
        risk_label=predicted_label,
        historical_risk_label=historical_label,
        seller_context={
            "state": seller.get("seller_state"),
            "total_orders": int(seller.get("total_orders") or 0),
            "late_delivery_rate_pct": float(seller.get("late_delivery_rate") or 0),
            "avg_review_score": float(seller.get("avg_review_score") or 0),
            "seller_risk_score": float(seller.get("seller_risk_score") or 0),
        },
        top_factors=top_factors,
        recommendation=_recommendation(seller, proba, predicted_label, historical_label),
        model={
            "name": "XGBClassifier",
            "n_features": len(features),
            "threshold": round(threshold, 4),
        },
    )
