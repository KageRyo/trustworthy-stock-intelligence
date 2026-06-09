"""Tests for trust experiment report generation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.report_trust_experiment import (
    parse_args,
    render_report,
    run_report,
    select_sweep_candidate,
)


def test_select_sweep_candidate_prefers_matching_coverage_band() -> None:
    sweep = pd.DataFrame(
        {
            "coverage": [0.1, 0.3, 0.8],
            "selective_risk": [0.01, 0.2, 0.9],
            "alert_precision": [0.5, 0.4, 0.9],
            "alert_false_alarm_rate": [0.1, 0.2, 0.3],
        }
    )

    candidate = select_sweep_candidate(
        sweep,
        coverage_min=0.25,
        coverage_max=0.5,
        sort_columns=("selective_risk",),
        ascending=(True,),
    )

    assert candidate["coverage"] == 0.3


def test_select_sweep_candidate_can_require_alerting_policy() -> None:
    sweep = pd.DataFrame(
        {
            "coverage": [0.3, 0.4],
            "selective_risk": [0.1, 0.2],
            "alert_rate": [0.0, 0.02],
        }
    )

    candidate = select_sweep_candidate(
        sweep,
        coverage_min=0.25,
        coverage_max=0.5,
        alert_rate_min=0.005,
        sort_columns=("selective_risk",),
        ascending=(True,),
    )

    assert candidate["alert_rate"] == 0.02


def test_render_report_contains_core_sections() -> None:
    summary = {
        "model_config": {"d_model": 16},
        "training_config": {"epochs": 1},
        "trust_config": {"calibration_method": "platt"},
        "summary": {
            "raw": {"auc": 0.6, "f1": 0.2},
            "calibrated": {"auc": 0.6, "f1": 0.1},
            "tuned": {"auc": 0.6, "f1": 0.25},
        },
    }
    warning_eval = {
        "row_count": 10,
        "overall": {
            "alert_count": 1.0,
            "watch_count": 2.0,
            "coverage": 0.3,
            "selective_risk": 0.2,
        },
    }
    sweep = pd.DataFrame(
        {
            "coverage": [0.3],
            "selective_risk": [0.2],
            "alert_precision": [0.5],
            "alert_false_alarm_rate": [0.1],
        }
    )

    report = render_report(summary, warning_eval, sweep)

    assert "# Temporal Transformer Trust Experiment Report" in report
    assert "## Warning-Level Distribution" in report
    assert "## Threshold Sweep Candidates" in report


def test_run_report_writes_markdown(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    warning_eval_path = tmp_path / "warning_eval.json"
    sweep_path = tmp_path / "threshold_sweep.csv"
    output_path = tmp_path / "report.md"

    summary_path.write_text(
        json.dumps(
            {
                "model_config": {"d_model": 16},
                "training_config": {"epochs": 1},
                "trust_config": {"calibration_method": "platt"},
                "summary": {"tuned": {"auc": 0.6}},
            }
        ),
        encoding="utf-8",
    )
    warning_eval_path.write_text(
        json.dumps({"row_count": 2, "overall": {"coverage": 0.5}}),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "coverage": [0.5],
            "selective_risk": [0.2],
            "alert_precision": [0.4],
            "alert_false_alarm_rate": [0.1],
        }
    ).to_csv(sweep_path, index=False)

    args = parse_args(
        [
            "--summary",
            str(summary_path),
            "--warning-eval",
            str(warning_eval_path),
            "--threshold-sweep",
            str(sweep_path),
            "--output",
            str(output_path),
        ]
    )
    run_report(args)

    assert output_path.exists()
    assert "Temporal Transformer Trust Experiment Report" in output_path.read_text(encoding="utf-8")
