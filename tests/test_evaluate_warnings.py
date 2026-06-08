"""Tests for the trust-aware warning evaluation CLI."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.evaluate_warnings import parse_args, run_evaluation


def test_evaluate_warnings_reports_overall_and_group_metrics(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    pd.DataFrame(
        {
            "fold_id": [0, 0, 1, 1],
            "risk_label": [1, 0, 1, 0],
            "warning_level": ["alert", "watch", "abstain", "no_alert"],
            "trust_score": [0.8, 0.4, 0.1, 0.2],
            "uncertainty_score": [0.2, 0.5, 0.9, 0.3],
        }
    ).to_csv(input_path, index=False)

    args = parse_args(["--input", str(input_path)])
    results = run_evaluation(args)

    assert results["row_count"] == 4
    assert results["overall"]["alert_count"] == 1.0
    assert results["overall"]["coverage"] == 0.5
    assert len(results["by_group"]) == 2
    assert results["by_group"][0]["group"] == 0
