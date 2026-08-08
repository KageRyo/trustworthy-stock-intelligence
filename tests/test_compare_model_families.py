"""Tests for identical-protocol model-family audits."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.compare_model_families import build_model_family_report, render_report


def _write_run(root: Path, model: str, *, mismatch: bool = False) -> Path:
    run_dir = root / model
    run_dir.mkdir()
    summary = {
        "model_type": model,
        "feature_columns": ["return_1d"],
        "horizon": 5,
        "purge_size": 5,
        "train_size": 252,
        "calibration_size": 63,
        "test_size": 63,
        "step_size": 63,
        "drawdown_threshold": -0.05,
        "calibration_method": "platt",
        "threshold_objective": "f1",
        "fold_count": 1,
        "rows_after_filtering": 4,
        "folds": [
            {
                "fold_id": 0,
                "train_start": "2020-01-01",
                "train_end": "2020-01-02",
                "calibration_start": "2020-01-03",
                "calibration_end": "2020-01-04",
                "test_start": "2020-01-05",
                "test_end": "2020-01-06",
                "train_rows": 2,
                "calibration_rows": 1,
                "test_rows": 1,
                "raw_metrics": {"auc": 0.5},
                "calibrated_metrics": {"auc": 0.6},
                "tuned_metrics": {"f1": 0.2},
            }
        ],
        "summary": {
            "calibrated": {"auc": 0.6, "pr_auc": 0.6, "brier_score": 0.2, "ece": 0.1},
            "tuned": {"f1": 0.2, "false_discovery_rate": 0.8},
        },
        "summary_std": {},
    }
    if mismatch:
        summary["purge_size"] = 4
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    dates = ["2020-01-05", "2020-01-06"] if not mismatch else ["2020-01-05", "2020-01-07"]
    pd.DataFrame(
        {
            "fold_id": [0, 0],
            "ticker": ["AAA", "BBB"],
            "date": dates,
            "risk_label": [0, 1],
        }
    ).to_csv(run_dir / "predictions.csv", index=False)
    return run_dir / "summary.json"


def test_model_family_report_audits_shared_keys(tmp_path: Path) -> None:
    logistic = _write_run(tmp_path, "logistic")
    forest = _write_run(tmp_path, "random_forest")

    report = build_model_family_report([logistic, forest])

    assert report["sample_key_audit"]["identical"] is True
    assert report["sample_key_audit"]["shared_row_count"] == 2
    assert "Deep Model Boundary" in render_report(report)


def test_model_family_report_rejects_protocol_mismatch(tmp_path: Path) -> None:
    logistic = _write_run(tmp_path, "logistic")
    forest = _write_run(tmp_path, "random_forest", mismatch=True)

    with pytest.raises(ValueError, match="identical temporal protocols"):
        build_model_family_report([logistic, forest])
