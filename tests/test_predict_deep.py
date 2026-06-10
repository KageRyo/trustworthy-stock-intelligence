"""Tests for deep prediction entrypoint helpers."""

from __future__ import annotations

import pandas as pd

import numpy as np

from scripts.predict_deep import (
    build_inference_frame,
    build_latest_sequence_dataset,
    parse_args,
    select_latest_per_ticker,
    select_latest_sequence_dataset,
)
from tsi.training.dataset import SequenceDataset


def test_parse_args_defaults_to_auto_device() -> None:
    args = parse_args(["--input", "input.csv", "--model-bundle", "bundle", "--output", "out.csv"])

    assert args.device == "auto"
    assert args.latest_only is False
    assert args.json_output is None


def test_parse_args_supports_json_output() -> None:
    args = parse_args(
        [
            "--input",
            "input.csv",
            "--model-bundle",
            "bundle",
            "--output",
            "out.csv",
            "--json-output",
            "warnings.json",
        ]
    )

    assert str(args.json_output) == "warnings.json"


def test_build_inference_frame_adds_dummy_labels_without_future_labeling() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=12, freq="D"),
            "ticker": ["AAA"] * 12,
            "open": range(12),
            "high": range(1, 13),
            "low": range(12),
            "close": range(1, 13),
            "adj_close": range(1, 13),
            "volume": [100] * 12,
        }
    )

    inference = build_inference_frame(frame, feature_columns=("return_1d", "return_5d"))

    assert "risk_label" in inference.columns
    assert inference["risk_label"].eq(0).all()
    assert inference[["return_1d", "return_5d"]].notna().all().all()


def test_select_latest_per_ticker_keeps_latest_rows() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-02"]),
            "ticker": ["AAA", "AAA", "BBB"],
            "risk_probability": [0.1, 0.2, 0.3],
        }
    )

    latest = select_latest_per_ticker(frame)

    assert latest["ticker"].tolist() == ["AAA", "BBB"]
    assert latest["risk_probability"].tolist() == [0.2, 0.3]


def test_build_latest_sequence_dataset_builds_one_window_per_ticker() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4, freq="D").tolist() * 2,
            "ticker": ["AAA"] * 4 + ["BBB"] * 4,
            "feature_a": [1, 2, 3, 4, 10, 20, 30, 40],
        }
    )

    dataset = build_latest_sequence_dataset(frame, feature_columns=("feature_a",), lookback=3)

    assert dataset.x.shape == (2, 3, 1)
    assert dataset.y.tolist() == [0.0, 0.0]
    assert dataset.metadata["ticker"].tolist() == ["AAA", "BBB"]
    assert dataset.metadata["date"].tolist() == [pd.Timestamp("2024-01-04")] * 2
    np.testing.assert_array_equal(
        dataset.x.squeeze(-1),
        np.asarray([[2, 3, 4], [20, 30, 40]], dtype=np.float32),
    )


def test_select_latest_sequence_dataset_filters_before_inference() -> None:
    dataset = SequenceDataset(
        x=np.arange(12, dtype=np.float32).reshape(4, 3, 1),
        y=np.zeros(4, dtype=np.float32),
        metadata=pd.DataFrame(
            {
                "ticker": ["AAA", "AAA", "BBB", "BBB"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-02", "2024-01-04"]),
                "source_index": [1, 2, 3, 4],
                "window_start_date": pd.to_datetime(
                    ["2023-12-30", "2024-01-01", "2023-12-31", "2024-01-02"]
                ),
                "window_end_date": pd.to_datetime(
                    ["2024-01-01", "2024-01-03", "2024-01-02", "2024-01-04"]
                ),
            }
        ),
        feature_columns=("feature_a",),
        lookback=3,
    )

    latest = select_latest_sequence_dataset(dataset)

    assert latest.metadata["ticker"].tolist() == ["AAA", "BBB"]
    assert latest.metadata["source_index"].tolist() == [2, 4]
    np.testing.assert_array_equal(latest.x[:, 0, 0], np.array([3, 9], dtype=np.float32))
