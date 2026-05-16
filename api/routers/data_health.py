"""
Data Health endpoint — aggregates pipeline, model, and alert status into one
response that the /data-health dashboard page polls every 60 s.

Endpoint: GET /api/v1/data-health/status

Every sub-system is best-effort: if Dagster is offline, dbt artifacts are
missing, or the DB query fails, that section degrades to a safe default rather
than returning a 500.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from db import query_gold_one
from fastapi import APIRouter
from pydantic import BaseModel
from services.dagster_client import get_recent_runs
from services.dbt_artifacts_reader import get_dbt_test_stats

router = APIRouter()


# ── Pydantic DTOs ──────────────────────────────────────────────────────────────


class ReplayStatus(BaseModel):
    synthetic_today: str | None
    last_run_at: str | None
    age_seconds: int | None
    initialised: bool


class DbtStatus(BaseModel):
    last_test_pass_count: int
    last_test_fail_count: int
    last_test_warn_count: int
    last_run_at: str | None
    available: bool


class ModelHealth(BaseModel):
    name: str
    roc_auc: float | None = None
    mape: float | None = None
    drift_status: str = "unknown"
    trained_at: str | None = None


class AlertCount(BaseModel):
    kind: str
    count: int


class DagsterStatus(BaseModel):
    reachable: bool
    last_24h_count: int
    last_24h_success_rate: float


class DataHealthResponse(BaseModel):
    checked_at: str
    replay: ReplayStatus
    dbt: DbtStatus
    ml: list[ModelHealth]
    alerts: list[AlertCount]
    dagster: DagsterStatus


# ── Sub-system fetchers ────────────────────────────────────────────────────────


def _get_replay_status() -> ReplayStatus:
    try:
        row = query_gold_one(
            """
            SELECT
                synthetic_today::text,
                last_run_at::text,
                EXTRACT(EPOCH FROM (NOW() - last_run_at))::int AS age_seconds,
                (last_run_at IS NOT NULL) AS initialised
            FROM replay.state
            LIMIT 1
            """
        )
        if row:
            return ReplayStatus(
                synthetic_today=row.get("synthetic_today"),
                last_run_at=row.get("last_run_at"),
                age_seconds=row.get("age_seconds"),
                initialised=bool(row.get("initialised")),
            )
    except Exception:
        pass
    return ReplayStatus(
        synthetic_today=None, last_run_at=None,
        age_seconds=None, initialised=False,
    )


def _get_ml_health() -> list[ModelHealth]:
    """Read model artefacts from the local ml/models/ directory."""
    import json
    from pathlib import Path

    models_dir = (
        Path(__file__).parent.parent.parent / "ml" / "models"
    )
    results: list[ModelHealth] = []

    for meta_file in sorted(models_dir.glob("*_metadata.json")):
        try:
            meta: dict[str, Any] = json.loads(meta_file.read_text())
            results.append(ModelHealth(
                name=meta.get("name", meta_file.stem.replace("_metadata", "")),
                roc_auc=meta.get("roc_auc"),
                mape=meta.get("mape"),
                drift_status=meta.get("drift_status", "unknown"),
                trained_at=meta.get("trained_at"),
            ))
        except Exception:
            pass

    return results


def _get_alert_counts() -> list[AlertCount]:
    try:
        rows = query_gold_one(
            """
            SELECT kind, COUNT(*) AS cnt
            FROM governance.alerts
            WHERE resolved_at IS NULL
            GROUP BY kind
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
        # query_gold returns list; query_gold_one just returns first row — use query_gold
        from db import query_gold

        rows = query_gold(
            """
            SELECT kind, COUNT(*) AS cnt
            FROM governance.alerts
            WHERE resolved_at IS NULL
            GROUP BY kind
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
        return [AlertCount(kind=str(r["kind"]), count=int(r["cnt"])) for r in rows]
    except Exception:
        return []


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get("/data-health/status")
async def data_health_status() -> DataHealthResponse:
    """
    Aggregate pipeline health: replay, dbt, ML models, governance alerts,
    and Dagster run history. All sub-systems degrade gracefully when offline.
    """
    replay = _get_replay_status()
    dbt_raw = get_dbt_test_stats()
    dbt = DbtStatus(**dbt_raw)
    ml = _get_ml_health()
    alerts = _get_alert_counts()
    dagster_raw = get_recent_runs()
    dagster = DagsterStatus(
        reachable=dagster_raw["reachable"],
        last_24h_count=dagster_raw["last_24h_count"],
        last_24h_success_rate=dagster_raw["last_24h_success_rate"],
    )

    return DataHealthResponse(
        checked_at=datetime.now(UTC).isoformat(),
        replay=replay,
        dbt=dbt,
        ml=ml,
        alerts=alerts,
        dagster=dagster,
    )
