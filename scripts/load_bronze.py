"""
Bronze Layer Loader — Olist Brazilian E-Commerce
Loads all 8 CSV files into PostgreSQL bronze schema.
Idempotent: truncates before loading (safe to re-run).
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# ── Configuration ──
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
    "user": os.getenv("POSTGRES_USER", "pfa"),
    "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
}

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# Mapping: CSV filename (without extension) → bronze table name
CSV_TO_TABLE: dict[str, str] = {
    "olist_orders_dataset": "orders",
    "olist_order_items_dataset": "order_items",
    "olist_order_payments_dataset": "order_payments",
    "olist_order_reviews_dataset": "order_reviews",
    "olist_products_dataset": "products",
    "olist_sellers_dataset": "sellers",
    "olist_customers_dataset": "customers",
    "olist_geolocation_dataset": "geolocation",
    "product_category_name_translation": "product_category_name_translation",
}

# Columns per bronze table (excluding _loaded_at and _source_file, added automatically)
TABLE_COLUMNS: dict[str, list[str]] = {
    "orders": [
        "order_id", "customer_id", "order_status",
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": [
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
    ],
    "order_payments": [
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value",
    ],
    "order_reviews": [
        "review_id", "order_id", "review_score",
        "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp",
    ],
    "products": [
        "product_id", "product_category_name",
        "product_name_lenght", "product_description_lenght",
        "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ],
    "sellers": [
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    ],
    "customers": [
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state",
    ],
    "geolocation": [
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
        "geolocation_city", "geolocation_state",
    ],
    "product_category_name_translation": [
        "product_category_name", "product_category_name_english",
    ],
}


def load_csv_to_bronze(conn, csv_path: Path, table_name: str) -> int:
    """Load a single CSV file into a bronze table. Returns row count."""
    columns = TABLE_COLUMNS[table_name]
    source_file = csv_path.name
    loaded_at = datetime.now(UTC).isoformat()

    # Read CSV — all columns as string to preserve raw data
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

    # Validate expected columns exist
    missing = set(columns) - set(df.columns)
    if missing:
        print(f"  ⚠️  Missing columns in {csv_path.name}: {missing}")
        # Add missing columns as empty strings
        for col in missing:
            df[col] = ""

    # Select only expected columns (ignore extras)
    df = df[columns]

    # Add metadata columns
    df["_loaded_at"] = loaded_at
    df["_source_file"] = source_file

    all_columns = columns + ["_loaded_at", "_source_file"]

    with conn.cursor() as cur:
        # Truncate for idempotency
        cur.execute(f"TRUNCATE TABLE bronze.{table_name}")

        # Bulk insert
        values = [tuple(row) for row in df[all_columns].values]
        insert_sql = f"""
            INSERT INTO bronze.{table_name} ({', '.join(all_columns)})
            VALUES %s
        """
        execute_values(cur, insert_sql, values, page_size=5000)

    conn.commit()
    return len(df)


def main():
    """Main loader: iterate over all CSVs and load to bronze."""
    print("=" * 60)
    print("🔶 BRONZE LOADER — Olist E-Commerce")
    print("=" * 60)

    # Check data directory
    if not DATA_DIR.exists():
        print(f"\n❌ Data directory not found: {DATA_DIR}")
        print("   Download Olist dataset from Kaggle and place CSVs in data/raw/")
        print("   https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        sys.exit(1)

    csv_files = list(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"\n❌ No CSV files found in {DATA_DIR}")
        sys.exit(1)

    print(f"\n📂 Found {len(csv_files)} CSV files in {DATA_DIR}")

    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    total_rows = 0
    loaded_tables = 0
    skipped = []

    for csv_path in sorted(csv_files):
        stem = csv_path.stem
        if stem not in CSV_TO_TABLE:
            skipped.append(csv_path.name)
            continue

        table_name = CSV_TO_TABLE[stem]
        print(f"\n  📄 {csv_path.name}")
        print(f"     → bronze.{table_name}", end=" ... ")

        try:
            count = load_csv_to_bronze(conn, csv_path, table_name)
            print(f"✅ {count:,} rows")
            total_rows += count
            loaded_tables += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print(f"   Tables loaded: {loaded_tables}/{len(CSV_TO_TABLE)}")
    print(f"   Total rows:    {total_rows:,}")
    if skipped:
        print(f"   Skipped files:  {', '.join(skipped)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
