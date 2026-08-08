"""Tests for paired fold-level statistical summaries."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tsi.evaluation.statistics import bootstrap_mean_interval, paired_fold_metric_intervals


def test_single_unit_bootstrap_is_deterministic() -> None:
    interval = bootstrap_mean_interval([0.25], resamples=20)

    assert interval.sample_count == 1
    assert interval.estimate == 0.25
    assert interval.lower == 0.25
    assert interval.upper == 0.25


def test_paired_bootstrap_reports_comparison_minus_baseline() -> None:
    baseline = [{"fold_id": index, "brier_score": value} for index, value in enumerate([0.2, 0.3, 0.4])]
    comparison = [
        {"fold_id": index, "brier_score": value}
        for index, value in enumerate([0.1, 0.2, 0.3])
    ]

    result = paired_fold_metric_intervals(
        baseline,
        comparison,
        metrics=["brier_score"],
        resamples=100,
    )
    delta = result["metrics"]["brier_score"]["delta"]

    assert math.isclose(delta["estimate"], -0.1)
    assert delta["lower"] <= delta["estimate"] <= delta["upper"]
    assert result["method"].startswith("percentile bootstrap")


def test_paired_bootstrap_excludes_non_finite_pairs_together() -> None:
    baseline = [{"fold_id": 0, "auc": np.nan}, {"fold_id": 1, "auc": 0.6}]
    comparison = [{"fold_id": 0, "auc": 0.5}, {"fold_id": 1, "auc": 0.7}]

    result = paired_fold_metric_intervals(
        baseline,
        comparison,
        metrics=["auc"],
        resamples=20,
    )

    metric = result["metrics"]["auc"]
    assert metric["excluded_non_finite_pairs"] == 1
    assert metric["delta"]["sample_count"] == 1


def test_paired_bootstrap_rejects_misaligned_folds() -> None:
    with pytest.raises(ValueError, match="identical fold_id"):
        paired_fold_metric_intervals(
            [{"fold_id": 0, "auc": 0.5}],
            [{"fold_id": 1, "auc": 0.5}],
            metrics=["auc"],
        )
