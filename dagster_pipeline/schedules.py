"""
Dagster schedules — Day 2 wires the every-15-minute "ops refresh" tick.

Day 3 will add:
  * model_drift_check       — nightly 02:00 UTC
  * anomaly_escalation_sweep — hourly

The cron string `*/15 * * * *` is intentional: it produces the "Last refresh:
2 min ago" pill in the dashboard header that anchors the entire demo (see
EXECUTION_HANDOFF §10).
"""

from __future__ import annotations

from dagster import AssetSelection, ScheduleDefinition, define_asset_job

# Materialise the whole Day-2 graph on every tick. As the graph grows, we'll
# either narrow this selection or split into multiple schedules with different
# cadences (e.g. ML scoring may run every 15 min while briefings run hourly).
ops_refresh_job = define_asset_job(
    name="ops_refresh_job",
    selection=AssetSelection.all(),
    description="Replay one day of Olist into bronze.*_live and rebuild Gold via dbt.",
)

ops_refresh_schedule = ScheduleDefinition(
    name="ops_refresh_schedule",
    cron_schedule="*/15 * * * *",
    job=ops_refresh_job,
    description="Every 15 minutes: tick the synthetic clock + refresh Gold.",
    execution_timezone="UTC",
)
