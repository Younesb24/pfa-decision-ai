-- Day 12 — ingest source registry.
-- One row per uploaded file. The actual bytes live on disk (or S3 in prod)
-- under data/ingest/<source_id>/raw.<ext>; the registry stores what we know
-- about it: schema profile, row count, the user who uploaded it, and a
-- pointer to the dbt staging model name we would scaffold for it (the
-- scaffold itself is deferred — out of scope for Day 12).

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.source_registry (
    id                BIGSERIAL PRIMARY KEY,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    uploaded_by       BIGINT REFERENCES governance.users(id) ON DELETE SET NULL,
    original_filename TEXT NOT NULL,
    storage_path      TEXT NOT NULL,             -- relative to data/ingest/
    content_type      TEXT,
    size_bytes        BIGINT NOT NULL,
    row_count         INTEGER,
    column_count      INTEGER,
    schema_profile    JSONB NOT NULL,            -- [{name, dtype, null_pct, sample}]
    suggested_table   TEXT,                      -- e.g. 'stg_user_orders'
    status            TEXT NOT NULL DEFAULT 'profiled'  -- 'profiled' | 'modeled' | 'failed'
        CHECK (status IN ('profiled', 'modeled', 'failed')),
    error             TEXT
);

CREATE INDEX IF NOT EXISTS source_registry_uploaded_at_idx
    ON governance.source_registry (uploaded_at DESC);
