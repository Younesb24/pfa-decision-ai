"""
Governance endpoints — audit journal + human review decisions.

This is the OODA "Act" surface:
- /governance/audit returns the recent LLM-touched activity for transparency
- /governance/review writes a human decision against an alert/narrative,
  closing the loop from observation → orientation → decision → action.

The governance schema is defined in scripts/audit_log_migration.sql. If the
schema is missing (e.g. fresh dev DB), endpoints return empty results rather
than 500ing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from db import get_db, list_audit_log, record_review
from fastapi import APIRouter, Query
from psycopg2.extras import Json
from pydantic import BaseModel, Field

router = APIRouter()


SubjectType = Literal["alert", "narrative", "recommendation"]
Decision = Literal["acknowledge", "dismiss", "escalate"]


class AuditEntry(BaseModel):
    id: int
    created_at: str
    endpoint: str
    persona: str | None = None
    user_input: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    latency_ms: int | None = None
    error: str | None = None
    self_critique: dict | None = None


class AuditResponse(BaseModel):
    entries: list[AuditEntry]
    generated_at: str


class ReviewRequest(BaseModel):
    subject_type: SubjectType = Field(description="What is being reviewed: alert | narrative | recommendation")
    subject_ref: str = Field(description="Stable reference: e.g. 'otif_rate@2018-08-31' for an alert")
    decision: Decision
    note: str | None = None
    reviewer: str | None = Field(default=None, description="Placeholder until auth lands")
    audit_log_id: int | None = None


class ReviewResponse(BaseModel):
    review_id: int | None
    recorded: bool
    generated_at: str


@router.get("/governance/audit")
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditResponse:
    """Most recent governance.audit_log entries, newest first."""
    rows = list_audit_log(limit=limit)
    entries = [AuditEntry(**row) for row in rows]
    return AuditResponse(
        entries=entries,
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.post("/governance/review")
async def post_review(req: ReviewRequest) -> ReviewResponse:
    """
    Record a human decision against an audited subject.
    Returns recorded=False if the governance schema is not installed.
    """
    review_id = record_review(
        audit_log_id=req.audit_log_id,
        subject_type=req.subject_type,
        subject_ref=req.subject_ref,
        decision=req.decision,
        note=req.note,
        reviewer=req.reviewer,
    )
    return ReviewResponse(
        review_id=review_id,
        recorded=review_id is not None,
        generated_at=datetime.now(UTC).isoformat(),
    )


# ── Decision outcomes (Day 4 — OODA "Learn" loop) ─────────────────────

class DecisionOutcome(BaseModel):
    """One open decision being tracked for after-the-fact effectiveness.

    Read-side: `expected_direction` and `status` are str (not Literal) so
    historical rows with legacy values like 'improved' don't break
    serialisation. The write-side (POST /governance/outcomes) does enforce
    the canonical enum on insert."""
    id: int
    created_at: str
    action_id: int | None
    subject_ref: str
    metric: str
    expected_direction: str
    baseline_value: float | None
    outcome_value: float | None
    outcome_date: str | None
    status: str
    note: str | None
    created_by: str | None


class OutcomesResponse(BaseModel):
    outcomes: list[DecisionOutcome]
    counts: dict[str, int]
    generated_at: str


class RecordOutcomeRequest(BaseModel):
    """Open a new decision-outcome tracker. Called when the operator acts.

    `metric` must be one of the gold.agg_daily_ops_kpi columns the learn
    sensor knows how to read: otif_rate, cancellation_rate, total_orders,
    total_gmv. Anything else stays in 'open' forever (we never close it).
    """
    subject_ref: str = Field(description="e.g. 'otif_rate@2018-08-29'")
    metric: str = Field(description="otif_rate | cancellation_rate | total_orders | total_gmv")
    expected_direction: Literal["increase", "decrease", "stable"]
    baseline_value: float | None = None
    action_id: int | None = None
    note: str | None = None
    created_by: str | None = None


class RecordOutcomeResponse(BaseModel):
    outcome_id: int | None
    recorded: bool
    generated_at: str


@router.get("/governance/outcomes")
async def get_outcomes(
    limit: int = Query(default=20, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status",
        description="open | useful | not_useful | inconclusive"),
) -> OutcomesResponse:
    """List recent decision-outcome rows. The dashboard's 'Past decisions'
    panel reads this. Counts per status are included for the summary chip."""
    where = ""
    params: dict[str, Any] = {"limit": limit}
    if status_filter:
        where = "WHERE status = %(status)s"
        params["status"] = status_filter

    rows: list[dict] = []
    counts: dict[str, int] = {"open": 0, "useful": 0, "not_useful": 0, "inconclusive": 0}
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, created_at::text, action_id, subject_ref, metric,
                           expected_direction, baseline_value, outcome_value,
                           outcome_date::text, status, note, created_by
                      FROM governance.decision_outcomes
                      {where}
                     ORDER BY created_at DESC
                     LIMIT %(limit)s
                """, params)
                rows = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT status, count(*)::int AS n
                      FROM governance.decision_outcomes
                     GROUP BY status
                """)
                for r in cur.fetchall():
                    counts[r["status"]] = int(r["n"])
    except Exception:
        # Schema missing — degrade gracefully (Day 3 alerts pattern).
        pass

    return OutcomesResponse(
        outcomes=[
            DecisionOutcome(
                id=r["id"],
                created_at=r["created_at"],
                action_id=r["action_id"],
                subject_ref=r["subject_ref"],
                metric=r["metric"],
                expected_direction=r["expected_direction"],
                baseline_value=float(r["baseline_value"]) if r["baseline_value"] is not None else None,
                outcome_value=float(r["outcome_value"]) if r["outcome_value"] is not None else None,
                outcome_date=r["outcome_date"],
                status=r["status"],
                note=r["note"],
                created_by=r["created_by"],
            )
            for r in rows
        ],
        counts=counts,
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.post("/governance/outcomes")
async def post_outcome(req: RecordOutcomeRequest) -> RecordOutcomeResponse:
    """Open a new decision-outcome record. Returns recorded=False if the
    governance schema is missing — same graceful-degrade contract as the
    review endpoint above."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO governance.decision_outcomes
                        (action_id, subject_ref, metric, expected_direction,
                         baseline_value, note, created_by, status)
                    VALUES
                        (%(action_id)s, %(subject_ref)s, %(metric)s,
                         %(expected_direction)s, %(baseline_value)s,
                         %(note)s, %(created_by)s, 'open')
                    RETURNING id
                """, {
                    "action_id": req.action_id,
                    "subject_ref": req.subject_ref,
                    "metric": req.metric,
                    "expected_direction": req.expected_direction,
                    "baseline_value": req.baseline_value,
                    "note": req.note,
                    "created_by": req.created_by,
                })
                row = cur.fetchone()
                conn.commit()
                return RecordOutcomeResponse(
                    outcome_id=int(row["id"]) if row else None,
                    recorded=row is not None,
                    generated_at=datetime.now(UTC).isoformat(),
                )
    except Exception:
        return RecordOutcomeResponse(
            outcome_id=None,
            recorded=False,
            generated_at=datetime.now(UTC).isoformat(),
        )


# ── Action history (Day 5 — Action Center backend) ────────────────────

class ActionHistoryEntry(BaseModel):
    """Read-side model — `action_type` and `status` are str (not Literal)
    so that historical rows with legacy values like 'dry_run' don't break
    serialisation. Write-side validation enforces the canonical enum on
    insert (see /act/* + insert_action)."""
    id: int
    created_at: str
    action_type: str
    channel: str
    subject_ref: str
    status: str
    title: str | None
    payload: dict | None
    result: dict | None


class ActionHistoryResponse(BaseModel):
    entries: list[ActionHistoryEntry]
    generated_at: str


@router.get("/governance/actions")
async def get_action_history(
    limit: int = Query(default=30, ge=1, le=200),
    subject_ref: str | None = Query(default=None),
) -> ActionHistoryResponse:
    """List recent outbound actions. The dashboard's action panel reads
    this so operators see what's been fired against an anomaly."""
    where = ""
    params: dict[str, Any] = {"limit": limit}
    if subject_ref:
        where = "WHERE subject_ref = %(subject_ref)s"
        params["subject_ref"] = subject_ref

    rows: list[dict] = []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, created_at::text, action_type, channel,
                           subject_ref, status, title, payload, result
                      FROM governance.action_history
                      {where}
                     ORDER BY created_at DESC
                     LIMIT %(limit)s
                """, params)
                rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        pass

    return ActionHistoryResponse(
        entries=[
            ActionHistoryEntry(
                id=r["id"],
                created_at=r["created_at"],
                action_type=r["action_type"],
                channel=r["channel"],
                subject_ref=r["subject_ref"],
                status=r["status"],
                title=r["title"],
                payload=r["payload"],
                result=r["result"],
            )
            for r in rows
        ],
        generated_at=datetime.now(UTC).isoformat(),
    )


# Helper used by api/routers/act.py and the Dagster learn sensor.
def insert_action(
    *,
    action_type: str,
    channel: str,
    subject_ref: str,
    status: str = "drafted",
    title: str | None = None,
    payload: dict | None = None,
    result: dict | None = None,
    created_by: str | None = None,
) -> int | None:
    """Best-effort INSERT into governance.action_history. Returns the new
    row id, or None on failure."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO governance.action_history
                        (action_type, channel, subject_ref, status, title,
                         payload, result, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    action_type, channel, subject_ref, status, title,
                    Json(payload) if payload is not None else None,
                    Json(result) if result is not None else None,
                    created_by,
                ))
                row = cur.fetchone()
                conn.commit()
                return int(row["id"]) if row else None
    except Exception:
        return None


def update_action_status(action_id: int, *, status: str, result: dict | None = None) -> bool:
    """Best-effort update — used by /act/email/send to flip status from
    drafted -> sent (or failed). Returns True on success."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE governance.action_history
                       SET status = %s,
                           result = COALESCE(%s::jsonb, result)
                     WHERE id = %s
                """, (
                    status,
                    Json(result) if result is not None else None,
                    action_id,
                ))
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


def fetch_action(action_id: int) -> dict | None:
    """Read a single action_history row by id (for /act/email/send)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, action_type, channel, subject_ref, status,
                           title, payload, result
                      FROM governance.action_history
                     WHERE id = %s
                """, (action_id,))
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        return None
