-- Replay simulator state + bronze "_live" tables.
--
-- Day 2 (EXECUTION_HANDOFF §5.1). The replay simulator advances a single
-- `synthetic_today` cursor one day per run; each run pulls the slice of Olist
-- CSV history for that date, shifts timestamps so they look "now-ish", and
-- appends to bronze.*_live. These are SEPARATE from bronze.* (which is the
-- legacy one-shot load via load_bronze.py): Day 3 will UNION both layers in
-- the dbt sources so Gold sees a continuously growing dataset.
--
-- Idempotency: each row carries an `_ingest_run_id` so the simulator can
-- safely retry a failed run without double-inserting. The unique index on
-- (table_natural_key, _ingest_run_id) guards against that.

-- ── State cursor (one row total) ────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS replay;

CREATE TABLE IF NOT EXISTS replay.state (
    id                   SMALLINT PRIMARY KEY DEFAULT 1,
    synthetic_today      DATE NOT NULL,
    runs_completed       INTEGER NOT NULL DEFAULT 0,
    last_run_at          TIMESTAMPTZ,
    last_rows_ingested   INTEGER,
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO replay.state (id, synthetic_today)
VALUES (1, DATE '2017-01-01')
ON CONFLICT (id) DO NOTHING;


-- ── Per-run journal (one row per simulator invocation) ──────────────────

CREATE TABLE IF NOT EXISTS replay.run (
    run_id           BIGSERIAL PRIMARY KEY,
    synthetic_today  DATE NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    rows_orders      INTEGER NOT NULL DEFAULT 0,
    rows_items       INTEGER NOT NULL DEFAULT 0,
    rows_reviews     INTEGER NOT NULL DEFAULT 0,
    rows_payments    INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed', 'noop')),
    error            TEXT
);

CREATE INDEX IF NOT EXISTS replay_run_started_at_idx
    ON replay.run (started_at DESC);


-- ── Live bronze tables ───────────────────────────────────────────────────
-- Same column shapes as bronze.* but with replay metadata; timestamps are
-- TEXT to mirror the source (dbt staging handles casting).

CREATE TABLE IF NOT EXISTS bronze.orders_live (
    order_id                      TEXT NOT NULL,
    customer_id                   TEXT,
    order_status                  TEXT,
    order_purchase_timestamp      TEXT,
    order_approved_at             TEXT,
    order_delivered_carrier_date  TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT,
    _synthetic_date     DATE,
    _ingest_run_id      BIGINT REFERENCES replay.run(run_id) ON DELETE CASCADE,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS bronze_orders_live_pk
    ON bronze.orders_live (order_id, _ingest_run_id);
CREATE INDEX IF NOT EXISTS bronze_orders_live_synth_date_idx
    ON bronze.orders_live (_synthetic_date);

CREATE TABLE IF NOT EXISTS bronze.order_items_live (
    order_id            TEXT NOT NULL,
    order_item_id       TEXT NOT NULL,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TEXT,
    price               TEXT,
    freight_value       TEXT,
    _synthetic_date     DATE,
    _ingest_run_id      BIGINT REFERENCES replay.run(run_id) ON DELETE CASCADE,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS bronze_order_items_live_pk
    ON bronze.order_items_live (order_id, order_item_id, _ingest_run_id);

CREATE TABLE IF NOT EXISTS bronze.order_reviews_live (
    review_id              TEXT NOT NULL,
    order_id               TEXT,
    review_score           TEXT,
    review_comment_title   TEXT,
    review_comment_message TEXT,
    review_creation_date   TEXT,
    review_answer_timestamp TEXT,
    _synthetic_date        DATE,
    _ingest_run_id         BIGINT REFERENCES replay.run(run_id) ON DELETE CASCADE,
    _ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Olist's raw data legitimately has the same review_id attached to multiple
-- order_ids (one written review can be tied to several purchases), so the
-- natural key for idempotency is (review_id, order_id, _ingest_run_id).
-- See replay_simulator duplicate-key bug discovered on 2026-05-11.
DROP INDEX IF EXISTS bronze.bronze_order_reviews_live_pk;
CREATE UNIQUE INDEX IF NOT EXISTS bronze_order_reviews_live_pk
    ON bronze.order_reviews_live (review_id, order_id, _ingest_run_id);

CREATE TABLE IF NOT EXISTS bronze.order_payments_live (
    order_id              TEXT NOT NULL,
    payment_sequential    TEXT NOT NULL,
    payment_type          TEXT,
    payment_installments  TEXT,
    payment_value         TEXT,
    _synthetic_date       DATE,
    _ingest_run_id        BIGINT REFERENCES replay.run(run_id) ON DELETE CASCADE,
    _ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS bronze_order_payments_live_pk
    ON bronze.order_payments_live (order_id, payment_sequential, _ingest_run_id);
