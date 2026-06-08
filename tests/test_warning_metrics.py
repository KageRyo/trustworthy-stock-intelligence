"""Tests for trust-aware warning metrics."""

from __future__ import annotations

import math

import numpy as np

from tsi.evaluation.warning_metrics import trust_warning_metrics, warning_level_counts


def test_warning_level_counts_includes_default_levels() -> None:
    levels = np.array(["alert", "watch", "alert", "abstain"])

    counts = warning_level_counts(levels)

    assert counts["alert_count"] == 2.0
    assert counts["watch_count"] == 1.0
    assert counts["abstain_count"] == 1.0
    assert counts["no_alert_count"] == 0.0
    assert counts["alert_rate"] == 0.5
    assert counts["no_alert_rate"] == 0.0


def test_trust_warning_metrics_match_alert_confusion_matrix() -> None:
    labels = np.array([1, 0, 1, 0, 1])
    levels = np.array(["alert", "alert", "watch", "no_alert", "abstain"])

    metrics = trust_warning_metrics(labels, levels)

    assert metrics["alert_count"] == 2.0
    assert metrics["watch_count"] == 1.0
    assert metrics["abstain_count"] == 1.0
    assert metrics["no_alert_count"] == 1.0
    assert math.isclose(metrics["alert_precision"], 0.5)
    assert math.isclose(metrics["alert_recall"], 1 / 3)
    assert math.isclose(metrics["alert_false_alarm_rate"], 0.5)
    assert math.isclose(metrics["alert_miss_rate"], 2 / 3)
    assert math.isclose(metrics["coverage"], 3 / 5)
    assert math.isclose(metrics["abstain_rate"], 1 / 5)
    assert math.isclose(metrics["selective_risk"], 2 / 3)
    assert math.isclose(metrics["alert_only_selective_risk"], 2 / 3)
    assert math.isclose(metrics["alert_or_watch_selective_risk"], 1 / 3)


def test_trust_warning_metrics_summarizes_trust_and_uncertainty_by_level() -> None:
    labels = np.array([1, 0, 0])
    levels = np.array(["alert", "watch", "watch"])
    trust_scores = np.array([0.9, 0.2, 0.4])
    uncertainty_scores = np.array([0.1, 0.8, 0.6])

    metrics = trust_warning_metrics(
        labels,
        levels,
        trust_scores=trust_scores,
        uncertainty_scores=uncertainty_scores,
    )

    assert metrics["mean_trust_score_by_level"]["alert"] == 0.9
    assert metrics["mean_trust_score_by_level"]["watch"] == 0.30000000000000004
    assert metrics["mean_uncertainty_by_level"]["alert"] == 0.1
    assert metrics["mean_uncertainty_by_level"]["watch"] == 0.7


def test_trust_warning_metrics_rejects_shape_mismatch() -> None:
    try:
        trust_warning_metrics(np.array([1, 0]), np.array(["alert"]))
    except ValueError as error:
        assert "same length" in str(error)
    else:
        raise AssertionError("Expected ValueError for mismatched inputs")
