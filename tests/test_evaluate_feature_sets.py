"""Tests for the walk-forward feature-set comparison experiment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.evaluate_feature_sets import parse_args, parse_feature_sets, run, union_columns
from tests.test_evaluate_selective_trust import _write_ohlcv
from tests.test_walk_forward_experiment import _write_reference
from tsi.features.sets import resolve_feature_set


def test_parse_feature_sets_puts_baseline_first_without_duplicates() -> None:
    sets = parse_feature_sets("technical_market,technical,technical_market", baseline="technical")

    assert list(sets) == ["technical", "technical_market"]
    assert union_columns(sets) == resolve_feature_set("technical_market")


def test_parse_feature_sets_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="Unknown feature set"):
        parse_feature_sets("technical,nope", baseline="technical")


def test_run_scores_every_set_on_identical_folds(tmp_path: Path) -> None:
    _write_ohlcv(tmp_path / "ohlcv.csv")
    _write_reference(tmp_path / "market")
    args = parse_args(
        [
            "--input",
            str(tmp_path / "ohlcv.csv"),
            "--output-dir",
            "run",
            "--output-root",
            str(tmp_path),
            "--market-reference",
            str(tmp_path / "market"),
            "--train-size",
            "80",
            "--calibration-size",
            "30",
            "--test-size",
            "30",
            "--min-alerts",
            "3",
            "--bootstrap-resamples",
            "200",
        ]
    )

    summary = run(args)

    saved = json.loads((tmp_path / "run" / "summary.json").read_text())
    per_fold = pd.read_csv(tmp_path / "run" / "per_fold.csv")
    coefficients = pd.read_csv(tmp_path / "run" / "coefficients.csv")
    assert list(saved["feature_sets"]) == [
        "technical",
        "technical_range",
        "technical_market",
        "technical_range_market",
    ]
    assert set(saved["paired_vs_baseline"]) == {
        "technical_range",
        "technical_market",
        "technical_range_market",
    }
    assert saved["fold_count"] == summary["fold_count"] >= 1
    rows_per_fold = per_fold.groupby("fold_id")["rows"].nunique()
    assert (rows_per_fold == 1).all()
    assert saved["protocol"]["market_reference"]["path"] == str(tmp_path / "market")
    full = coefficients[coefficients["feature_set"] == "technical_range_market"]
    assert full["feature"].tolist() == resolve_feature_set("technical_range_market")
    for metrics in saved["feature_sets"].values():
        assert metrics["watch_rate"] >= metrics["alert_rate"]
        assert 0.0 <= metrics["auc_mean"] <= 1.0
