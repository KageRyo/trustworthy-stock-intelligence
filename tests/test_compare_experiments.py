"""Tests for experiment comparison reports."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_experiments import build_comparison_frame, parse_args, run_comparison


def _write_run(
    root: Path,
    name: str,
    *,
    trust_score_method: str,
    alert_rate: float,
) -> Path:
    run_dir = root / name
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "trust_config": {
                    "trust_score_method": trust_score_method,
                    "calibration_method": "platt",
                    "uncertainty_method": "entropy",
                },
                "summary": {
                    "calibrated": {"auc": 0.61, "brier_score": 0.08, "ece": 0.02},
                    "tuned": {"precision": 0.2, "recall": 0.1, "f1": 0.13},
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "warning_eval.json").write_text(
        json.dumps(
            {
                "row_count": 100,
                "overall": {
                    "alert_rate": alert_rate,
                    "watch_rate": 0.4,
                    "no_alert_rate": 0.6 - alert_rate,
                    "alert_precision": 0.15,
                    "alert_recall": 0.04,
                    "alert_false_alarm_rate": 0.02,
                    "coverage": 0.4 + alert_rate,
                    "selective_risk": 0.16,
                },
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def test_build_comparison_frame_loads_core_metrics(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, "multiplicative", trust_score_method="multiplicative", alert_rate=0.02)

    frame = build_comparison_frame([run_dir])

    assert frame.loc[0, "run"] == "multiplicative"
    assert frame.loc[0, "trust_score_method"] == "multiplicative"
    assert frame.loc[0, "alert_rate"] == 0.02
    assert frame.loc[0, "calibrated_ece"] == 0.02


def test_run_comparison_writes_markdown(tmp_path: Path) -> None:
    subtractive = _write_run(tmp_path, "subtractive", trust_score_method="subtractive", alert_rate=0.0)
    multiplicative = _write_run(
        tmp_path,
        "multiplicative",
        trust_score_method="multiplicative",
        alert_rate=0.025,
    )
    output = tmp_path / "comparison.md"

    args = parse_args(["--runs", str(subtractive), str(multiplicative), "--output", str(output)])
    report = run_comparison(args)

    assert output.exists()
    assert "Experiment Comparison Report" in report
    assert "subtractive-versus-multiplicative" in report
