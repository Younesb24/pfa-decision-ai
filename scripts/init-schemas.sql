-- ============================================================
-- PFA Olist — PostgreSQL Schema Initialization
-- Medallion Architecture: bronze / silver / gold
-- ============================================================

-- Bronze: raw data exactly as CSV, no transformations
CREATE SCHEMA IF NOT EXISTS bronze;

-- Silver: cleaned, typed, deduplicated, FK-validated
CREATE SCHEMA IF NOT EXISTS silver;

-- Gold: star schema — facts + dimensions for analytics
CREATE SCHEMA IF NOT EXISTS gold;

-- Audit: decision logs, LLM traces, token usage
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================
-- BRONZE TABLES — mirror the 8 Olist CSV files
-- All columns TEXT to preserve raw data integrity
-- ============================================================

CREATE TABLE IF NOT EXISTS bronze.orders (
    order_id TEXT,
    customer_id TEXT,
    order_status TEXT,
    order_purchase_timestamp TEXT,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.order_items (
    order_id TEXT,
    order_item_id TEXT,
    product_id TEXT,
    seller_id TEXT,
    shipping_limit_date TEXT,
    price TEXT,
    freight_value TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.order_payments (
    order_id TEXT,
    payment_sequential TEXT,
    payment_type TEXT,
    payment_installments TEXT,
    payment_value TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.order_reviews (
    review_id TEXT,
    order_id TEXT,
    review_score TEXT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TEXT,
    review_answer_timestamp TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.products (
    product_id TEXT,
    product_category_name TEXT,
    product_name_lenght TEXT,
    product_description_lenght TEXT,
    product_photos_qty TEXT,
    product_weight_g TEXT,
    product_length_cm TEXT,
    product_height_cm TEXT,
    product_width_cm TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.sellers (
    seller_id TEXT,
    seller_zip_code_prefix TEXT,
    seller_city TEXT,
    seller_state TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.customers (
    customer_id TEXT,
    customer_unique_id TEXT,
    customer_zip_code_prefix TEXT,
    customer_city TEXT,
    customer_state TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

CREATE TABLE IF NOT EXISTS bronze.geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat TEXT,
    geolocation_lng TEXT,
    geolocation_city TEXT,
    geolocation_state TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

-- Product category name translation (supplementary table)
CREATE TABLE IF NOT EXISTS bronze.product_category_name_translation (
    product_category_name TEXT,
    product_category_name_english TEXT,
    _loaded_at TIMESTAMPTZ DEFAULT NOW(),
    _source_file TEXT
);

-- ============================================================
-- AUDIT TABLE — tracks every LLM interaction
-- ============================================================

CREATE TABLE IF NOT EXISTS audit.llm_interactions (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    user_query TEXT,
    generated_sql TEXT,
    sql_valid BOOLEAN,
    llm_response TEXT,
    model_used TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit.decisions (
    id SERIAL PRIMARY KEY,
    decision_type TEXT,
    description TEXT,
    recommended_action TEXT,
    data_sources TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    outcome TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
