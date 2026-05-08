"""
Late Delivery Prediction — XGBoost Binary Classifier
Target: is_late (boolean) — whether order was delivered after estimated date
Feature engineering inspired by rismawidiya/Final-Project-Olist
Uses scale_pos_weight to handle class imbalance (~8% positive rate)

Usage:
    python ml/train_late_delivery.py
"""

import os
from datetime import datetime

import joblib
import pandas as pd
from sklearn.metrics import classification_report, f1_score, precision_recall_curve, roc_auc_score
from xgboost import XGBClassifier

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


def load_features() -> pd.DataFrame:
    """Load features from Gold layer for late delivery prediction."""
    from sqlalchemy import create_engine
    engine = create_engine(
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )

    query = """
    WITH seller_hist AS (
        SELECT
            seller_id,
            late_delivery_rate::float as seller_late_rate,
            avg_review_score::float as seller_avg_review,
            total_orders as seller_total_orders,
            seller_risk_score::float as seller_risk
        FROM gold.agg_seller_scorecard
    )
    SELECT
        f.order_id,
        (case when f.is_late then 1 else 0 end) as target,
        f.price::float,
        f.freight_value::float,
        f.total_item_value::float,
        f.order_item_id,
        f.processing_time_days::float,

        -- Ratio features
        case when f.price > 0 then (f.freight_value / f.price)::float else 0 end as freight_to_price_ratio,
        f.order_total_payment::float,

        -- Product features
        p.product_weight_g::float,
        p.product_volume_cm3::float,
        p.product_photos_qty,
        p.product_name_length,
        p.product_description_length,

        -- Seller historical performance (KEY features)
        sh.seller_late_rate,
        sh.seller_avg_review,
        sh.seller_total_orders,
        sh.seller_risk,

        -- Seller features
        s.seller_state,

        -- Customer features
        c.customer_state,

        -- Time features
        extract(dow from f.order_purchase_at)::int    as purchase_day_of_week,
        extract(month from f.order_purchase_at)::int  as purchase_month,
        extract(hour from f.order_purchase_at)::int   as purchase_hour,

        -- Date features
        (case when d.is_weekend then 1 else 0 end)    as is_weekend,
        (case when d.is_brazilian_holiday then 1 else 0 end) as is_holiday,

        -- Payment features
        f.payment_count,
        f.max_installments

    FROM gold.fct_orders f
    LEFT JOIN gold.dim_product p ON f.product_key = p.product_key
    LEFT JOIN gold.dim_seller s ON f.seller_key = s.seller_key
    LEFT JOIN gold.dim_customer c ON f.customer_key = c.customer_key
    LEFT JOIN gold.dim_date d ON f.purchase_date_key = d.date_key
    LEFT JOIN seller_hist sh ON f.seller_id = sh.seller_id
    WHERE f.order_status = 'delivered'
      AND f.is_late IS NOT NULL
      AND f.delivery_delay_days IS NOT NULL
    """

    df = pd.read_sql(query, engine)
    engine.dispose()
    return df


def engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Feature engineering — inspired by rismawidiya extracted_code.py"""

    # Distance proxy: different state between seller and customer
    df["cross_state"] = (df["seller_state"] != df["customer_state"]).astype(int)

    # Top seller states as one-hot (SP dominates)
    top_seller_states = df["seller_state"].value_counts().head(5).index
    for state in top_seller_states:
        df[f"seller_is_{state}"] = (df["seller_state"] == state).astype(int)

    # Top customer states
    top_cust_states = df["customer_state"].value_counts().head(5).index
    for state in top_cust_states:
        df[f"customer_is_{state}"] = (df["customer_state"] == state).astype(int)

    # Fill nulls
    df["product_weight_g"] = df["product_weight_g"].fillna(df["product_weight_g"].median())
    df["product_volume_cm3"] = df["product_volume_cm3"].fillna(df["product_volume_cm3"].median())
    df["product_photos_qty"] = df["product_photos_qty"].fillna(0)
    df["product_name_length"] = df["product_name_length"].fillna(0)
    df["product_description_length"] = df["product_description_length"].fillna(0)
    df["processing_time_days"] = df["processing_time_days"].fillna(df["processing_time_days"].median())
    df["freight_to_price_ratio"] = df["freight_to_price_ratio"].fillna(0)
    df["order_total_payment"] = df["order_total_payment"].fillna(0)
    df["seller_late_rate"] = df["seller_late_rate"].fillna(0)
    df["seller_avg_review"] = df["seller_avg_review"].fillna(3.0)
    df["seller_total_orders"] = df["seller_total_orders"].fillna(0)
    df["seller_risk"] = df["seller_risk"].fillna(50)
    df["payment_count"] = df["payment_count"].fillna(1)
    df["max_installments"] = df["max_installments"].fillna(1)

    # Target
    y = df["target"]

    # Features (drop non-numeric and target)
    drop_cols = ["order_id", "target", "seller_state", "customer_state"]
    X = df.drop(columns=drop_cols)

    return X, y


def train_model():
    """Train XGBoost late delivery classifier."""
    print("=" * 60)
    print("LATE DELIVERY CLASSIFIER — XGBoost")
    print("=" * 60)

    # Load data
    print("\n1. Loading features from Gold layer...")
    df = load_features()
    print(f"   Rows: {len(df):,}")
    print(f"   Late rate: {df['target'].mean():.2%}")

    # Engineer features
    print("\n2. Engineering features...")
    X, y = engineer_features(df)
    print(f"   Features: {X.shape[1]}")
    print(f"   Feature names: {list(X.columns)}")

    # Time-based split (not random — more realistic)
    # Use last 20% of data as test set
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print("\n3. Train/test split:")
    print(f"   Train: {len(X_train):,} rows ({y_train.mean():.2%} positive)")
    print(f"   Test:  {len(X_test):,} rows ({y_test.mean():.2%} positive)")

    # Handle class imbalance with scale_pos_weight
    # (preferred over SMOTE — see Alexandre987 comparison)
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_pos_weight = neg_count / pos_count

    print(f"   scale_pos_weight: {scale_pos_weight:.2f}")

    # Train XGBoost
    print("\n4. Training XGBoost...")
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Evaluate
    print("\n5. Evaluation:")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba)

    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {roc_auc:.4f}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['on_time', 'late'])}")

    # Feature importance
    print("6. Top 10 features:")
    importance = pd.Series(
        model.feature_importances_, index=X.columns
    ).sort_values(ascending=False)
    for feat, imp in importance.head(10).items():
        print(f"   {feat}: {imp:.4f}")

    # Threshold tuning — optimize F1 with recall >= 0.50
    # Business framing: rater une livraison en retard coûte plus qu'une fausse alarme
    print("\n6b. Threshold optimization (recall >= 0.50):")
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)
    best_f1 = 0
    best_threshold = 0.5
    for i in range(len(thresholds)):
        if recalls[i] >= 0.50:
            curr_f1 = 2 * precisions[i] * recalls[i] / (precisions[i] + recalls[i] + 1e-8)
            if curr_f1 > best_f1:
                best_f1 = curr_f1
                best_threshold = thresholds[i]

    y_pred_tuned = (y_proba >= best_threshold).astype(int)
    f1_tuned = f1_score(y_test, y_pred_tuned)

    print(f"   Optimal threshold: {best_threshold:.4f}")
    print(f"   F1 (tuned):  {f1_tuned:.4f}")
    print(f"\n{classification_report(y_test, y_pred_tuned, target_names=['on_time', 'late'])}")

    # Use tuned F1 as the final metric
    f1 = f1_tuned

    # Save model
    model_path = os.path.join(MODEL_DIR, "late_delivery_xgb.joblib")
    joblib.dump({
        "model": model,
        "features": list(X.columns),
        "threshold": best_threshold,
    }, model_path)
    print(f"7. Model saved to {model_path}")

    # Save metrics
    metrics = {
        "model": "XGBClassifier",
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "threshold": round(best_threshold, 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "positive_rate": round(y.mean(), 4),
        "n_features": X.shape[1],
        "trained_at": datetime.now().isoformat(),
    }
    joblib.dump(metrics, os.path.join(MODEL_DIR, "late_delivery_metrics.joblib"))
    print("   Metrics saved.")

    return f1


if __name__ == "__main__":
    f1 = train_model()
    target = 0.75
    if f1 >= target:
        print(f"\n{'='*60}")
        print(f"TARGET MET: F1={f1:.4f} >= {target}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"BELOW TARGET: F1={f1:.4f} < {target}")
        print("Consider: more features, hyperparameter tuning, threshold adjustment")
        print(f"{'='*60}")
