"""Trust-aware warning decision rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

WarningDecision = Literal["alert", "watch", "abstain", "no_alert"]


@dataclass(frozen=True)
class TrustDecisionConfig:
    """Thresholds for trust-aware warning decisions."""

    alert_threshold: float
    watch_threshold: float
    trust_threshold: float
    uncertainty_threshold: float

    def __post_init__(self) -> None:
        thresholds = {
            "alert_threshold": self.alert_threshold,
            "watch_threshold": self.watch_threshold,
            "trust_threshold": self.trust_threshold,
            "uncertainty_threshold": self.uncertainty_threshold,
        }
        for name, value in thresholds.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.watch_threshold > self.alert_threshold:
            raise ValueError("watch_threshold must be less than or equal to alert_threshold")


def compute_watch_threshold(
    alert_threshold: float,
    *,
    watch_threshold_ratio: float,
    min_watch_threshold: float,
) -> float:
    """Compute a watch threshold that never exceeds the alert threshold."""

    if not 0.0 <= alert_threshold <= 1.0:
        raise ValueError("alert_threshold must be in [0, 1]")
    if not 0.0 <= watch_threshold_ratio <= 1.0:
        raise ValueError("watch_threshold_ratio must be in [0, 1]")
    if not 0.0 <= min_watch_threshold <= 1.0:
        raise ValueError("min_watch_threshold must be in [0, 1]")
    return min(alert_threshold, max(min_watch_threshold, alert_threshold * watch_threshold_ratio))


def assign_trust_decisions(
    *,
    calibrated_probabilities: np.ndarray,
    uncertainty_scores: np.ndarray,
    trust_scores: np.ndarray,
    config: TrustDecisionConfig,
) -> np.ndarray:
    """Assign alert, watch, abstain, or no_alert using the roadmap rule order."""

    probabilities = np.asarray(calibrated_probabilities, dtype=float)
    uncertainty = np.asarray(uncertainty_scores, dtype=float)
    trust = np.asarray(trust_scores, dtype=float)
    if probabilities.shape != uncertainty.shape or probabilities.shape != trust.shape:
        raise ValueError("calibrated_probabilities, uncertainty_scores, and trust_scores must match")

    levels = np.full(probabilities.shape, "no_alert", dtype=object)
    abstain_mask = uncertainty >= config.uncertainty_threshold
    watch_mask = probabilities >= config.watch_threshold
    alert_mask = (probabilities >= config.alert_threshold) & (trust >= config.trust_threshold)

    levels[abstain_mask] = "abstain"
    levels[watch_mask] = "watch"
    levels[alert_mask] = "alert"
    return levels
