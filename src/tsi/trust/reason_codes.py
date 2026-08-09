"""Reason codes for trust-aware warning outputs."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from tsi.trust.decision import TrustDecisionConfig, WarningDecision


def reason_codes_for_prediction(
    *,
    calibrated_probability: float,
    uncertainty_score: float,
    trust_score: float,
    warning_level: WarningDecision,
    config: TrustDecisionConfig,
    extra_reason_codes: Sequence[str] = (),
) -> tuple[str, ...]:
    """Generate concise audit reason codes for one warning decision."""

    probability = float(calibrated_probability)
    uncertainty = float(uncertainty_score)
    trust = float(trust_score)
    codes: list[str] = []

    if probability >= config.alert_threshold:
        codes.append("probability_above_alert_threshold")
    elif probability >= config.watch_threshold:
        codes.append("probability_above_watch_threshold")
    else:
        codes.append("calibrated_probability_below_watch_threshold")

    if probability >= config.watch_threshold and "probability_above_watch_threshold" not in codes:
        codes.append("probability_above_watch_threshold")

    if trust >= config.trust_threshold:
        codes.append("trust_above_alert_threshold")
    else:
        codes.append("trust_below_alert_threshold")

    if uncertainty >= config.uncertainty_threshold:
        codes.append("uncertainty_above_threshold")
    else:
        codes.append("uncertainty_below_threshold")

    codes.extend(str(code) for code in extra_reason_codes)
    codes.append(f"warning_level_{warning_level}")
    return tuple(codes)


def build_reason_codes(
    *,
    calibrated_probabilities: np.ndarray,
    uncertainty_scores: np.ndarray,
    trust_scores: np.ndarray,
    warning_levels: Sequence[WarningDecision],
    config: TrustDecisionConfig,
    extra_reason_codes: Sequence[str] = (),
) -> list[list[str]]:
    """Generate reason code lists for vectorized prediction outputs."""

    probabilities = np.asarray(calibrated_probabilities, dtype=float)
    uncertainty = np.asarray(uncertainty_scores, dtype=float)
    trust = np.asarray(trust_scores, dtype=float)
    levels = np.asarray(warning_levels, dtype=object)
    if probabilities.shape != uncertainty.shape or probabilities.shape != trust.shape:
        raise ValueError("calibrated_probabilities, uncertainty_scores, and trust_scores must match")
    if probabilities.shape != levels.shape:
        raise ValueError("warning_levels must match probability arrays")

    return [
        list(
            reason_codes_for_prediction(
                calibrated_probability=probability,
                uncertainty_score=uncertainty_score,
                trust_score=trust_score,
                warning_level=level,
                config=config,
                extra_reason_codes=extra_reason_codes,
            )
        )
        for probability, uncertainty_score, trust_score, level in zip(
            probabilities,
            uncertainty,
            trust,
            levels,
            strict=True,
        )
    ]
