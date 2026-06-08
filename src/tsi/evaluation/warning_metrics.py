"""Trust-aware warning-level evaluation metrics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

DEFAULT_WARNING_LEVELS = ("alert", "watch", "abstain", "no_alert")


def _as_level_array(warning_levels: np.ndarray | Sequence[str]) -> np.ndarray:
    values = np.asarray(warning_levels, dtype=object)
    if values.ndim != 1:
        raise ValueError("warning_levels must be one-dimensional")
    return values.astype(str)


def warning_level_counts(
    warning_levels: np.ndarray | Sequence[str],
    *,
    known_levels: Sequence[str] = DEFAULT_WARNING_LEVELS,
) -> dict[str, float]:
    """Count warning levels and return per-level rates."""

    levels = _as_level_array(warning_levels)
    total = float(len(levels))
    metrics: dict[str, float] = {}
    for level in known_levels:
        count = float(np.sum(levels == level))
        metrics[f"{level}_count"] = count
        metrics[f"{level}_rate"] = count / total if total else 0.0
    return metrics


def _binary_alert_metrics(labels: np.ndarray, alert_mask: np.ndarray) -> dict[str, float]:
    tp = int(np.sum((labels == 1) & alert_mask))
    fp = int(np.sum((labels == 0) & alert_mask))
    tn = int(np.sum((labels == 0) & ~alert_mask))
    fn = int(np.sum((labels == 1) & ~alert_mask))

    return {
        "alert_precision": float(tp / (tp + fp)) if (tp + fp) else 0.0,
        "alert_recall": float(tp / (tp + fn)) if (tp + fn) else 0.0,
        "alert_false_alarm_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "alert_miss_rate": float(fn / (fn + tp)) if (fn + tp) else 0.0,
    }


def _mean_by_level(values: np.ndarray, levels: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {}
    for level in DEFAULT_WARNING_LEVELS:
        mask = levels == level
        if np.any(mask):
            result[level] = float(np.asarray(values, dtype=float)[mask].mean())
    return result


def trust_warning_metrics(
    labels: np.ndarray,
    warning_levels: np.ndarray | Sequence[str],
    *,
    positive_levels: tuple[str, ...] = ("alert",),
    covered_levels: tuple[str, ...] = ("alert", "watch"),
    trust_scores: np.ndarray | None = None,
    uncertainty_scores: np.ndarray | None = None,
) -> dict[str, object]:
    """Evaluate trust-aware warning decisions.

    ``positive_levels`` are treated as positive predictions. ``covered_levels``
    define the subset used for coverage and selective risk.
    """

    y_true = np.asarray(labels, dtype=int)
    levels = _as_level_array(warning_levels)
    if y_true.ndim != 1:
        raise ValueError("labels must be one-dimensional")
    if len(y_true) != len(levels):
        raise ValueError("labels and warning_levels must have the same length")
    if len(y_true) == 0:
        raise ValueError("labels and warning_levels must not be empty")

    positive_mask = np.isin(levels, positive_levels)
    covered_mask = np.isin(levels, covered_levels)
    covered_count = int(np.sum(covered_mask))
    selective_risk = 0.0
    if covered_count:
        selective_predictions = positive_mask[covered_mask].astype(int)
        selective_labels = y_true[covered_mask]
        selective_risk = float(np.mean(selective_predictions != selective_labels))

    metrics: dict[str, object] = {
        **warning_level_counts(levels),
        **_binary_alert_metrics(y_true, positive_mask),
        "coverage": float(covered_count / len(y_true)),
        "selective_risk": selective_risk,
    }

    if trust_scores is not None:
        trust_values = np.asarray(trust_scores, dtype=float)
        if trust_values.shape != y_true.shape:
            raise ValueError("trust_scores must have the same shape as labels")
        metrics["mean_trust_score_by_level"] = _mean_by_level(trust_values, levels)

    if uncertainty_scores is not None:
        uncertainty_values = np.asarray(uncertainty_scores, dtype=float)
        if uncertainty_values.shape != y_true.shape:
            raise ValueError("uncertainty_scores must have the same shape as labels")
        metrics["mean_uncertainty_by_level"] = _mean_by_level(uncertainty_values, levels)

    return metrics
