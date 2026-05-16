"""
Dagster GraphQL client — best-effort wrapper.

Queries the Dagster webserver (default: http://localhost:3001) for recent
pipeline runs. Degrades gracefully to an empty dict when Dagster is offline
or unreachable — data-health pages should show "Dagster offline" rather
than crashing.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DAGSTER_URL = os.getenv("DAGSTER_URL", "http://localhost:3001")
_GRAPHQL = f"{DAGSTER_URL}/graphql"

_RUNS_QUERY = """
query RecentRuns($limit: Int!) {
  runsOrError(limit: $limit) {
    ... on Runs {
      results {
        runId
        status
        startTime
        endTime
        jobName
      }
    }
  }
}
"""


def get_recent_runs(limit: int = 20, timeout: float = 3.0) -> dict[str, Any]:
    """
    Fetch recent Dagster runs via GraphQL.

    Returns:
        {
          "runs": [{"runId": ..., "status": ..., "startTime": ..., "jobName": ...}],
          "reachable": True,
          "last_24h_count": int,
          "last_24h_success_rate": float,   # 0-1
        }

    On any error returns {"runs": [], "reachable": False, ...}.
    """
    try:
        r = httpx.post(
            _GRAPHQL,
            json={"query": _RUNS_QUERY, "variables": {"limit": limit}},
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        data = r.json()
        runs = (
            data.get("data", {})
            .get("runsOrError", {})
            .get("results", [])
        )

        import time
        cutoff = time.time() - 86400  # 24 h ago
        recent = [
            run for run in runs
            if run.get("startTime") and float(run["startTime"]) >= cutoff
        ]
        success = sum(1 for r in recent if r.get("status") == "SUCCESS")
        rate = success / len(recent) if recent else 0.0

        return {
            "runs": runs,
            "reachable": True,
            "last_24h_count": len(recent),
            "last_24h_success_rate": round(rate, 3),
        }
    except Exception:
        return {
            "runs": [],
            "reachable": False,
            "last_24h_count": 0,
            "last_24h_success_rate": 0.0,
        }
