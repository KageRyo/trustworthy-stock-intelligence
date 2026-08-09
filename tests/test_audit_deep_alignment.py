"""Tests for the fail-closed deep alignment audit."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_deep_alignment import build_alignment_report


def _write_run(root: Path, name: str, *, mismatch: bool = False) -> Path:
    run_dir = root / name
    run_dir.mkdir()
    summary = {
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
        "folds": [{"model": name}],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    dates = ["2026-01-02", "2026-01-03"] if not mismatch else ["2026-01-02", "2026-01-04"]
    pd.DataFrame(
        {
            "fold_id": [0, 0],
            "ticker": ["0050", "2330"],
            "date": dates,
            "risk_label": [0, 1],
        }
    ).to_csv(run_dir / "predictions.csv", index=False)
    return run_dir / "summary.json"


def test_alignment_report_requires_exact_sample_keys(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer")

    report = build_alignment_report(baseline, deep)

    assert report["aligned"] is True
    assert report["shared_row_count"] == 2
    assert len(report["sample_key_sha256"]) == 64


def test_alignment_report_fails_closed_on_key_mismatch(tmp_path: Path) -> None:
    baseline = _write_run(tmp_path, "logistic")
    deep = _write_run(tmp_path, "temporal_transformer", mismatch=True)

    with pytest.raises(ValueError, match="sample keys are not identical"):
        build_alignment_report(baseline, deep)
