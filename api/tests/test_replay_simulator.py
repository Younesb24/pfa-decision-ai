"""
Unit tests for `scripts/replay_simulator.py` — pure logic only, no DB.

The DB-touching `tick()` is exercised under `pytest -m integration` (Day 3+
adds an in-process Postgres harness). What we test here is the pure-function
core: timestamp shifting, cursor wrap, malformed-input tolerance.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# Make scripts/ importable without packaging it.
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import replay_simulator as sim  # noqa: E402


class TestShiftTs:
    def test_none_passes_through(self):
        assert sim._shift_ts(None, 30) is None

    def test_empty_string_passes_through(self):
        assert sim._shift_ts("", 30) == ""

    def test_shifts_date_only_string_forward(self):
        # "2017-06-01" + 5 days → "2017-06-06T00:00:00"
        shifted = sim._shift_ts("2017-06-01", 5)
        assert shifted.startswith("2017-06-06")

    def test_shifts_full_datetime_with_space_separator(self):
        shifted = sim._shift_ts("2017-06-01 14:30:00", 10)
        # The separator is normalised to a space by isoformat(sep=" ").
        assert shifted.startswith("2017-06-11 14:30:00")

    def test_shifts_iso_datetime_with_t_separator(self):
        shifted = sim._shift_ts("2017-06-01T14:30:00", 10)
        assert "2017-06-11" in shifted

    def test_malformed_input_passes_through_unchanged(self):
        """Garbage timestamps survive — dbt staging will catch them."""
        assert sim._shift_ts("not-a-date", 5) == "not-a-date"

    def test_zero_offset_is_identity_for_iso_inputs(self):
        # Date-only strings get normalised to T00:00:00 even at offset 0.
        assert sim._shift_ts("2017-06-01 12:00:00", 0).startswith("2017-06-01 12:00:00")


class TestShiftedRow:
    def test_only_listed_columns_are_shifted(self):
        row = {
            "order_id": "abc",
            "order_purchase_timestamp": "2017-06-01 10:00:00",
            "order_status": "delivered",
        }
        out = sim._shifted(row, sim.ORDERS_TS_COLS, 30)
        assert out["order_id"] == "abc"
        assert out["order_status"] == "delivered"
        assert out["order_purchase_timestamp"].startswith("2017-07-01")

    def test_missing_columns_are_ignored(self):
        """Rows with only a subset of TS columns don't blow up."""
        row = {"order_id": "abc", "order_purchase_timestamp": "2017-06-01"}
        out = sim._shifted(row, sim.ORDERS_TS_COLS, 30)
        assert "order_approved_at" not in out  # not present in input

    def test_returns_a_copy_not_in_place_mutation(self):
        row = {"order_purchase_timestamp": "2017-06-01"}
        out = sim._shifted(row, sim.ORDERS_TS_COLS, 30)
        assert row["order_purchase_timestamp"] == "2017-06-01"
        assert out["order_purchase_timestamp"] != "2017-06-01"


class TestCursorAdvance:
    def test_one_day_advance_inside_window(self):
        assert sim._next_day(date(2017, 6, 1)) == date(2017, 6, 2)

    def test_wraps_at_window_end(self):
        assert sim._next_day(sim.REPLAY_END) == sim.REPLAY_START

    def test_advance_at_start_is_simple_increment(self):
        assert sim._next_day(sim.REPLAY_START) == date(2017, 1, 2)

    def test_last_day_in_window_advances_to_next_day_not_wrap(self):
        """Wrap fires only when *next* day exceeds REPLAY_END, not on equality."""
        almost_end = sim.REPLAY_END.replace(day=sim.REPLAY_END.day - 1)
        assert sim._next_day(almost_end) == sim.REPLAY_END


class TestResetCursorValidation:
    def test_rejects_date_before_window(self):
        with pytest.raises(ValueError, match="outside replay window"):
            sim.reset_cursor(date(2016, 12, 31))

    def test_rejects_date_after_window(self):
        with pytest.raises(ValueError, match="outside replay window"):
            sim.reset_cursor(date(2018, 9, 4))

    # The "accepts in-window" case requires a DB and is left for the
    # integration suite — the validation rejection path is enough for unit.
