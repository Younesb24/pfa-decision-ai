-- Day 10 — JWT auth.
-- Users live in the governance schema alongside the audit journal: the same
-- people who read the audit log are the ones who own actions in /act/* and
-- decisions in /governance/review. Keeping them together makes joins for
-- "who acknowledged this alert?" trivial.

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,            -- bcrypt
    display_name    TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'ops', 'analyst', 'viewer')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS users_email_idx ON governance.users (email);

-- Optional: link audit_log rows to a user once auth is wired through.
-- Soft FK so legacy unauthenticated rows keep working.
ALTER TABLE governance.audit_log
    ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES governance.users(id) ON DELETE SET NULL;

ALTER TABLE governance.review_decisions
    ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES governance.users(id) ON DELETE SET NULL;
