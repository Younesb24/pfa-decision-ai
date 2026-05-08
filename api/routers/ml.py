"""
ML endpoints — serves predictions from trained models.
- Late delivery prediction (XGBoost)
- Sales forecast (Holt-Winters)
"""

import os
from datetime import UTC, datetime

import joblib
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ml", "models")


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
