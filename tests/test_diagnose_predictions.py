"""Tests for prediction diagnostics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.diagnose_predictions import parse_args, run_diagnostics


def test_run_diagnostics_summarizes_probability_and_trust_columns(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    output_path = tmp_path / "diagnostics.json"
    pd.DataFrame(
        {
            "risk_label": [0, 1, 1, 0],
            "calibrated_risk_probability": [0.1, 0.4, 0.8, 0.2],
            "uncertainty_score": [0.9, 0.6, 0.2, 0.8],
            "trust_score": [0.0, 0.1, 0.7, 0.0],
            "alert_threshold": [0.5, 0.5, 0.5, 0.5],
        }
    ).to_csv(input_path, index=False)

    args = parse_args(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--trust-threshold",
            "0.5",
        ]
    )
    diagnostics = run_diagnostics(args)

    assert diagnostics["row_count"] == 4
    assert diagnostics["positive_rate"] == 0.5
    assert diagnostics["columns"]["trust_score"]["mean"] == pytest.approx(0.2)
    assert diagnostics["decision_readiness"]["rows_p_ge_alert"] == 1
    assert diagnostics["decision_readiness"]["rows_p_ge_alert_and_trust_ge_threshold"] == 1
    assert diagnostics["by_label"]["1"]["row_count"] == 2
    assert output_path.exists()
