"""
dbt artifacts reader — parses target/run_results.json produced by `dbt test`.

Degrades gracefully when the file is missing (e.g. dbt has never been run).
Returns empty stats rather than raising.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Resolve relative to this file so it works regardless of cwd
_DEFAULT_PATH = (
    Path(__file__).parent.parent.parent
    / "dbt_project"
    / "target"
    / "run_results.json"
)
DBT_ARTIFACTS_PATH = Path(os.getenv("DBT_RUN_RESULTS_PATH", str(_DEFAULT_PATH)))


def get_dbt_test_stats() -> dict[str, Any]:
    """
    Parse dbt run_results.json and return test pass/fail counts.

    Returns:
        {
          "last_test_pass_count": int,
          "last_test_fail_count": int,
          "last_test_warn_count": int,
          "last_run_at": str | None,   # ISO timestamp from metadata
          "available": bool,
        }
    """
    if not DBT_ARTIFACTS_PATH.exists():
        return {
            "last_test_pass_count": 0,
            "last_test_fail_count": 0,
            "last_test_warn_count": 0,
            "last_run_at": None,
            "available": False,
        }

    try:
        with open(DBT_ARTIFACTS_PATH) as f:
            data: dict = json.load(f)

        generated_at: str | None = data.get("metadata", {}).get("generated_at")
        results: list[dict] = data.get("results", [])

        passed = sum(1 for r in results if r.get("status") == "pass")
        failed = sum(1 for r in results if r.get("status") in ("fail", "error"))
        warned = sum(1 for r in results if r.get("status") == "warn")

        return {
            "last_test_pass_count": passed,
            "last_test_fail_count": failed,
            "last_test_warn_count": warned,
            "last_run_at": generated_at,
            "available": True,
        }
    except Exception:
        return {
            "last_test_pass_count": 0,
            "last_test_fail_count": 0,
            "last_test_warn_count": 0,
            "last_run_at": None,
            "available": False,
        }
