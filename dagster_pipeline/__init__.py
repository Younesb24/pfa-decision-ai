"""
dagster_pipeline — Dagster project for the Marketplace Decision Cockpit.

Day 2 (EXECUTION_HANDOFF §3, Sprint 1). This package exports a `Definitions`
object that Dagster's UI / `dagster dev` loads. The asset graph for Day 2 is
intentionally minimal:

    bronze_replay  →  dbt_models

Day 3 will extend it with `ml_scores` and `cached_briefings`, plus source
freshness policies and the dbt-test failure sensor.

Run from the repo root:

    pip install -r dagster_pipeline/requirements.txt
    dagster dev -m dagster_pipeline           # UI on :3000 (override with -p 3001)

ADR-007 captures the "why Dagster" decision.
"""

from __future__ import annotations

from dagster import Definitions

from .assets import bronze_replay, dbt_models
from .schedules import ops_refresh_schedule
from .sensors import ALL_SENSORS

defs = Definitions(
    assets=[bronze_replay, dbt_models],
    schedules=[ops_refresh_schedule],
    sensors=ALL_SENSORS,
)
