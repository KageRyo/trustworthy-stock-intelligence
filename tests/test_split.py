"""Tests for temporal split protocols."""

from __future__ import annotations

import pandas as pd

from tsi.data.split import build_walk_forward_splits


def test_walk_forward_split_preserves_temporal_order() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates.tolist() * 2,
            "ticker": ["AAA"] * 12 + ["BBB"] * 12,
            "value": range(24),
        }
    )

    folds = build_walk_forward_splits(
        frame,
        train_size=4,
        calibration_size=2,
        test_size=2,
        step_size=2,
    )

    assert len(folds) == 3
    first_fold = folds[0]
    assert first_fold.train_dates[-1] < first_fold.calibration_dates[0]
    assert first_fold.calibration_dates[-1] < first_fold.test_dates[0]
    assert len(first_fold.train_index) == 8
    assert len(first_fold.calibration_index) == 4
    assert len(first_fold.test_index) == 4


def test_walk_forward_split_rejects_short_history() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "ticker": ["AAA"] * 5,
        }
    )

    try:
        build_walk_forward_splits(frame, train_size=3, calibration_size=2, test_size=2)
    except ValueError as error:
        assert "Not enough unique dates" in str(error)
    else:
        raise AssertionError("Expected ValueError for short history")
