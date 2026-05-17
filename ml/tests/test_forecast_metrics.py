"""
Tests for the safe MAPE / sMAPE / MAE helpers in ml/train_forecast.py.

These existed because a previous training run reported MAPE = 259262%
on a near-zero warm-up day. The helpers floor the denominator and
report sMAPE alongside so a single bad row can't blow up the metric.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# ml/ is a flat directory of scripts; import the helpers directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from train_forecast import _safe_mape, _smape  # noqa: E402


class TestSafeMape:
    def test_zero_actuals_do_not_explode(self):
        """Regression: previous MAPE reported 259262% on warm-up days."""
        actual = np.array([0.0, 1.0, 0.0, 2.0])
        pred = np.array([5.0, 1.0, 3.0, 2.0])
        result = _safe_mape(actual, pred)
        assert result < 500.0, f"safe MAPE blew up: {result}"

    def test_matches_plain_mape_when_no_near_zero(self):
        actual = np.array([100.0, 200.0, 300.0])
        pred = np.array([110.0, 180.0, 330.0])
        plain = float(np.mean(np.abs(actual - pred) / actual) * 100.0)
        safe = _safe_mape(actual, pred, floor=1.0)
        assert abs(plain - safe) < 1e-6

    def test_perfect_prediction_is_zero(self):
        actual = np.array([10.0, 20.0, 30.0])
        assert _safe_mape(actual, actual) == 0.0

    def test_floor_is_configurable(self):
        actual = np.array([0.5])
        pred = np.array([1.5])
        # floor=1.0 → |1.5-0.5| / max(0.5, 1.0) = 1.0 → 100%
        assert _safe_mape(actual, pred, floor=1.0) == pytest.approx(100.0)
        # floor=10.0 → 1.0 / 10.0 → 10%
        assert _safe_mape(actual, pred, floor=10.0) == pytest.approx(10.0)


class TestSmape:
    def test_symmetric(self):
        """sMAPE is symmetric in actual <-> pred (within numerical noise)."""
        a = np.array([100.0, 200.0])
        b = np.array([110.0, 180.0])
        assert _smape(a, b) == pytest.approx(_smape(b, a), abs=1e-6)

    def test_bounded_at_200(self):
        """sMAPE bound: a positive prediction against zero actual = 200%."""
        actual = np.array([0.0, 0.0])
        pred = np.array([10.0, 10.0])
        assert _smape(actual, pred) == pytest.approx(200.0)

    def test_both_zero_is_zero(self):
        assert _smape(np.zeros(3), np.zeros(3)) == 0.0

    def test_perfect_prediction_is_zero(self):
        x = np.array([10.0, 20.0, 30.0])
        assert _smape(x, x) == 0.0
