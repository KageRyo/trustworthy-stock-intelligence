"""Heuristic calibration-drift gates for research and trust reporting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CalibrationDriftConfig:
    """Thresholds for the conservative research drift gate."""

    event_rate_delta_threshold: float = 0.10
    ece_increase_threshold: float = 0.05
    brier_increase_threshold: float = 0.05
    abstain_signal_count: int = 2
    degraded_trust_multiplier: float = 0.5


@dataclass(frozen=True)
class CalibrationDriftAssessment:
    """Drift signals and the resulting conservative gate decision."""

    event_rate_delta: float
    ece_delta: float
    brier_delta: float
    signals: tuple[str, ...]
    degraded: bool
    low_trust: bool
    abstain: bool
    trust_multiplier: float

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "event_rate_delta": self.event_rate_delta,
            "ece_delta": self.ece_delta,
            "brier_delta": self.brier_delta,
            "signals": list(self.signals),
            "degraded": self.degraded,
            "low_trust": self.low_trust,
            "abstain": self.abstain,
            "trust_multiplier": self.trust_multiplier,
        }


def calibration_drift_reason_codes(
    assessment: CalibrationDriftAssessment | None,
    *,
    evaluated: bool,
) -> tuple[str, ...]:
    """Return stable reason codes for a serving batch's drift state."""

    if not evaluated or assessment is None:
        return ("calibration_drift_not_evaluated",)
    if not assessment.degraded:
        return ("calibration_drift_stable",)

    codes = ["calibration_drift_detected"]
    codes.extend(f"calibration_drift_{signal}" for signal in assessment.signals)
    if assessment.abstain:
        codes.append("calibration_drift_abstain")
    return tuple(codes)


def assess_calibration_drift(
    calibration_metrics: Mapping[str, object],
    recent_metrics: Mapping[str, object],
    *,
    config: CalibrationDriftConfig | None = None,
) -> CalibrationDriftAssessment:
    """Assess reliability degradation without fitting on the recent window.

    The gate compares event rate, ECE, and Brier score from a calibration window
    with a later evaluation window. A large event-rate shift or reliability
    increase lowers trust. Two or more simultaneous signals trigger abstention.
    Thresholds are engineering heuristics and require future validation.
    """

    config = config or CalibrationDriftConfig()
    _validate_config(config)
    calibration_rate = _metric(calibration_metrics, "positive_rate")
    recent_rate = _metric(recent_metrics, "positive_rate")
    calibration_ece = _metric(calibration_metrics, "ece")
    recent_ece = _metric(recent_metrics, "ece")
    calibration_brier = _metric(calibration_metrics, "brier_score")
    recent_brier = _metric(recent_metrics, "brier_score")

    event_rate_delta = recent_rate - calibration_rate
    ece_delta = recent_ece - calibration_ece
    brier_delta = recent_brier - calibration_brier
    signals: list[str] = []
    if abs(event_rate_delta) >= config.event_rate_delta_threshold:
        signals.append("event_rate_shift")
    if ece_delta >= config.ece_increase_threshold:
        signals.append("ece_increase")
    if brier_delta >= config.brier_increase_threshold:
        signals.append("brier_increase")

    degraded = bool(signals)
    abstain = len(signals) >= config.abstain_signal_count
    return CalibrationDriftAssessment(
        event_rate_delta=event_rate_delta,
        ece_delta=ece_delta,
        brier_delta=brier_delta,
        signals=tuple(signals),
        degraded=degraded,
        low_trust=degraded,
        abstain=abstain,
        trust_multiplier=config.degraded_trust_multiplier if degraded else 1.0,
    )


def _metric(metrics: Mapping[str, object], name: str) -> float:
    value = metrics.get(name)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"metrics must contain numeric {name!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"metric {name!r} must be finite")
    return number


def _validate_config(config: CalibrationDriftConfig) -> None:
    if config.event_rate_delta_threshold < 0:
        raise ValueError("event_rate_delta_threshold must be non-negative")
    if config.ece_increase_threshold < 0 or config.brier_increase_threshold < 0:
        raise ValueError("reliability thresholds must be non-negative")
    if config.abstain_signal_count < 1:
        raise ValueError("abstain_signal_count must be at least 1")
    if not 0.0 < config.degraded_trust_multiplier <= 1.0:
        raise ValueError("degraded_trust_multiplier must be in (0, 1]")
