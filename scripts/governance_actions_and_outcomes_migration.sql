-- governance.action_history + governance.decision_outcomes
--
-- Day 4 / Day 5 (EXECUTION_HANDOFF §5.2, §5.3). These tables were already
-- live in the dev DB (an earlier Codex run created them in-place) but had
-- no committed migration. Captured here so a fresh box can stand them up.
--
-- action_history    — every outbound action (email, webhook, escalation)
--                     fired by the Decision Analyst, with status + result.
-- decision_outcomes — bookkeeping for the OODA "Learn" loop. A row is
--                     opened when the operator acts; the Dagster
--                     learn_sensor (dagster_pipeline/learn_sensor.py)
--                     fills outcome_value after 7 synthetic days and
--                     marks the decision useful / inconclusive.

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.action_history (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_type  TEXT NOT NULL CHECK (action_type IN ('email', 'webhook', 'escalation')),
    channel      TEXT NOT NULL,                  -- 'smtp:ops', 'slack', 'linear', 'jira', 'escalate:internal'
    subject_ref  TEXT NOT NULL,                  -- e.g. 'otif_rate@2018-08-29'
    status       TEXT NOT NULL DEFAULT 'drafted'  -- drafted | sent | failed
        CHECK (status IN ('drafted', 'sent', 'failed', 'cancelled')),
    title        TEXT,
    payload      JSONB,                          -- body, recipient, draft text
    result       JSONB,                          -- delivery receipt / error
    created_by   TEXT                            -- placeholder until auth (Day 10)
);

CREATE INDEX IF NOT EXISTS action_history_created_at_idx
    ON governance.action_history (created_at DESC);

CREATE INDEX IF NOT EXISTS action_history_subject_idx
    ON governance.action_history (subject_ref, action_type);


CREATE TABLE IF NOT EXISTS governance.decision_outcomes (
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_id          BIGINT REFERENCES governance.action_history(id) ON DELETE SET NULL,
    subject_ref        TEXT NOT NULL,
    metric             TEXT NOT NULL,                    -- e.g. 'otif_rate', 'cancellation_rate'
    expected_direction TEXT NOT NULL                     -- increase | decrease | stable
        CHECK (expected_direction IN ('increase', 'decrease', 'stable')),
    baseline_value     NUMERIC,                          -- metric at decision time
    outcome_value      NUMERIC,                          -- metric 7 days later
    outcome_date       DATE,                             -- when learn_sensor filled it
    status             TEXT NOT NULL DEFAULT 'open'      -- open | useful | not_useful | inconclusive
        CHECK (status IN ('open', 'useful', 'not_useful', 'inconclusive')),
    note               TEXT,
    created_by         TEXT
);

CREATE INDEX IF NOT EXISTS decision_outcomes_created_at_idx
    ON governance.decision_outcomes (created_at DESC);

CREATE INDEX IF NOT EXISTS decision_outcomes_subject_idx
    ON governance.decision_outcomes (subject_ref, metric);

CREATE INDEX IF NOT EXISTS decision_outcomes_open_idx
    ON governance.decision_outcomes (created_at) WHERE status = 'open';
