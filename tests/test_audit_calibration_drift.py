"""Tests for the fold-level calibration-drift audit."""

from __future__ import annotations

from scripts.audit_calibration_drift import build_drift_report


def test_drift_report_computes_coverage_after_abstention() -> None:
    summary = {
        "input": "data.csv",
        "model_type": "logistic",
        "folds": [
            {
                "fold_id": 0,
                "test_rows": 10,
                "threshold_selection": {
                    "calibration_metrics": {
                        "positive_rate": 0.1,
                        "ece": 0.01,
                        "brier_score": 0.04,
                    }
                },
                "calibrated_metrics": {
                    "positive_rate": 0.4,
                    "ece": 0.3,
                    "brier_score": 0.35,
                },
            },
            {
                "fold_id": 1,
                "test_rows": 10,
                "threshold_selection": {
                    "calibration_metrics": {
                        "positive_rate": 0.1,
                        "ece": 0.01,
                        "brier_score": 0.04,
                    }
                },
                "calibrated_metrics": {
                    "positive_rate": 0.1,
                    "ece": 0.02,
                    "brier_score": 0.05,
                },
            },
        ],
    }

    report = build_drift_report(summary)

    assert report["aggregate"]["abstain_fold_ids"] == [0]
    assert report["aggregate"]["coverage"] == 0.5
    assert report["aggregate"]["selective_risk"] == 0.1
