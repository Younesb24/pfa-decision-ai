"""
Replay simulator — drives the synthetic "now" cursor one day forward per run.

Day 2 (EXECUTION_HANDOFF §5.1). The Olist dataset spans 2017-01-01 → 2018-09-03;
the cockpit needs a continuously-refreshing data flow to make the OODA Observe
loop visible. This script:

  1. Reads `replay.state.synthetic_today` (initialises to 2017-01-01 if missing).
  2. Pulls every Olist row whose `order_purchase_timestamp` falls on that date
     out of the legacy `bronze.*` one-shot load.
  3. Shifts every timestamp it owns by (today_wall_clock − synthetic_today),
     so the rows look like they were placed "a few minutes ago" — that's the
     timestamp the dashboard's "Last refresh" pill shows.
  4. Appends to `bronze.*_live` with `_ingest_run_id` for idempotency.
  5. Advances the cursor by one day. Wraps to 2017-01-01 after 2018-09-03.

The Dagster `bronze_replay` asset shells out to this script. The script is
also runnable standalone for manual testing:

    python scripts/replay_simulator.py            # one tick
    python scripts/replay_simulator.py --dry-run  # show plan, change nothing
    python scripts/replay_simulator.py --reset 2017-06-01  # reset cursor

Idempotency: the unique index on (natural_key..., _ingest_run_id) means re-
running with the same `replay.run` row inserted is impossible (we never reuse
run_ids). A failed run leaves status='failed' in `replay.run` and the cursor
unchanged; the next run picks up the same `synthetic_today`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# ── Configuration ──────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
    "user": os.getenv("POSTGRES_USER", "pfa"),
    "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
}

# Olist coverage window. Anything outside this wraps to REPLAY_START.
REPLAY_START = date(2017, 1, 1)
REPLAY_END = date(2018, 9, 3)

# Source date column used to slice the legacy bronze.* tables by day. We slice
# on order_purchase_timestamp (the natural arrival cadence) for orders/items/
# payments; reviews carry their own creation date.
ORDERS_DATE_EXPR = "order_purchase_timestamp::timestamp::date"
REVIEWS_DATE_EXPR = "review_creation_date::timestamp::date"


# ── Domain model ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReplaySlice:
    """One day's worth of rows pulled from the legacy bronze.* warehouse."""
    orders: list[dict[str, Any]]
    items: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    payments: list[dict[str, Any]]

    @property
    def total_rows(self) -> int:
        return (
            len(self.orders) + len(self.items) + len(self.reviews) + len(self.payments)
        )


@dataclass
class ReplayResult:
    """Returned by `tick()` so the caller (Dagster) can log it as metadata."""
    synthetic_today: date
    next_synthetic_today: date
    run_id: int | None
    rows: dict[str, int]
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthetic_today": self.synthetic_today.isoformat(),
            "next_synthetic_today": self.next_synthetic_today.isoformat(),
            "run_id": self.run_id,
            "rows": self.rows,
            "status": self.status,
            "error": self.error,
        }


# ── DB helpers ─────────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def _read_cursor(conn) -> date:
    with conn.cursor() as cur:
        cur.execute("SELECT synthetic_today FROM replay.state WHERE id = 1")
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                "replay.state not initialised — run scripts/replay_state_migration.sql first."
            )
        return row["synthetic_today"]


def _advance_cursor(conn, *, current: date, next_day: date, run_id: int | None, rows: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE replay.state
               SET synthetic_today = %(next)s,
                   runs_completed = runs_completed + 1,
                   last_run_at = now(),
                   last_rows_ingested = %(rows)s
             WHERE id = 1
            """,
            {"next": next_day, "rows": rows},
        )


def _open_run(conn, synthetic_today: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO replay.run (synthetic_today) VALUES (%s) RETURNING run_id",
            (synthetic_today,),
        )
        row = cur.fetchone()
        return int(row["run_id"])


def _close_run(
    conn,
    *,
    run_id: int,
    rows: dict[str, int],
    status: str,
    error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE replay.run
               SET finished_at = now(),
                   rows_orders = %(o)s,
                   rows_items = %(i)s,
                   rows_reviews = %(r)s,
                   rows_payments = %(p)s,
                   status = %(status)s,
                   error = %(err)s
             WHERE run_id = %(rid)s
            """,
            {
                "o": rows.get("orders", 0),
                "i": rows.get("items", 0),
                "r": rows.get("reviews", 0),
                "p": rows.get("payments", 0),
                "status": status,
                "err": error,
                "rid": run_id,
            },
        )


# ── Slicing the legacy bronze layer ────────────────────────────────────────

def _fetch_slice(conn, synthetic_today: date) -> ReplaySlice:
    """Pull every row dated `synthetic_today` out of the legacy bronze.* tables.

    The legacy `bronze.*` is populated once by `scripts/load_bronze.py` and is
    treated here as a read-only historical stash. We do NOT touch its rows;
    we only copy slices into bronze.*_live.
    """
    params = {"day": synthetic_today.isoformat()}

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT *
              FROM bronze.orders
             WHERE {ORDERS_DATE_EXPR} = %(day)s::date
        """, params)
        orders = [dict(r) for r in cur.fetchall()]

        if orders:
            order_ids = tuple(o["order_id"] for o in orders)
            cur.execute(
                "SELECT * FROM bronze.order_items WHERE order_id = ANY(%(ids)s)",
                {"ids": list(order_ids)},
            )
            items = [dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT * FROM bronze.order_payments WHERE order_id = ANY(%(ids)s)",
                {"ids": list(order_ids)},
            )
            payments = [dict(r) for r in cur.fetchall()]
        else:
            items, payments = [], []

        # Reviews have their own creation date — slice independently.
        cur.execute(f"""
            SELECT *
              FROM bronze.order_reviews
             WHERE {REVIEWS_DATE_EXPR} = %(day)s::date
        """, params)
        reviews = [dict(r) for r in cur.fetchall()]

    return ReplaySlice(orders=orders, items=items, reviews=reviews, payments=payments)


# ── Timestamp shifting ─────────────────────────────────────────────────────

# Columns whose values are ISO timestamps we need to shift forward so they
# appear "now-ish" to the dashboard. Anything not in this map is copied as-is.
ORDERS_TS_COLS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
ITEMS_TS_COLS = ("shipping_limit_date",)
REVIEWS_TS_COLS = ("review_creation_date", "review_answer_timestamp")
# Payments carry no timestamp of their own.


def _shift_ts(value: str | None, offset_days: int) -> str | None:
    """Shift an ISO timestamp string forward by `offset_days`. None passes through."""
    if not value:
        return value
    try:
        # The bronze layer stores everything as TEXT; tolerate both date and
        # datetime forms.
        if " " in value or "T" in value:
            dt = datetime.fromisoformat(value.replace(" ", "T"))
        else:
            dt = datetime.fromisoformat(value + "T00:00:00")
    except ValueError:
        return value  # malformed; preserve so dbt surfaces it via its tests
    return (dt + timedelta(days=offset_days)).isoformat(sep=" ")


def _shifted(row: dict[str, Any], cols: Iterable[str], offset_days: int) -> dict[str, Any]:
    out = dict(row)
    for c in cols:
        if c in out:
            out[c] = _shift_ts(out[c], offset_days)
    return out


# ── Insert into bronze.*_live ──────────────────────────────────────────────

def _insert_orders(conn, rows: list[dict[str, Any]], synthetic_today: date, run_id: int) -> int:
    if not rows:
        return 0
    cols = (
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "_synthetic_date",
        "_ingest_run_id",
    )
    values = [tuple(r.get(c) for c in cols[:-2]) + (synthetic_today, run_id) for r in rows]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO bronze.orders_live ({', '.join(cols)}) VALUES %s",
            values,
            page_size=2000,
        )
    return len(rows)


def _insert_items(conn, rows: list[dict[str, Any]], synthetic_today: date, run_id: int) -> int:
    if not rows:
        return 0
    cols = (
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
        "_synthetic_date", "_ingest_run_id",
    )
    values = [tuple(r.get(c) for c in cols[:-2]) + (synthetic_today, run_id) for r in rows]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO bronze.order_items_live ({', '.join(cols)}) VALUES %s",
            values,
            page_size=2000,
        )
    return len(rows)


def _insert_reviews(conn, rows: list[dict[str, Any]], synthetic_today: date, run_id: int) -> int:
    if not rows:
        return 0
    cols = (
        "review_id", "order_id", "review_score",
        "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp",
        "_synthetic_date", "_ingest_run_id",
    )
    values = [tuple(r.get(c) for c in cols[:-2]) + (synthetic_today, run_id) for r in rows]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO bronze.order_reviews_live ({', '.join(cols)}) VALUES %s",
            values,
            page_size=2000,
        )
    return len(rows)


def _insert_payments(conn, rows: list[dict[str, Any]], synthetic_today: date, run_id: int) -> int:
    if not rows:
        return 0
    cols = (
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value",
        "_synthetic_date", "_ingest_run_id",
    )
    values = [tuple(r.get(c) for c in cols[:-2]) + (synthetic_today, run_id) for r in rows]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO bronze.order_payments_live ({', '.join(cols)}) VALUES %s",
            values,
            page_size=2000,
        )
    return len(rows)


# ── Cursor advance ─────────────────────────────────────────────────────────

def _next_day(d: date) -> date:
    """Advance one day with wrap at the dataset end."""
    nxt = d + timedelta(days=1)
    return REPLAY_START if nxt > REPLAY_END else nxt


# ── Public API — used by Dagster ───────────────────────────────────────────

def tick(*, dry_run: bool = False) -> ReplayResult:
    """Advance the synthetic cursor by one day and ingest that slice.

    Returns a `ReplayResult` so the caller can attach it to Dagster asset
    metadata. Never raises for an empty slice — that's a valid "noop" tick
    (the source has no rows on that day).
    """
    conn = _conn()
    conn.autocommit = False
    run_id: int | None = None
    try:
        synthetic_today = _read_cursor(conn)
        offset_days = (date.today() - synthetic_today).days

        slice_ = _fetch_slice(conn, synthetic_today)

        if dry_run:
            return ReplayResult(
                synthetic_today=synthetic_today,
                next_synthetic_today=_next_day(synthetic_today),
                run_id=None,
                rows={
                    "orders": len(slice_.orders),
                    "items": len(slice_.items),
                    "reviews": len(slice_.reviews),
                    "payments": len(slice_.payments),
                },
                status="dry_run",
            )

        run_id = _open_run(conn, synthetic_today)

        rows_orders = _insert_orders(
            conn,
            [_shifted(r, ORDERS_TS_COLS, offset_days) for r in slice_.orders],
            synthetic_today, run_id,
        )
        rows_items = _insert_items(
            conn,
            [_shifted(r, ITEMS_TS_COLS, offset_days) for r in slice_.items],
            synthetic_today, run_id,
        )
        rows_reviews = _insert_reviews(
            conn,
            [_shifted(r, REVIEWS_TS_COLS, offset_days) for r in slice_.reviews],
            synthetic_today, run_id,
        )
        rows_payments = _insert_payments(
            conn,
            slice_.payments,  # payments have no timestamp to shift
            synthetic_today, run_id,
        )

        total = rows_orders + rows_items + rows_reviews + rows_payments
        status = "success" if total > 0 else "noop"
        _close_run(
            conn,
            run_id=run_id,
            rows={
                "orders": rows_orders, "items": rows_items,
                "reviews": rows_reviews, "payments": rows_payments,
            },
            status=status,
        )

        next_day = _next_day(synthetic_today)
        _advance_cursor(conn, current=synthetic_today, next_day=next_day, run_id=run_id, rows=total)

        conn.commit()

        return ReplayResult(
            synthetic_today=synthetic_today,
            next_synthetic_today=next_day,
            run_id=run_id,
            rows={
                "orders": rows_orders, "items": rows_items,
                "reviews": rows_reviews, "payments": rows_payments,
            },
            status=status,
        )

    except Exception as e:
        conn.rollback()
        # Best-effort: record the failure if we had opened a run already.
        if run_id is not None:
            try:
                _close_run(conn, run_id=run_id, rows={}, status="failed", error=str(e)[:500])
                conn.commit()
            except Exception:
                conn.rollback()
        raise
    finally:
        conn.close()


def reset_cursor(target: date) -> None:
    """Manual recovery — point the cursor at an arbitrary date inside the window."""
    if not (REPLAY_START <= target <= REPLAY_END):
        raise ValueError(f"target {target} outside replay window {REPLAY_START}..{REPLAY_END}")
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE replay.state SET synthetic_today = %s WHERE id = 1", (target,))
        conn.commit()


# ── CLI ────────────────────────────────────────────────────────────────────

def _print_result(result: ReplayResult) -> None:
    payload = result.to_dict()
    # JSON to stdout — Dagster captures this for asset metadata.
    print(json.dumps(payload, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="Olist replay simulator — advances synthetic clock by one day per tick.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no writes.")
    parser.add_argument("--reset", metavar="YYYY-MM-DD", help="Point the cursor at this date and exit.")
    args = parser.parse_args()

    if args.reset:
        target = date.fromisoformat(args.reset)
        reset_cursor(target)
        print(json.dumps({"action": "reset", "synthetic_today": target.isoformat()}))
        return 0

    started = datetime.now(UTC)
    try:
        result = tick(dry_run=args.dry_run)
    except Exception as e:
        print(json.dumps({"status": "failed", "error": str(e)}), file=sys.stderr)
        return 1

    _print_result(result)
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print(f"# tick completed in {elapsed:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
