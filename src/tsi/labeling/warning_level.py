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


AlertPolicyKind = Literal["f1", "target_precision", "alert_rate"]


@dataclass(frozen=True)
class AlertPolicy:
    """How to choose the alert threshold on the calibration window.

    - ``f1``: maximize calibration F1 (the historical default).
    - ``target_precision``: the lowest threshold whose calibration precision reaches
      ``target`` with at least ``min_alerts`` alerts, which maximizes recall at that
      precision. If no threshold qualifies, fall back to the most precise threshold
      with enough alerts and report ``target_met=False``.
    - ``alert_rate``: the lowest threshold whose calibration alert rate is at most
      ``target``, which caps alert volume.
    """

    kind: AlertPolicyKind = "f1"
    target: float | None = None
    min_alerts: int = 20

    def __post_init__(self) -> None:
        if self.kind not in ("f1", "target_precision", "alert_rate"):
            raise ValueError(f"Unsupported alert policy: {self.kind}")
        if self.kind != "f1" and (self.target is None or not 0.0 < self.target <= 1.0):
            raise ValueError(f"{self.kind} policy requires a target in (0, 1]")
        if self.min_alerts < 1:
            raise ValueError("min_alerts must be at least 1")

    @property
    def label(self) -> str:
        return self.kind if self.target is None else f"{self.kind}:{self.target:g}"


@dataclass(frozen=True)
class PolicyThresholdResult:
    """Threshold chosen by an alert policy on a calibration window."""

    threshold: float
    policy: AlertPolicy
    target_met: bool
    metrics: dict[str, float]


def select_alert_threshold_by_policy(
    labels: np.ndarray,
    probabilities: np.ndarray,
    policy: AlertPolicy,
    *,
    min_threshold: float = 1e-6,
    max_threshold: float = 0.99,
) -> PolicyThresholdResult:
    """Select an alert threshold on calibration outcomes according to ``policy``."""

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if labels.shape[0] != probabilities.shape[0]:
        raise ValueError("labels and probabilities must have the same length")
    if labels.shape[0] == 0:
        raise ValueError("labels and probabilities must not be empty")

    if policy.kind == "f1":
        selection = select_alert_threshold(
            labels,
            probabilities,
            objective="f1",
            min_threshold=min_threshold,
            max_threshold=max_threshold,
        )
        return PolicyThresholdResult(
            threshold=selection.threshold,
            policy=policy,
            target_met=True,
            metrics=selection.metrics,
        )

    assert policy.target is not None
    thresholds, alert_counts, true_positive_counts = _threshold_sweep(
        labels, probabilities, min_threshold=min_threshold, max_threshold=max_threshold
    )
    total = labels.shape[0]
    alert_rates = alert_counts / total
    with np.errstate(divide="ignore", invalid="ignore"):
        precisions = np.where(alert_counts > 0, true_positive_counts / alert_counts, 0.0)

    def result(index: int, target_met: bool) -> PolicyThresholdResult:
        threshold = float(thresholds[index])
        metrics = classification_metrics(labels, probabilities, threshold=threshold)
        return PolicyThresholdResult(threshold, policy, target_met, metrics)

    # ``thresholds`` is descending, so alert counts grow with the index and the last
    # qualifying index is the lowest threshold (highest recall) that satisfies the policy.
    if policy.kind == "alert_rate":
        qualifying = np.flatnonzero(alert_rates <= policy.target)
        if qualifying.size:
            return result(int(qualifying[-1]), True)
        return result(0, False)

    supported = alert_counts >= policy.min_alerts
    if not supported.any():
        return result(len(thresholds) - 1, False)
    qualifying = np.flatnonzero(supported & (precisions >= policy.target))
    if qualifying.size:
        return result(int(qualifying[-1]), True)
    # Most precise supported threshold; argmax keeps the first (highest) threshold on ties.
    supported_precisions = np.where(supported, precisions, -1.0)
    return result(int(np.argmax(supported_precisions)), False)


def _threshold_sweep(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    min_threshold: float,
    max_threshold: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return descending candidate thresholds with alert and true-positive counts.

    Candidates are the observed probabilities clipped to the allowed range; a row
    alerts when its probability is at or above the threshold.
    """

    order = np.argsort(-probabilities, kind="stable")
    sorted_probabilities = probabilities[order]
    cumulative_true_positives = np.cumsum(labels[order])
    thresholds = np.unique(np.clip(probabilities, min_threshold, max_threshold))[::-1]
    # Number of rows with probability >= threshold, via the ascending view.
    ascending = sorted_probabilities[::-1]
    alert_counts = len(probabilities) - np.searchsorted(ascending, thresholds, side="left")
    true_positive_counts = np.where(
        alert_counts > 0, cumulative_true_positives[np.maximum(alert_counts - 1, 0)], 0
    )
    return thresholds, alert_counts, true_positive_counts
