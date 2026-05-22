"""Alert-oriented metrics for binary risk warnings."""

from __future__ import annotations

import math

import numpy as np
from sklearn.metrics import roc_auc_score


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bins: int = 10,
) -> float:
    """Compute equal-width expected calibration error."""

    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(y_true)
    error = 0.0

    for start, end in zip(bins[:-1], bins[1:], strict=True):
        if math.isclose(end, 1.0):
            mask = (y_prob >= start) & (y_prob <= end)
        else:
            mask = (y_prob >= start) & (y_prob < end)
        if not np.any(mask):
            continue
        bin_accuracy = y_true[mask].mean()
        bin_confidence = y_prob[mask].mean()
        error += (mask.sum() / total) * abs(bin_accuracy - bin_confidence)

    return float(error)


def classification_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    threshold: float = 0.5,
    ece_bins: int = 10,
) -> dict[str, float]:
    """Compute alert-oriented binary classification metrics."""

    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have the same length")
    if len(y_true) == 0:
        raise ValueError("y_true and y_prob must not be empty")

    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    false_alarm_rate = fp / (fp + tn) if (fp + tn) else 0.0
    miss_rate = fn / (fn + tp) if (fn + tp) else 0.0
    brier_score = float(np.mean((y_prob - y_true) ** 2))
    ece = expected_calibration_error(y_true, y_prob, n_bins=ece_bins)

    auc = float("nan")
    if len(np.unique(y_true)) > 1:
        auc = float(roc_auc_score(y_true, y_prob))

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": auc,
        "false_alarm_rate": float(false_alarm_rate),
        "miss_rate": float(miss_rate),
        "brier_score": brier_score,
        "ece": ece,
        "positive_rate": float(y_true.mean()),
        "prediction_rate": float(y_pred.mean()),
        "support": float(len(y_true)),
    }
