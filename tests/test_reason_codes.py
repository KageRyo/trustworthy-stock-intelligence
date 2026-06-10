"""Tests for warning reason code generation."""

from __future__ import annotations

import numpy as np

from tsi.trust.decision import TrustDecisionConfig
from tsi.trust.reason_codes import build_reason_codes, reason_codes_for_prediction


def test_reason_codes_describe_alert_decision() -> None:
    codes = reason_codes_for_prediction(
        calibrated_probability=0.8,
        uncertainty_score=0.2,
        trust_score=0.7,
        warning_level="alert",
        config=TrustDecisionConfig(
            alert_threshold=0.7,
            watch_threshold=0.4,
            trust_threshold=0.5,
            uncertainty_threshold=0.8,
        ),
    )

    assert codes == (
        "probability_above_alert_threshold",
        "probability_above_watch_threshold",
        "trust_above_alert_threshold",
        "uncertainty_below_threshold",
        "warning_level_alert",
    )


def test_reason_codes_describe_watch_when_trust_blocks_alert() -> None:
    codes = reason_codes_for_prediction(
        calibrated_probability=0.75,
        uncertainty_score=0.3,
        trust_score=0.2,
        warning_level="watch",
        config=TrustDecisionConfig(
            alert_threshold=0.7,
            watch_threshold=0.4,
            trust_threshold=0.5,
            uncertainty_threshold=0.8,
        ),
    )

    assert "probability_above_alert_threshold" in codes
    assert "trust_below_alert_threshold" in codes
    assert "warning_level_watch" in codes


def test_reason_codes_describe_abstain_and_no_alert() -> None:
    config = TrustDecisionConfig(
        alert_threshold=0.7,
        watch_threshold=0.4,
        trust_threshold=0.5,
        uncertainty_threshold=0.8,
    )

    abstain_codes = reason_codes_for_prediction(
        calibrated_probability=0.2,
        uncertainty_score=0.9,
        trust_score=0.1,
        warning_level="abstain",
        config=config,
    )
    no_alert_codes = reason_codes_for_prediction(
        calibrated_probability=0.2,
        uncertainty_score=0.2,
        trust_score=0.1,
        warning_level="no_alert",
        config=config,
    )

    assert "uncertainty_above_threshold" in abstain_codes
    assert "calibrated_probability_below_watch_threshold" in no_alert_codes


def test_build_reason_codes_vectorizes_predictions() -> None:
    codes = build_reason_codes(
        calibrated_probabilities=np.array([0.8, 0.2]),
        uncertainty_scores=np.array([0.2, 0.9]),
        trust_scores=np.array([0.7, 0.1]),
        warning_levels=np.array(["alert", "abstain"], dtype=object),
        config=TrustDecisionConfig(
            alert_threshold=0.7,
            watch_threshold=0.4,
            trust_threshold=0.5,
            uncertainty_threshold=0.8,
        ),
    )

    assert len(codes) == 2
    assert codes[0][0] == "probability_above_alert_threshold"
    assert codes[1][-1] == "warning_level_abstain"
