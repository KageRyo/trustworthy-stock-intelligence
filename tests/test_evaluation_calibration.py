"""Tests for calibration reliability diagnostics."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.export_reliability_bins import export_reliability_bins, parse_args
from tsi.evaluation.calibration import reliability_bins


def test_reliability_bins_computes_bin_means() -> None:
    y_true = np.array([0, 1, 1, 0])
    y_prob = np.array([0.1, 0.2, 0.8, 1.0])

    bins = reliability_bins(y_true, y_prob, n_bins=2)

    assert bins["count"].tolist() == [2, 2]
    assert math.isclose(bins.loc[0, "mean_predicted_probability"], 0.15)
    assert math.isclose(bins.loc[0, "observed_positive_rate"], 0.5)
    assert math.isclose(bins.loc[1, "mean_predicted_probability"], 0.9)
    assert math.isclose(bins.loc[1, "observed_positive_rate"], 0.5)


def test_reliability_bins_rejects_invalid_probabilities() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        reliability_bins(np.array([1]), np.array([1.2]))


def test_export_reliability_bins_writes_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    output_path = tmp_path / "reliability_bins.csv"
    pd.DataFrame(
        {
            "risk_label": [0, 1, 1, 0],
            "calibrated_risk_probability": [0.1, 0.2, 0.8, 1.0],
        }
    ).to_csv(input_path, index=False)

    args = parse_args(["--input", str(input_path), "--output", str(output_path), "--bins", "2"])
    bins = export_reliability_bins(args)

    assert output_path.exists()
    assert bins["count"].tolist() == [2, 2]
