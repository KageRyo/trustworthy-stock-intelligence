"""Tests for trust threshold sweep diagnostics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.sweep_warning_thresholds import (
    assign_swept_warning_levels,
    parse_float_grid,
    parse_string_grid,
    run_sweep,
)


def test_parse_float_grid_rejects_empty_values() -> None:
    assert parse_float_grid("0.1, 0.2") == [0.1, 0.2]

    try:
        parse_float_grid("")
    except ValueError as error:
        assert "must not be empty" in str(error)
    else:
        raise AssertionError("Expected ValueError for empty grid")


def test_parse_string_grid_rejects_unknown_values() -> None:
    assert parse_string_grid("subtractive, multiplicative", choices=("subtractive", "multiplicative")) == [
        "subtractive",
        "multiplicative",
    ]

    try:
        parse_string_grid("unknown", choices=("subtractive", "multiplicative"))
    except ValueError as error:
        assert "Unsupported value" in str(error)
    else:
        raise AssertionError("Expected ValueError for unknown string grid value")


def test_assign_swept_warning_levels_uses_ratio_and_trust_threshold() -> None:
    levels = assign_swept_warning_levels(
        calibrated_probabilities=np.array([0.9, 0.9, 0.65, 0.2]),
        alert_thresholds=np.array([0.8, 0.8, 0.8, 0.8]),
        uncertainty_scores=np.array([0.2, 0.9, 0.2, 0.9]),
        trust_scores=np.array([0.7, 0.2, 0.2, 0.2]),
        watch_threshold_ratio=0.75,
        min_watch_threshold=0.05,
        trust_threshold=0.5,
        uncertainty_threshold=0.8,
    )

    assert levels.tolist() == ["alert", "watch", "watch", "abstain"]


def test_run_sweep_outputs_one_row_per_parameter_combination(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    predictions = pd.DataFrame(
        {
            "risk_label": [1, 0, 1, 0],
            "calibrated_risk_probability": [0.9, 0.7, 0.2, 0.1],
            "uncertainty_score": [0.1, 0.2, 0.9, 0.1],
            "alert_threshold": [0.8, 0.8, 0.8, 0.8],
        }
    )
    predictions.to_csv(input_path, index=False)

    results = run_sweep(
        predictions,
        watch_threshold_ratios=[0.75, 0.9],
        trust_thresholds=[0.5],
        uncertainty_thresholds=[0.8],
        uncertainty_penalties=[0.5],
        trust_score_methods=["subtractive", "multiplicative"],
        min_watch_threshold=0.05,
    )

    assert len(results) == 4
    assert results["watch_threshold_ratio"].tolist() == [0.75, 0.75, 0.9, 0.9]
    assert results["trust_score_method"].tolist() == [
        "subtractive",
        "multiplicative",
        "subtractive",
        "multiplicative",
    ]
    assert "coverage" in results.columns
