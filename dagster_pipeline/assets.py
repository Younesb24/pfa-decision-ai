"""
Dagster assets — minimal Day 2 graph: bronze_replay → dbt_models.

Each asset shells out to an existing script (replay_simulator.py / dbt-core)
rather than re-implementing logic inside Dagster. This keeps Dagster as pure
orchestration; the scripts remain runnable standalone for debugging and CI.

Day 3 will add `ml_scores` and `cached_briefings`; Day 4 adds the learn
sensor; Day 9 adds source freshness annotations.

NOTE: this module deliberately does *not* `from __future__ import annotations`.
Dagster 1.13's `_validate_context_type_hint` compares `params[0].annotation`
against the class objects `AssetExecutionContext` / `OpExecutionContext`. With
PEP-563 annotations enabled, the annotation arrives as the string
`"AssetExecutionContext"` and the `in` check fails — producing a confusing
"Cannot annotate context parameter with type AssetExecutionContext" error
even though that *is* the required type. Until Dagster's validator uses
`get_type_hints()` (resolves forward refs), real classes are required here.
"""

import json
import subprocess
import sys
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    MaterializeResult,
    MetadataValue,
    asset,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPLAY_SCRIPT = REPO_ROOT / "scripts" / "replay_simulator.py"
DBT_PROJECT = REPO_ROOT / "dbt_project"


# ── bronze_replay ──────────────────────────────────────────────────────────

@asset(
    name="bronze_replay",
    key_prefix=["bronze"],
    group_name="bronze",
    description=(
        "Advances the synthetic clock by one day and ingests that day's slice "
        "of Olist into bronze.*_live. Idempotent per replay.run row."
    ),
    compute_kind="python",
)
def bronze_replay(context: AssetExecutionContext) -> MaterializeResult:
    """Run `python scripts/replay_simulator.py` and surface its JSON result."""
    cmd = [sys.executable, str(REPLAY_SCRIPT)]
    context.log.info(f"$ {' '.join(cmd)}")

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        # Pipe the simulator's stderr up so the Dagster run page shows it.
        context.log.error(proc.stderr or proc.stdout)
        raise RuntimeError(
            f"replay_simulator exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    # The simulator prints a JSON result to stdout. Parse it for metadata.
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        context.log.warning(f"Could not parse simulator output: {proc.stdout!r}")
        result = {"status": "unknown", "rows": {}}

    rows = result.get("rows", {}) or {}
    total = sum(int(v or 0) for v in rows.values())

    return MaterializeResult(
        metadata={
            "synthetic_today": MetadataValue.text(result.get("synthetic_today", "?")),
            "next_synthetic_today": MetadataValue.text(result.get("next_synthetic_today", "?")),
            "run_id": MetadataValue.int(result.get("run_id") or 0),
            "rows_total": MetadataValue.int(total),
            "rows_orders": MetadataValue.int(int(rows.get("orders") or 0)),
            "rows_items": MetadataValue.int(int(rows.get("items") or 0)),
            "rows_reviews": MetadataValue.int(int(rows.get("reviews") or 0)),
            "rows_payments": MetadataValue.int(int(rows.get("payments") or 0)),
            "status": MetadataValue.text(result.get("status", "?")),
        },
    )


# ── dbt_models ──────────────────────────────────────────────────────────────

@asset(
    name="dbt_models",
    key_prefix=["gold"],
    deps=[AssetKey(["bronze", "bronze_replay"])],
    group_name="silver_gold",
    description=(
        "Runs `dbt run` then `dbt test` against the prod target. Surfaces the "
        "test pass/fail count as asset metadata so the Dagster UI shows data "
        "quality at a glance."
    ),
    compute_kind="dbt",
)
def dbt_models(context: AssetExecutionContext) -> MaterializeResult:
    run_summary = _run_dbt(context, "run")
    test_summary = _run_dbt(context, "test", allow_failure=True)

    return MaterializeResult(
        metadata={
            "dbt_run_status": MetadataValue.text(run_summary["status"]),
            "dbt_run_log_tail": MetadataValue.text(run_summary["tail"]),
            "dbt_test_status": MetadataValue.text(test_summary["status"]),
            "dbt_test_log_tail": MetadataValue.text(test_summary["tail"]),
        },
    )


def _run_dbt(
    context: AssetExecutionContext,
    command: str,
    *,
    allow_failure: bool = False,
) -> dict:
    """Run a dbt subcommand and return a (status, log-tail) summary.

    Day 2 keeps this dead simple — Day 3 will switch to dbt-core's native
    `dagster-dbt` integration so each model becomes its own asset.
    """
    cmd = ["dbt", command, "--profiles-dir", str(DBT_PROJECT), "--project-dir", str(DBT_PROJECT)]
    context.log.info(f"$ {' '.join(cmd)}")

    proc = subprocess.run(
        cmd,
        cwd=str(DBT_PROJECT),
        capture_output=True,
        text=True,
        check=False,
    )
    tail = "\n".join((proc.stdout or "").splitlines()[-20:])

    if proc.returncode != 0:
        if allow_failure:
            context.log.warning(f"`dbt {command}` exited {proc.returncode}; continuing (tests are non-blocking on Day 2).")
            return {"status": f"failed ({proc.returncode})", "tail": tail}
        context.log.error(proc.stderr or tail)
        raise RuntimeError(f"`dbt {command}` exited {proc.returncode}")

    return {"status": "success", "tail": tail}
