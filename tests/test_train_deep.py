"""Tests for the deep training entrypoint helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

train_deep = pytest.importorskip("scripts.train_deep")


def test_subset_sequence_dataset_uses_source_indices() -> None:
    dataset = train_deep.SequenceDataset(
        x=np.arange(24, dtype=np.float32).reshape(4, 3, 2),
        y=np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32),
        metadata=pd.DataFrame(
            {
                "ticker": ["AAA", "AAA", "BBB", "BBB"],
                "date": pd.date_range("2024-01-01", periods=4, freq="D"),
                "source_index": [10, 11, 20, 21],
                "window_start_date": pd.date_range("2023-12-01", periods=4, freq="D"),
                "window_end_date": pd.date_range("2024-01-01", periods=4, freq="D"),
            }
        ),
        feature_columns=("f1", "f2"),
        lookback=3,
    )

    subset = train_deep.subset_sequence_dataset(dataset, [21, 10])

    assert subset.x.shape == (2, 3, 2)
    assert subset.y.tolist() == [0.0, 1.0]
    assert subset.metadata["source_index"].tolist() == [10, 21]


def test_parse_args_supports_trust_score_method() -> None:
    args = train_deep.parse_args(["--input", "data.csv"])

    assert args.trust_score_method == "subtractive"

    args = train_deep.parse_args(["--input", "data.csv", "--trust-score-method", "multiplicative"])

    assert args.trust_score_method == "multiplicative"


def test_build_prediction_frame_matches_baseline_schema() -> None:
    metadata = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "source_index": [1, 2],
            "window_start_date": pd.date_range("2023-12-01", periods=2, freq="D"),
            "window_end_date": pd.date_range("2024-01-01", periods=2, freq="D"),
        }
    )

    frame = train_deep.build_prediction_frame(
        metadata,
        labels=np.array([0.0, 1.0], dtype=np.float32),
        probabilities=np.array([0.25, 0.75], dtype=float),
        calibrated_probabilities=np.array([0.2, 0.8], dtype=float),
        calibration_method="platt",
        uncertainty_scores=np.array([0.3, 0.4], dtype=float),
        trust_scores=np.array([0.1, 0.6], dtype=float),
        alert_threshold=0.7,
        warning_levels=np.array(["no_alert", "alert"], dtype=object),
        fold_id=3,
        model_name="temporal_transformer",
    )

    assert frame.columns.tolist() == [
        "date",
        "ticker",
        "risk_label",
        "fold_id",
        "model",
        "risk_probability",
        "calibrated_risk_probability",
        "calibration_method",
        "uncertainty_score",
        "trust_score",
        "alert_threshold",
        "warning_level",
    ]
    assert frame["risk_label"].tolist() == [0, 1]
    assert frame["risk_probability"].tolist() == [0.25, 0.75]
    assert frame["calibrated_risk_probability"].tolist() == [0.2, 0.8]
    assert frame["warning_level"].tolist() == ["no_alert", "alert"]
