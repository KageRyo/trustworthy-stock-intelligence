"""Tests for the walk-forward model-family and training-window comparison."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from scripts.evaluate_model_variants import (
    MODEL_FAMILIES,
    build_model,
    parse_args,
    parse_model_families,
    parse_train_windows,
    run,
    train_rows_for_window,
    variant_name,
)
from scripts.walk_forward_experiment import load_walk_forward_folds
from tests.test_evaluate_selective_trust import _write_ohlcv


def _run_args(tmp_path: Path, *extra: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_ohlcv(tmp_path / "ohlcv.csv")
    return parse_args(
        [
            "--input",
            str(tmp_path / "ohlcv.csv"),
            "--output-dir",
            "run",
            "--output-root",
            str(tmp_path),
            "--train-size",
            "80",
            "--train-windows",
            "40,80,all",
            "--calibration-size",
            "30",
            "--test-size",
            "30",
            "--min-alerts",
            "3",
            "--bootstrap-resamples",
            "200",
            "--device",
            "cpu",
            "--allow-cpu",
            "--mlp-epochs",
            "2",
            *extra,
        ]
    )


def test_parse_train_windows_sorts_and_validates() -> None:
    assert parse_train_windows("all,756, 252,756", train_size=756) == ["252", "756", "all"]
    assert parse_train_windows("252", train_size=252) == ["252"]
    with pytest.raises(ValueError, match="positive"):
        parse_train_windows("0,252", train_size=252)
    with pytest.raises(ValueError, match="--train-size"):
        parse_train_windows("252,504", train_size=756)
    with pytest.raises(ValueError, match="--train-size"):
        parse_train_windows("all", train_size=756)


def test_parse_model_families_keeps_logistic_first_and_rejects_unknown() -> None:
    assert parse_model_families("hist_gradient_boosting,logistic") == [
        "logistic",
        "hist_gradient_boosting",
    ]
    assert parse_model_families("mlp")[0] == "logistic"
    with pytest.raises(ValueError, match="Unknown model family"):
        parse_model_families("logistic,svm")


@pytest.mark.parametrize("family", MODEL_FAMILIES)
def test_build_model_returns_positive_class_probabilities(family: str) -> None:
    rng = np.random.default_rng(3)
    features = rng.normal(size=(400, 4))
    features[0, 2] = np.nan
    labels = (features[:, 0] * features[:, 1] + rng.normal(scale=0.5, size=400) > 0).astype(int)

    model = build_model(family, device=torch.device("cpu"), mlp_epochs=3)
    probabilities = model.fit(features, labels).predict_proba(features)

    assert probabilities.shape == (400,)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))


def test_mlp_is_deterministic_for_a_fixed_seed() -> None:
    rng = np.random.default_rng(5)
    features = rng.normal(size=(300, 3))
    labels = (features[:, 0] > 0).astype(int)

    first, second = (
        build_model("mlp", device=torch.device("cpu"), mlp_epochs=2)
        .fit(features, labels)
        .predict_proba(features)
        for _ in range(2)
    )

    np.testing.assert_array_equal(first, second)


def test_train_rows_for_window_uses_recent_dates_or_all_history(tmp_path: Path) -> None:
    args = _run_args(tmp_path)
    walk_forward = load_walk_forward_folds(args, feature_columns=["return_1d"])
    item = walk_forward.folds[-1]
    assert walk_forward.frame is not None

    recent = train_rows_for_window(item, "40", walk_forward.frame)
    longest = train_rows_for_window(item, "80", walk_forward.frame)
    expanding = train_rows_for_window(item, "all", walk_forward.frame)

    recent_dates = set(pd.to_datetime(recent["date"]).unique())
    assert recent_dates <= set(item.fold.train_dates[-40:])
    assert longest.equals(item.train)
    assert len(recent) < len(longest) < len(expanding)
    first_date = pd.to_datetime(walk_forward.frame["date"]).min()
    assert pd.to_datetime(expanding["date"]).min() == first_date
    assert pd.to_datetime(expanding["date"]).max() == pd.to_datetime(item.train["date"]).max()


def test_run_scores_every_variant_on_identical_folds(tmp_path: Path) -> None:
    args = _run_args(tmp_path, "--feature-set", "technical", "--max-folds", "2")

    summary = run(args)

    saved = json.loads((tmp_path / "run" / "summary.json").read_text())
    per_fold = pd.read_csv(tmp_path / "run" / "per_fold.csv", dtype={"train_window": str})
    baseline = variant_name("logistic", "40")
    assert saved["baseline_variant"] == baseline
    assert list(saved["variants"]) == [
        variant_name(family, window) for family in MODEL_FAMILIES for window in ("40", "80", "all")
    ]
    comparisons = saved["paired_comparisons"]
    assert f"{variant_name('mlp', 'all')} vs {baseline}" in comparisons
    assert f"{variant_name('mlp', 'all')} vs {variant_name('logistic', 'all')}" in comparisons
    assert f"{variant_name('logistic', 'all')} vs {baseline}" in comparisons
    assert saved["fold_count"] == summary["fold_count"] >= 1
    assert saved["protocol"]["train_windows"] == ["40", "80", "all"]
    assert saved["protocol"]["mlp_device"] == "cpu"
    assert (per_fold.groupby("fold_id")["rows"].nunique() == 1).all()
    train_rows = per_fold.groupby("train_window")["train_rows"].mean()
    assert train_rows["40"] < train_rows["80"] <= train_rows["all"]
    for metrics in saved["variants"].values():
        assert metrics["watch_rate"] >= metrics["alert_rate"]
        assert 0.0 <= metrics["auc_mean"] <= 1.0


def test_run_rejects_cpu_mlp_without_allow_cpu(tmp_path: Path) -> None:
    args = _run_args(tmp_path, "--models", "logistic,mlp")
    args.allow_cpu = False

    with pytest.raises(RuntimeError, match="CPU training is disabled"):
        run(args)


def test_run_is_deterministic(tmp_path: Path) -> None:
    extra = ("--models", "logistic,hist_gradient_boosting,mlp", "--max-folds", "1")
    first = run(_run_args(tmp_path / "a", *extra))
    second = run(_run_args(tmp_path / "b", *extra))

    first.pop("input")
    second.pop("input")
    assert first == second
