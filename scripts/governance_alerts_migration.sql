-- governance.alerts — operational alerts fired by Dagster sensors.
-- Day 3 (EXECUTION_HANDOFF §5.1). Two flavours surface here:
--   * source_freshness: bronze.*_live didn't get a new row inside its
--     freshness window — i.e. the replay simulator is stalled.
--   * dbt_test_failed: a dbt test inside `dbt test` returned a non-pass,
--     surfacing data-quality regressions.
--
-- These alerts are NOT customer-facing anomalies (those live as z-score
-- detections in /insights/alerts). They're plumbing alarms intended for
-- the on-call operator + the dashboard's Data Health page (Day 9).

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.alerts (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind          TEXT NOT NULL
        CHECK (kind IN ('source_freshness', 'dbt_test_failed', 'pipeline_error', 'manual')),
    severity      TEXT NOT NULL DEFAULT 'warning'
        CHECK (severity IN ('info', 'warning', 'critical')),
    source_ref    TEXT,    -- e.g. 'bronze.orders_live', 'fct_orders.unique_order_id'
    message       TEXT NOT NULL,
    details       JSONB,
    resolved_at   TIMESTAMPTZ,
    resolved_by   TEXT
);

CREATE INDEX IF NOT EXISTS alerts_created_at_idx
    ON governance.alerts (created_at DESC);

CREATE INDEX IF NOT EXISTS alerts_unresolved_idx
    ON governance.alerts (created_at DESC) WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS alerts_kind_idx
    ON governance.alerts (kind, severity);
