"""Tests for the fail-closed deep benchmark audit."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_deep_alignment import build_alignment_report, render_report


INPUT_SHA256 = "a" * 64
NO_MEMBERSHIP = {
    "status": "not_supplied",
    "note": "The benchmark uses the input snapshot without point-in-time membership filtering.",
}


def _write_run(
    root: Path,
    name: str,
    *,
    mismatch: bool = False,
    input_sha256: str = INPUT_SHA256,
    fold_id: int = 0,
) -> Path:
    run_dir = root / name
    run_dir.mkdir()
    summary = {
        "model_type": name,
        "input_sha256": input_sha256,
        "training_config": {
            "device": "cuda",
            "max_gpu_count": 1,
            "used_data_parallel": False,
        },
        "universe_membership": NO_MEMBERSHIP,
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
        "folds": [{"fold_id": fold_id, "model": name}],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    dates = ["2026-01-02", "2026-01-03"] if not mismatch else ["2026-01-02", "2026-01-04"]
    pd.DataFrame(
        {
            "fold_id": [fold_id, fold_id],
            "ticker": ["0050", "2330"],
            "date": dates,
            "risk_label": [0, 1],
            "risk_probability": [0.2, 0.8],
            "calibrated_risk_probability": [0.1, 0.9],
            "alert_threshold": [0.5, 0.5],
        }
    ).to_csv(run_dir / "predictions.csv", index=False)
    return run_dir / "summary.json"


def test_alignment_report_requires_complete_comparable_artifacts(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer")

    report = build_alignment_report(baseline, deep, expected_fold_count=1)

    assert report["aligned"] is True
    assert report["quality_comparison_allowed"] is False
    assert report["shared_row_count"] == 2
    assert len(report["sample_key_sha256"]) == 64
    assert report["metrics"]["deep"]["aggregate"]["tuned"]["f1"] == 1.0
    assert "smoke/custom audit" in render_report(report)


def test_alignment_report_fails_closed_on_key_mismatch(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer", mismatch=True)

    with pytest.raises(ValueError, match="sample keys are not identical"):
        build_alignment_report(baseline, deep, expected_fold_count=1)


def test_alignment_report_fails_closed_on_input_snapshot_mismatch(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer", input_sha256="b" * 64)

    with pytest.raises(ValueError, match="input snapshot mismatch"):
        build_alignment_report(baseline, deep, expected_fold_count=1)


def test_alignment_report_requires_contiguous_expected_folds(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic", fold_id=1)
    deep = _write_run(tmp_path, "temporal_transformer", fold_id=1)

    with pytest.raises(ValueError, match="contiguous 0..0"):
        build_alignment_report(baseline, deep, expected_fold_count=1)


def test_alignment_report_rejects_a_cpu_deep_run(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer")
    payload = json.loads(deep.read_text(encoding="utf-8"))
    payload["training_config"]["device"] = "cpu"
    deep.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="requires CUDA training"):
        build_alignment_report(baseline, deep, expected_fold_count=1)
