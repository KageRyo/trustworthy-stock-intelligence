"""Warning-threshold selection and level mapping utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from tsi.evaluation.metrics import classification_metrics

ThresholdObjective = Literal["f1", "precision", "recall"]


@dataclass(frozen=True)
class ThresholdSelectionResult:
    """Best threshold found on a calibration window."""

    threshold: float
    objective: ThresholdObjective
    objective_value: float
    metrics: dict[str, float]


def threshold_grid(
    probabilities: np.ndarray,
    *,
    min_threshold: float = 1e-6,
    max_threshold: float = 0.99,
    num_quantiles: int = 199,
) -> np.ndarray:
    """Build a compact threshold grid informed by observed probabilities."""

    values = np.asarray(probabilities, dtype=float)
    values = values[np.isfinite(values)]
    values = values[(values >= min_threshold) & (values <= max_threshold)]

    if values.size == 0:
        return np.array([0.5], dtype=float)

    quantile_points = np.linspace(0.0, 1.0, num_quantiles)
    quantile_values = np.quantile(values, quantile_points)
    anchors = np.array([min_threshold, 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, max_threshold], dtype=float)
    return np.unique(np.concatenate([quantile_values, anchors]))


def select_alert_threshold(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    objective: ThresholdObjective = "f1",
    min_threshold: float = 1e-6,
    max_threshold: float = 0.99,
) -> ThresholdSelectionResult:
    """Select an alert threshold using calibration-window outcomes only."""

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)

    if labels.shape[0] != probabilities.shape[0]:
        raise ValueError("labels and probabilities must have the same length")
    if labels.shape[0] == 0:
        raise ValueError("labels and probabilities must not be empty")

    best_result: ThresholdSelectionResult | None = None
    best_rank: tuple[float, float, float] | None = None

    for threshold in threshold_grid(
        probabilities,
        min_threshold=min_threshold,
        max_threshold=max_threshold,
    ):
        metrics = classification_metrics(labels, probabilities, threshold=float(threshold))
        objective_value = float(metrics[objective])

        # Prefer higher objective, then higher precision, then higher threshold
        # so tied solutions are less trigger-happy.
        rank = (objective_value, float(metrics["precision"]), float(threshold))
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_result = ThresholdSelectionResult(
                threshold=float(threshold),
                objective=objective,
                objective_value=objective_value,
                metrics=metrics,
            )

    if best_result is None:
        raise RuntimeError("Threshold selection failed to produce any candidate")
    return best_result


def assign_warning_levels(
    probabilities: np.ndarray,
    *,
    alert_threshold: float,
    watch_threshold: float | None = None,
) -> np.ndarray:
    """Map probabilities into coarse warning states."""

    values = np.asarray(probabilities, dtype=float)
    if watch_threshold is None:
        watch_threshold = alert_threshold
    if watch_threshold > alert_threshold:
        raise ValueError("watch_threshold must be less than or equal to alert_threshold")

    levels = np.full(values.shape, "no_alert", dtype=object)
    levels[values >= watch_threshold] = "watch"
    levels[values >= alert_threshold] = "alert"
    return levels
