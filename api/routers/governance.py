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
from typing import Literal

from db import list_audit_log, record_review
from fastapi import APIRouter, Query
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
