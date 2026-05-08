"""
Sales Forecast — Exponential Smoothing + Trend Analysis
Predicts monthly order volume and revenue for the next 3 months.
Uses statsmodels Holt-Winters (additive seasonality).
Fallback from Prophet due to CmdStan backend issues on Windows.

Usage:
    python ml/train_forecast.py
"""

import os
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Config ──
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
    "user": os.getenv("POSTGRES_USER", "pfa"),
    "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
}

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)


def load_monthly_data() -> pd.DataFrame:
    """Load monthly aggregated data from Gold layer."""
    from sqlalchemy import create_engine
    engine = create_engine(
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )

    query = """
    SELECT
        date_trunc('month', order_date)::date as month,
        sum(total_orders) as total_orders,
        round(sum(total_gmv)::numeric, 2) as total_revenue,
        round(avg(aov)::numeric, 2) as avg_aov,
        round(avg(otif_rate)::numeric, 2) as avg_otif_rate
    FROM gold.agg_daily_ops_kpi
    GROUP BY 1
    HAVING sum(total_orders) > 0
    ORDER BY 1
    """

    df = pd.read_sql(query, engine)
    engine.dispose()
    return df


def train_forecast_model(series: pd.Series, model_name: str, periods: int = 3):
    """Train Holt-Winters exponential smoothing and forecast."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    # Remove incomplete last month
    series = series.iloc[:-1]

    print(f"\n   Training ExponentialSmoothing on {model_name}...")
    print(f"   Data points: {len(series)} months")

    # Holt-Winters with additive trend and seasonality
    # Need at least 2 * seasonal_periods data points
    # With ~23 months we use 6-month seasonality (semi-annual)
    seasonal_periods = 6 if len(series) >= 12 else None

    model = ExponentialSmoothing(
        series.values,
        trend="add",
        seasonal="add" if seasonal_periods else None,
        seasonal_periods=seasonal_periods,
    ).fit(optimized=True)

    # Forecast
    forecast = model.forecast(periods)

    # Backtest: last 3 months
    backtest_months = min(3, len(series) - 4)
    train = series.iloc[:-backtest_months]
    test = series.iloc[-backtest_months:]

    bt_seasonal = 6 if len(train) >= 12 else None
    bt_model = ExponentialSmoothing(
        train.values,
        trend="add",
        seasonal="add" if bt_seasonal else None,
        seasonal_periods=bt_seasonal,
    ).fit(optimized=True)

    bt_pred = bt_model.forecast(backtest_months)
    actual = test.values
    mape = np.mean(np.abs((actual - bt_pred) / actual)) * 100

    print(f"   Backtest MAPE ({backtest_months} months): {mape:.1f}%")

    return model, forecast, mape


def main():
    """Train forecast models for orders and revenue."""
    print("=" * 60)
    print("SALES FORECAST — Holt-Winters")
    print("=" * 60)

    print("\n1. Loading monthly data from Gold layer...")
    df = load_monthly_data()
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month").sort_index()
    print(f"   Months: {len(df)}")
    print(f"   Range: {df.index.min().strftime('%Y-%m')} to {df.index.max().strftime('%Y-%m')}")

    print("\n2. Training models...")

    # Model 1: Monthly order volume
    model_orders, fc_orders, mape_orders = train_forecast_model(
        df["total_orders"], "monthly_orders"
    )

    # Model 2: Monthly revenue
    model_rev, fc_rev, mape_revenue = train_forecast_model(
        df["total_revenue"], "monthly_revenue"
    )

    # Generate forecast dates
    last_month = df.index[-2]  # -2 because we removed incomplete last month
    forecast_dates = pd.date_range(start=last_month + pd.DateOffset(months=1), periods=3, freq="MS")

    # Print forecasts
    print("\n3. Next 3 months forecast:")
    print("\n   Orders:")
    for d, v in zip(forecast_dates, fc_orders):
        print(f"   {d.strftime('%Y-%m')}: {max(0, v):,.0f}")

    print("\n   Revenue (BRL):")
    for d, v in zip(forecast_dates, fc_rev):
        print(f"   {d.strftime('%Y-%m')}: R${max(0, v):,.0f}")

    # Save
    forecast_data = {
        "orders": {
            "forecast": [{"month": d.strftime("%Y-%m"), "value": max(0, float(v))} for d, v in zip(forecast_dates, fc_orders)],
            "mape": round(mape_orders, 2),
        },
        "revenue": {
            "forecast": [{"month": d.strftime("%Y-%m"), "value": max(0, float(v))} for d, v in zip(forecast_dates, fc_rev)],
            "mape": round(mape_revenue, 2),
        },
        "trained_at": datetime.now().isoformat(),
    }
    joblib.dump(forecast_data, os.path.join(MODEL_DIR, "forecast_results.joblib"))
    print("\n4. Results saved to ml/models/forecast_results.joblib")

    # Summary
    print(f"\n{'='*60}")
    print(f"MAPE Orders:  {mape_orders:.1f}% {'PASS (<= 20%)' if mape_orders <= 20 else 'NEEDS WORK'}")
    print(f"MAPE Revenue: {mape_revenue:.1f}% {'PASS (<= 20%)' if mape_revenue <= 20 else 'NEEDS WORK'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
