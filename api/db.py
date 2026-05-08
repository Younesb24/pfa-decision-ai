"""
Database connection module for FastAPI.
Uses psycopg2 for sync queries against the Gold layer.
Connection pooling via contextmanager pattern.

Also exposes audit-journal helpers: every LLM-touched request is recorded in
governance.audit_log, and human review decisions in governance.review_decisions.
See scripts/audit_log_migration.sql for the schema.
"""

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
    "user": os.getenv("POSTGRES_USER", "pfa"),
    "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
}


@contextmanager
def get_db() -> Generator:
    """Yield a database connection with RealDictCursor."""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def query_gold(sql: str, params: dict | None = None) -> list[dict]:
    """Execute a read-only query against the Gold layer and return list of dicts."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()


def query_gold_one(sql: str, params: dict | None = None) -> dict | None:
    """Execute a query and return a single row as dict."""
    rows = query_gold(sql, params)
    return rows[0] if rows else None


# ── Audit journal ──

def log_audit(
    *,
    endpoint: str,
    persona: str | None = None,
    user_input: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_output: str | None = None,
    data_context: dict[str, Any] | None = None,
    self_critique: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> int | None:
    """
    Record an audit entry. Best-effort: returns None if the governance schema
    isn't installed (e.g. on a fresh dev DB before running the migration).
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.audit_log
                        (endpoint, persona, user_input, llm_provider, llm_model,
                         llm_output, data_context, self_critique, latency_ms, error)
                    VALUES
                        (%(endpoint)s, %(persona)s, %(user_input)s, %(llm_provider)s,
                         %(llm_model)s, %(llm_output)s, %(data_context)s,
                         %(self_critique)s, %(latency_ms)s, %(error)s)
                    RETURNING id
                    """,
                    {
                        "endpoint": endpoint,
                        "persona": persona,
                        "user_input": user_input,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "llm_output": llm_output,
                        "data_context": Json(data_context) if data_context is not None else None,
                        "self_critique": Json(self_critique) if self_critique is not None else None,
                        "latency_ms": latency_ms,
                        "error": error,
                    },
                )
                row = cur.fetchone()
                conn.commit()
                return int(row["id"]) if row else None
    except Exception:
        # Audit must never break the user request. Swallow and continue.
        return None


def record_review(
    *,
    audit_log_id: int | None,
    subject_type: str,
    subject_ref: str,
    decision: str,
    note: str | None = None,
    reviewer: str | None = None,
) -> int | None:
    """Record a human review decision against an audited subject."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.review_decisions
                        (audit_log_id, subject_type, subject_ref, decision, note, reviewer)
                    VALUES
                        (%(audit_log_id)s, %(subject_type)s, %(subject_ref)s,
                         %(decision)s, %(note)s, %(reviewer)s)
                    RETURNING id
                    """,
                    {
                        "audit_log_id": audit_log_id,
                        "subject_type": subject_type,
                        "subject_ref": subject_ref,
                        "decision": decision,
                        "note": note,
                        "reviewer": reviewer,
                    },
                )
                row = cur.fetchone()
                conn.commit()
                return int(row["id"]) if row else None
    except Exception:
        return None


def list_audit_log(limit: int = 50) -> list[dict]:
    """Fetch the most recent audit entries for the governance dashboard."""
    try:
        return query_gold(
            """
            SELECT id, created_at::text, endpoint, persona, user_input,
                   llm_provider, llm_model, latency_ms, error,
                   self_critique
            FROM governance.audit_log
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
    except Exception:
        return []
