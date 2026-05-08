-- Audit journal for AI governance.
-- Every LLM-touched request (text-to-SQL, narrative, alerts) is recorded here,
-- along with the data context that grounded it. Reviews close the OODA "Act"
-- loop: a human marks an alert/narrative as reviewed and (optionally) records
-- a decision.

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.audit_log (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    endpoint        TEXT NOT NULL,            -- e.g. 'POST /api/v1/ask'
    persona         TEXT,                     -- 'ops' | 'finance' | 'supply' | NULL
    user_input      TEXT,                     -- the natural-language question or trigger
    llm_provider    TEXT,                     -- 'anthropic' | 'openai' | 'template'
    llm_model       TEXT,
    llm_output      TEXT,                     -- raw text response (SQL, narrative, etc.)
    data_context    JSONB,                    -- the deterministic KPIs the LLM saw
    self_critique   JSONB,                    -- {valid: bool, issues: [...]} when applicable
    latency_ms      INTEGER,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS audit_log_created_at_idx
    ON governance.audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS audit_log_endpoint_idx
    ON governance.audit_log (endpoint);


CREATE TABLE IF NOT EXISTS governance.review_decisions (
    id              BIGSERIAL PRIMARY KEY,
    audit_log_id    BIGINT REFERENCES governance.audit_log(id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    subject_type    TEXT NOT NULL,            -- 'alert' | 'narrative' | 'recommendation'
    subject_ref     TEXT NOT NULL,            -- e.g. metric+date for an alert
    decision        TEXT NOT NULL,            -- 'acknowledge' | 'dismiss' | 'escalate'
    note            TEXT,
    reviewer        TEXT                      -- placeholder until auth is added
);

CREATE INDEX IF NOT EXISTS review_decisions_subject_idx
    ON governance.review_decisions (subject_type, subject_ref);
