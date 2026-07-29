"""Tests for alert-oriented evaluation metrics."""

from __future__ import annotations

import math

import numpy as np

from tsi.evaluation.metrics import classification_metrics, expected_calibration_error


def test_classification_metrics_match_confusion_matrix() -> None:
    y_true = np.array([1, 0, 1, 0])
    y_prob = np.array([0.9, 0.8, 0.4, 0.1])

    metrics = classification_metrics(y_true, y_prob, threshold=0.5, ece_bins=2)

    assert math.isclose(metrics["precision"], 0.5)
    assert math.isclose(metrics["recall"], 0.5)
    assert math.isclose(metrics["f1"], 0.5)
    assert math.isclose(metrics["false_alarm_rate"], 0.5)
    assert math.isclose(metrics["false_discovery_rate"], 0.5)
    assert math.isclose(metrics["miss_rate"], 0.5)
    assert math.isclose(metrics["brier_score"], 0.255)
    assert math.isclose(metrics["auc"], 0.75)


def test_expected_calibration_error_handles_perfect_calibration() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.0, 0.0, 1.0, 1.0])

    ece = expected_calibration_error(y_true, y_prob, n_bins=2)

    assert math.isclose(ece, 0.0)
