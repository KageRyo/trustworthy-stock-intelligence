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


def test_walk_forward_split_purges_label_horizon_between_windows() -> None:
    dates = pd.date_range("2024-01-01", periods=16, freq="D")
    frame = pd.DataFrame({"date": dates, "ticker": ["AAA"] * len(dates)})

    fold = build_walk_forward_splits(
        frame,
        train_size=4,
        calibration_size=3,
        test_size=3,
        purge_size=2,
    )[0]

    assert fold.train_dates == tuple(dates[:4])
    assert fold.train_calibration_gap_dates == tuple(dates[4:6])
    assert fold.calibration_dates == tuple(dates[6:9])
    assert fold.calibration_test_gap_dates == tuple(dates[9:11])
    assert fold.test_dates == tuple(dates[11:14])
    assert set(fold.train_index).isdisjoint(fold.calibration_index)
    assert set(fold.calibration_index).isdisjoint(fold.test_index)


def test_walk_forward_split_rejects_negative_purge_size() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=8, freq="D"),
            "ticker": ["AAA"] * 8,
        }
    )

    try:
        build_walk_forward_splits(
            frame,
            train_size=3,
            calibration_size=2,
            test_size=2,
            purge_size=-1,
        )
    except ValueError as error:
        assert "purge_size" in str(error)
    else:
        raise AssertionError("Expected ValueError for negative purge_size")


def test_walk_forward_split_removes_rows_with_labels_overlapping_next_window() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA"] * len(dates),
            "label_end_date": dates,
        }
    )
    frame.loc[3, "label_end_date"] = dates[5]
    frame.loc[7, "label_end_date"] = dates[9]

    fold = build_walk_forward_splits(
        frame,
        train_size=4,
        calibration_size=4,
        test_size=4,
        label_end_date_col="label_end_date",
    )[0]

    assert 3 not in fold.train_index
    assert 7 not in fold.calibration_index
    assert fold.train_label_overlap_removed == 1
    assert fold.calibration_label_overlap_removed == 1
