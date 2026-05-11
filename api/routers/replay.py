"""
Replay-state endpoint — exposes the synthetic-clock cursor so the dashboard
header can render "Last refresh: 2 min ago · synthetic_today = 2018-04-12".

Backed by the `replay.state` + `replay.run` tables seeded in
scripts/replay_state_migration.sql. Returns a graceful "uninitialised" payload
when the schema isn't installed yet (fresh dev DB) so the frontend never 500s.
"""

from __future__ import annotations

from datetime import UTC, datetime

from db import query_gold_one
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


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
