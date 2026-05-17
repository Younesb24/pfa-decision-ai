"""
Replay endpoints — read state for the dashboard "LIVE" pill, and advance the
synthetic clock from EventBridge (prod) or the local Dagster schedule (dev).

Backed by the `replay.state` + `replay.run` tables seeded in
scripts/replay_state_migration.sql. Returns a graceful "uninitialised" payload
when the schema isn't installed yet (fresh dev DB) so the frontend never 500s.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from db import query_gold_one
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

# scripts/replay_simulator.py is sibling to api/ — add the repo root once.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class ReplayState(BaseModel):
    synthetic_today: str | None = Field(
        default=None,
        description="ISO date of the simulator's current cursor.",
    )
    runs_completed: int = Field(default=0, description="Total successful ticks.")
    last_run_at: str | None = Field(
        default=None,
        description="Wall-clock timestamp of the last simulator tick (ISO).",
    )
    last_run_status: str | None = Field(
        default=None,
        description="success | noop | failed | running — from replay.run.",
    )
    last_run_rows: int | None = Field(
        default=None,
        description="Total rows ingested by the last successful tick.",
    )
    seconds_since_last_run: float | None = Field(
        default=None,
        description=(
            "Server-side computed delta — easier to render than asking the "
            "browser to do timezone math."
        ),
    )
    initialised: bool = Field(
        default=False,
        description="False when scripts/replay_state_migration.sql hasn't run yet.",
    )


class ReplayStateResponse(BaseModel):
    data: ReplayState
    generated_at: str


@router.get("/replay/state", response_model=ReplayStateResponse)
async def get_replay_state() -> ReplayStateResponse:
    """Return the current synthetic clock cursor + last-tick metadata.

    Best-effort: any DB / schema-missing error returns an uninitialised state
    rather than 500ing — the dashboard's LIVE pill simply renders 'idle'.
    """
    state = ReplayState()
    try:
        row = query_gold_one("""
            SELECT
                s.synthetic_today::text AS synthetic_today,
                s.runs_completed,
                s.last_run_at,
                r.status AS last_run_status,
                (
                    coalesce(r.rows_orders, 0)
                  + coalesce(r.rows_items, 0)
                  + coalesce(r.rows_reviews, 0)
                  + coalesce(r.rows_payments, 0)
                ) AS last_run_rows,
                extract(epoch FROM (now() - s.last_run_at)) AS seconds_since_last_run
              FROM replay.state s
              LEFT JOIN LATERAL (
                  SELECT status, rows_orders, rows_items, rows_reviews, rows_payments
                    FROM replay.run
                   ORDER BY started_at DESC
                   LIMIT 1
              ) r ON true
             WHERE s.id = 1
        """)
        if row:
            state = ReplayState(
                synthetic_today=row.get("synthetic_today"),
                runs_completed=int(row.get("runs_completed") or 0),
                last_run_at=row["last_run_at"].isoformat() if row.get("last_run_at") else None,
                last_run_status=row.get("last_run_status"),
                last_run_rows=(
                    int(row["last_run_rows"]) if row.get("last_run_rows") is not None else None
                ),
                seconds_since_last_run=(
                    float(row["seconds_since_last_run"])
                    if row.get("seconds_since_last_run") is not None
                    else None
                ),
                initialised=True,
            )
    except Exception:
        # Schema not installed yet — frontend falls back to "idle".
        pass

    return ReplayStateResponse(
        data=state,
        generated_at=datetime.now(UTC).isoformat(),
    )


class ReplayTickResponse(BaseModel):
    status: str = Field(description="success | noop | failed")
    synthetic_today: str | None = None
    next_synthetic_today: str | None = None
    run_id: int | None = None
    rows: dict[str, int] | None = None


def _verify_replay_token(provided: str | None) -> None:
    """Compare the inbound header against REPLAY_TICK_TOKEN.

    Missing env var → endpoint is disabled (returns 503). This is the safer
    default: a deploy that forgot to set the secret should NOT accept anonymous
    ticks. The local dev path passes the token explicitly when calling the
    function directly from Dagster.
    """
    expected = os.environ.get("REPLAY_TICK_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="REPLAY_TICK_TOKEN not configured; /replay/tick is disabled.",
        )
    if not provided or provided.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Replay-Token.",
        )


@router.post("/replay/tick", response_model=ReplayTickResponse)
async def post_replay_tick(
    x_replay_token: str | None = Header(default=None, alias="X-Replay-Token"),
) -> ReplayTickResponse:
    """Advance the synthetic clock by one day.

    Authenticated via a shared secret in the `X-Replay-Token` header — same
    value EventBridge sends from `aws_cloudwatch_event_connection.replay_tick`.
    The endpoint is intentionally *not* in the JWT-protected router: it's a
    machine-to-machine path and uses a separate credential.
    """
    _verify_replay_token(x_replay_token)

    try:
        from scripts.replay_simulator import tick
    except ImportError as exc:  # pragma: no cover - env-specific
        logger.exception("replay_simulator import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"replay_simulator unavailable: {exc}",
        ) from exc

    try:
        result = tick()
    except Exception as exc:
        logger.exception("replay tick failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"replay tick failed: {exc}",
        ) from exc

    return ReplayTickResponse(
        status=result.status,
        synthetic_today=str(result.synthetic_today),
        next_synthetic_today=str(result.next_synthetic_today),
        run_id=result.run_id,
        rows=result.rows,
    )
