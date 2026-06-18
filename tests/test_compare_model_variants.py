"""Tests for baseline-vs-Transformer comparison reports."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_model_variants import (
    build_variant_comparison_frame,
    parse_args,
    run_comparison,
)


def _write_run(root: Path, name: str, *, model: str, warning_eval: bool) -> Path:
    run_dir = root / name
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "folds": [{"model": model}],
                "summary": {
                    "raw": {"auc": 0.6, "brier_score": 0.2, "ece": 0.3, "precision": 0.1},
                    "calibrated": {
                        "auc": 0.6,
                        "brier_score": 0.1,
                        "ece": 0.05,
                        "precision": 0.0,
                    },
                    "tuned": {
                        "auc": 0.6,
                        "brier_score": 0.1,
                        "ece": 0.05,
                        "precision": 0.14,
                        "recall": 0.4,
                        "f1": 0.2,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    if warning_eval:
        (run_dir / "warning_eval.json").write_text(
            json.dumps(
                {
                    "overall": {
                        "alert_precision": 0.16,
                        "alert_false_alarm_rate": 0.02,
                        "coverage": 0.5,
                    }
                }
            ),
            encoding="utf-8",
        )
    return run_dir


def test_build_variant_comparison_frame_expands_summary_sections(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, "transformer", model="temporal_transformer", warning_eval=True)

    frame = build_variant_comparison_frame([run_dir])

    assert frame["variant"].tolist() == ["raw", "calibrated", "tuned", "trust_decision"]
    assert frame.loc[frame["variant"] == "trust_decision", "alert_precision"].iloc[0] == 0.16


def test_run_comparison_writes_report(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic", model="logistic_regression", warning_eval=False)
    transformer = _write_run(tmp_path, "transformer", model="temporal_transformer", warning_eval=True)
    output = tmp_path / "baseline_vs_transformer.md"

    args = parse_args(["--runs", str(baseline), str(transformer), "--output", str(output)])
    report = run_comparison(args)

    assert output.exists()
    assert "Baseline vs Transformer Comparison" in report
    assert "trust_decision" in report


def test_build_variant_comparison_frame_accepts_summary_file(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, "logistic", model="logistic_regression", warning_eval=False)
    summary_path = run_dir / "summary.json"

    frame = build_variant_comparison_frame([summary_path])

    assert frame["run"].iloc[0] == "summary"
    assert frame["model"].iloc[0] == "logistic_regression"
