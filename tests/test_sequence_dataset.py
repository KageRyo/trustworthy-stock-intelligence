"""Tests for leakage-aware sequence dataset construction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsi.training.dataset import build_sequence_dataset


def test_sequence_dataset_aligns_window_end_with_target_row() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates.tolist() * 2,
            "ticker": ["AAA"] * 5 + ["BBB"] * 5,
            "feature": list(range(5)) + list(range(10, 15)),
            "risk_label": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    dataset = build_sequence_dataset(frame, feature_columns=["feature"], lookback=3)

    assert dataset.x.shape == (6, 3, 1)
    assert dataset.y.tolist() == [0, 1, 0, 1, 0, 1]
    np.testing.assert_array_equal(dataset.x[0, :, 0], np.array([0.0, 1.0, 2.0]))
    np.testing.assert_array_equal(dataset.x[3, :, 0], np.array([10.0, 11.0, 12.0]))
    assert dataset.metadata.loc[0, "ticker"] == "AAA"
    assert dataset.metadata.loc[0, "date"] == pd.Timestamp("2024-01-03")
    assert dataset.metadata.loc[0, "window_start_date"] == pd.Timestamp("2024-01-01")
    assert dataset.metadata.loc[0, "window_end_date"] == pd.Timestamp("2024-01-03")
    assert dataset.metadata.loc[3, "ticker"] == "BBB"


def test_sequence_dataset_drops_windows_with_missing_features_or_labels() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "ticker": ["AAA"] * 5,
            "feature": [1.0, np.nan, 3.0, 4.0, 5.0],
            "risk_label": [0, 1, 0, np.nan, 1],
        }
    )

    dataset = build_sequence_dataset(frame, feature_columns=["feature"], lookback=3)

    assert dataset.x.shape == (1, 3, 1)
    np.testing.assert_array_equal(dataset.x[0, :, 0], np.array([3.0, 4.0, 5.0]))
    assert dataset.y.tolist() == [1]
    assert dataset.metadata.loc[0, "date"] == pd.Timestamp("2024-01-05")


def test_sequence_dataset_rejects_invalid_inputs() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "ticker": ["AAA"] * 3,
            "feature": [1.0, 2.0, 3.0],
            "risk_label": [0, 1, 0],
        }
    )

    try:
        build_sequence_dataset(frame, feature_columns=["feature"], lookback=0)
    except ValueError as error:
        assert "lookback" in str(error)
    else:
        raise AssertionError("Expected ValueError for invalid lookback")

    try:
        build_sequence_dataset(frame, feature_columns=["missing"], lookback=2)
    except ValueError as error:
        assert "Missing required columns" in str(error)
    else:
        raise AssertionError("Expected ValueError for missing feature column")
