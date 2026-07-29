"""Tests for paired calibration comparisons."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.compare_calibration import parse_args, run_comparison


def test_run_comparison_reports_fold_and_period_improvements(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2025-01-02", "2025-01-03"],
            "fold_id": [0, 0, 1, 1],
            "risk_label": [0, 1, 0, 1],
            "risk_probability": [0.8, 0.2, 0.7, 0.3],
            "calibrated_risk_probability": [0.1, 0.9, 0.2, 0.8],
        }
    ).to_csv(input_path, index=False)

    result = run_comparison(parse_args(["--input", str(input_path)]))

    overall = result["overall"]
    assert overall["delta_calibrated_minus_raw"]["brier_score"] < 0
    fold_summary = result["by_dimension"]["fold_id"]["improvement_summary"]
    assert fold_summary["brier_score"]["improved_group_count"] == 2
    assert len(result["by_dimension"]["year"]["groups"]) == 2


def test_run_comparison_supports_market_or_sector_dimensions(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    pd.DataFrame(
        {
            "market": ["us", "us", "twse", "twse"],
            "risk_label": [0, 1, 0, 1],
            "risk_probability": [0.7, 0.3, 0.6, 0.4],
            "calibrated_risk_probability": [0.1, 0.9, 0.2, 0.8],
        }
    ).to_csv(input_path, index=False)

    args = parse_args(
        [
            "--input",
            str(input_path),
            "--group-cols",
            "market",
            "--period",
            "none",
        ]
    )
    result = run_comparison(args)

    assert [row["group"] for row in result["by_dimension"]["market"]["groups"]] == [
        "twse",
        "us",
    ]


def test_run_comparison_uses_null_for_undefined_auc(tmp_path: Path) -> None:
    input_path = tmp_path / "predictions.csv"
    pd.DataFrame(
        {
            "market": ["us", "us"],
            "risk_label": [0, 0],
            "risk_probability": [0.7, 0.6],
            "calibrated_risk_probability": [0.1, 0.2],
        }
    ).to_csv(input_path, index=False)

    args = parse_args(
        [
            "--input",
            str(input_path),
            "--group-cols",
            "market",
            "--period",
            "none",
        ]
    )
    result = run_comparison(args)

    assert result["overall"]["raw"]["auc"] is None
    assert result["overall"]["delta_calibrated_minus_raw"]["auc"] is None
