"""
Dagster sensors — fire alerts into governance.alerts when the pipeline
misbehaves. Day 3 deliverable (EXECUTION_HANDOFF §3 / §5.1).

Two sensors run alongside the 15-min ops_refresh_schedule:

  * `replay_freshness_sensor` (every 5 min)
      Checks `replay.state.last_run_at`. If the last simulator tick is
      older than the freshness budget (30 min warn / 90 min critical),
      write a `source_freshness` alert. The dashboard's Data Health page
      (Day 9) reads these rows and surfaces "Replay stalled" if any are
      unresolved.

  * `dbt_test_failure_sensor` (event-driven on dbt_models materialization)
      When the `gold/dbt_models` asset's MaterializeResult metadata flags
      `dbt_test_status` as anything other than 'success', write a
      `dbt_test_failed` alert. The dbt subprocess captures the failure
      tail; we copy a truncated version into `details.tail` for the
      operator to see at a glance.

Both sensors are idempotent: each one upserts on `(kind, source_ref)` so
the table doesn't accumulate dozens of duplicate alerts when the same
issue persists across ticks.
"""

import json
import os
from typing import Any

import psycopg2
from dagster import (
    AssetKey,
    DefaultSensorStatus,
    EventLogEntry,
    RunRequest,
    SensorEvaluationContext,
    SkipReason,
    asset_sensor,
    sensor,
)

_DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
    "user": os.getenv("POSTGRES_USER", "pfa"),
    "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
}

# Freshness thresholds — match the dbt source freshness in sources.yml so the
# alarms are consistent across orchestration and warehouse-side checks.
FRESHNESS_WARN_MINUTES = 30
FRESHNESS_CRITICAL_MINUTES = 90


def _upsert_alert(
    *,
    kind: str,
    source_ref: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Idempotent insert: if an UNRESOLVED alert already exists for this
    (kind, source_ref) tuple, update its `created_at` + message so the
    Data Health page sees the latest state. Otherwise INSERT.
    """
    payload = json.dumps(details or {}, default=str)
    with psycopg2.connect(**_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE governance.alerts
                   SET created_at = now(),
                       severity   = %s,
                       message    = %s,
                       details    = %s::jsonb
                 WHERE kind = %s
                   AND source_ref = %s
                   AND resolved_at IS NULL
                """,
                (severity, message, payload, kind, source_ref),
            )
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO governance.alerts
                        (kind, severity, source_ref, message, details)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (kind, severity, source_ref, message, payload),
                )


def _resolve_alert(*, kind: str, source_ref: str, by: str = "auto-recovery") -> None:
    """Mark any unresolved alert for (kind, source_ref) as resolved.
    Called when the underlying condition has cleared so the dashboard
    doesn't keep showing stale alarms.
    """
    with psycopg2.connect(**_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE governance.alerts
                   SET resolved_at = now(),
                       resolved_by = %s
                 WHERE kind = %s
                   AND source_ref = %s
                   AND resolved_at IS NULL
                """,
                (by, kind, source_ref),
            )


# ── 1. Replay freshness sensor ───────────────────────────────────────────

@sensor(
    name="replay_freshness_sensor",
    minimum_interval_seconds=300,  # poll every 5 min
    default_status=DefaultSensorStatus.STOPPED,  # operator turns this on
    description=(
        "Watches replay.state.last_run_at. Writes a source_freshness alert "
        "to governance.alerts when the simulator is more than 30 min behind."
    ),
)
def replay_freshness_sensor(context: SensorEvaluationContext):
    """Pure observation — no jobs to launch. We rely on the SensorEvaluation
    side-effect of writing to governance.alerts, then return SkipReason so
    Dagster doesn't try to run anything.
    """
    try:
        with psycopg2.connect(**_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT synthetic_today::text,
                           last_run_at,
                           extract(epoch FROM (now() - last_run_at)) AS age_seconds
                      FROM replay.state
                     WHERE id = 1
                """)
                row = cur.fetchone()
    except Exception as e:
        context.log.warning(f"replay_freshness_sensor: cannot reach Postgres: {e}")
        return SkipReason(f"DB unreachable: {e}")

    if not row:
        return SkipReason("replay.state not initialised")

    synthetic_today, last_run_at, age_seconds = row
    if age_seconds is None:
        return SkipReason("never run")

    age_min = float(age_seconds) / 60.0
    source_ref = "replay.state"
    details = {
        "synthetic_today": synthetic_today,
        "last_run_at": str(last_run_at),
        "age_minutes": round(age_min, 1),
    }

    if age_min >= FRESHNESS_CRITICAL_MINUTES:
        _upsert_alert(
            kind="source_freshness",
            source_ref=source_ref,
            severity="critical",
            message=f"Replay simulator stalled — last tick {age_min:.0f} min ago.",
            details=details,
        )
        return SkipReason(f"critical: {age_min:.0f} min behind")

    if age_min >= FRESHNESS_WARN_MINUTES:
        _upsert_alert(
            kind="source_freshness",
            source_ref=source_ref,
            severity="warning",
            message=f"Replay simulator behind — last tick {age_min:.0f} min ago.",
            details=details,
        )
        return SkipReason(f"warning: {age_min:.0f} min behind")

    # Healthy — clear any prior alert.
    _resolve_alert(kind="source_freshness", source_ref=source_ref)
    return SkipReason(f"healthy: {age_min:.0f} min")


# ── 2. dbt-test failure sensor ────────────────────────────────────────────

@asset_sensor(
    asset_key=AssetKey(["gold", "dbt_models"]),
    name="dbt_test_failure_sensor",
    default_status=DefaultSensorStatus.STOPPED,
    description=(
        "Fires on each dbt_models materialization. Reads the asset's "
        "metadata; if `dbt_test_status` is non-success, writes a "
        "dbt_test_failed alert to governance.alerts."
    ),
)
def dbt_test_failure_sensor(
    context: SensorEvaluationContext,
    asset_event: EventLogEntry,
):
    """Asset sensors fire once per materialization event of the target
    asset. We pull the metadata off the event and decide whether to alarm.
    """
    materialization = (
        asset_event.dagster_event.event_specific_data.materialization
        if asset_event.dagster_event
        and asset_event.dagster_event.event_specific_data
        else None
    )
    metadata: dict[str, Any] = {}
    if materialization and materialization.metadata:
        metadata = {k: v.value for k, v in materialization.metadata.items()}

    test_status = str(metadata.get("dbt_test_status") or "unknown")
    tail = str(metadata.get("dbt_test_log_tail") or "")[:1500]
    source_ref = "dbt:test"

    if test_status == "success":
        _resolve_alert(kind="dbt_test_failed", source_ref=source_ref)
        return SkipReason("dbt tests passed")

    severity = "critical" if "error" in test_status.lower() else "warning"
    _upsert_alert(
        kind="dbt_test_failed",
        source_ref=source_ref,
        severity=severity,
        message=f"dbt test status: {test_status}",
        details={"tail": tail, "asset": "gold.dbt_models"},
    )
    return SkipReason(f"alerted: {test_status}")


# Dagster's `sensors=[...]` parameter on Definitions takes both `sensor` and
# `asset_sensor` outputs uniformly. The Definitions binding lives in
# dagster_pipeline/__init__.py.
ALL_SENSORS: list = [replay_freshness_sensor, dbt_test_failure_sensor]

# Surface a `RunRequest` constructor reference so future schedules /
# external triggers can reuse the same pattern without re-importing it.
__all__ = [
    "ALL_SENSORS",
    "replay_freshness_sensor",
    "dbt_test_failure_sensor",
    "RunRequest",
]
