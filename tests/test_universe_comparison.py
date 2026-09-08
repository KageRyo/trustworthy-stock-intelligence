"""Tests for paired current-vs-point-in-time benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tsi.evaluation.universe_comparison import build_universe_comparison_report


def _metrics(seed: float) -> dict[str, float]:
    return {
        "auc": seed,
        "pr_auc": seed - 0.05,
        "brier_score": 0.2,
        "ece": 0.1,
        "precision": 0.6,
        "recall": 0.5,
        "f1": 0.55,
        "miss_rate": 0.5,
        "false_alarm_rate": 0.2,
        "false_discovery_rate": 0.4,
        "prediction_rate": 0.25,
    }


def _write_run(
    root: Path,
    name: str,
    *,
    date_window: str = "2020-01-05",
    purge_size: int = 5,
) -> Path:
    run_dir = root / name
    run_dir.mkdir()
    summary = {
        "run_id": name,
        "input_sha256": name[0] * 64,
        "model_type": "logistic",
        "model_config": {"random_state": 42},
        "feature_columns": ["return_1d", "volatility_5d"],
        "label_column": "risk_label",
        "horizon": 5,
        "drawdown_threshold": -0.05,
        "purge_size": purge_size,
        "train_size": 252,
        "calibration_size": 63,
        "test_size": 63,
        "step_size": 63,
        "calibration_method": "platt",
        "threshold_objective": "f1",
        "rows_after_filtering": 4,
        "universe_membership": {
            "status": "not_supplied" if name == "baseline" else "valid",
            "schema_version": "point_in_time_universe.v2" if name != "baseline" else None,
            "membership_count": 2 if name != "baseline" else None,
            "membership_sha256": "c" * 64 if name != "baseline" else None,
            "source_license": "research-only" if name != "baseline" else None,
        },
        "folds": [
            {
                "fold_id": 0,
                "train_start": "2020-01-01",
                "train_end": "2020-01-02",
                "calibration_start": "2020-01-03",
                "calibration_end": "2020-01-04",
                "test_start": date_window,
                "test_end": "2020-01-06",
                "prior_metrics": _metrics(0.5),
                "raw_metrics": _metrics(0.55),
                "calibrated_metrics": _metrics(0.6),
                "tuned_metrics": _metrics(0.6),
            }
        ],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    rows = {
        "fold_id": [0, 0],
        "ticker": ["AAA", "BBB"] if name == "baseline" else ["AAA", "CCC"],
        "date": ["2020-01-05", "2020-01-06"],
        "risk_label": [0, 1],
    }
    pd.DataFrame(rows).to_csv(run_dir / "predictions.csv", index=False)
    return run_dir / "summary.json"


def _write_membership_files(root: Path) -> tuple[Path, Path]:
    baseline = root / "baseline-membership.csv"
    comparison = root / "comparison-membership.csv"
    pd.DataFrame(
        {
            "security_id": ["sec-a", "sec-b"],
            "ticker": ["AAA", "BBB"],
            "valid_from": ["2020-01-01", "2020-01-01"],
        }
    ).to_csv(baseline, index=False)
    pd.DataFrame(
        {
            "security_id": ["sec-a", "sec-c"],
            "ticker": ["AAA", "CCC"],
            "valid_from": ["2020-01-01", "2020-01-01"],
            "valid_to": [None, None],
            "known_at": ["2020-01-01", "2020-01-01"],
        }
    ).to_csv(comparison, index=False)
    return baseline, comparison


def test_paired_report_is_deterministic_and_only_contains_aggregate_coverage(
    tmp_path: Path,
) -> None:
    baseline = _write_run(tmp_path, "baseline")
    comparison = _write_run(tmp_path, "comparison")
    baseline_membership, comparison_membership = _write_membership_files(tmp_path)

    first = build_universe_comparison_report(
        baseline,
        comparison,
        baseline_membership_path=baseline_membership,
        comparison_membership_path=comparison_membership,
        seed=7,
        resamples=50,
    )
    second = build_universe_comparison_report(
        baseline,
        comparison,
        baseline_membership_path=baseline_membership,
        comparison_membership_path=comparison_membership,
        seed=7,
        resamples=50,
    )

    assert first == second
    assert first["claim_status"] == "comparable"
    assert first["coverage"]["evaluation_rows_added_count"] == 1
    assert first["coverage"]["evaluation_rows_removed_count"] == 1
    assert first["coverage"]["membership_rows_added_count"] == 1
    assert first["coverage"]["membership_rows_removed_count"] == 1
    assert first["metrics"]["calibrated"]["roc_auc"]["available"] is True
    assert first["metrics"]["calibrated"]["lead_time"]["available"] is False
    assert "CCC" not in json.dumps(first)


def test_paired_report_fails_on_protocol_or_date_mismatch(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "baseline")
    comparison = _write_run(tmp_path, "comparison", date_window="2020-01-07")

    with pytest.raises(ValueError, match="date windows"):
        build_universe_comparison_report(baseline, comparison, resamples=20)

    comparison = _write_run(tmp_path, "comparison-protocol", purge_size=4)
    with pytest.raises(ValueError, match="benchmark protocol"):
        build_universe_comparison_report(baseline, comparison, resamples=20)


def test_paired_report_fails_on_feature_and_model_contract_mismatch(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "baseline")
    comparison = _write_run(tmp_path, "comparison")
    payload = json.loads(comparison.read_text(encoding="utf-8"))
    payload["feature_columns"] = ["different_feature"]
    comparison.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="feature contract"):
        build_universe_comparison_report(baseline, comparison, resamples=20)

    payload["feature_columns"] = ["return_1d", "volatility_5d"]
    payload["model_config"] = {"random_state": 99}
    comparison.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="model configuration"):
        build_universe_comparison_report(baseline, comparison, resamples=20)
