"""Tests for trust-aware warning decisions."""

from __future__ import annotations

import numpy as np

from tsi.trust.decision import TrustDecisionConfig, assign_trust_decisions


def test_trust_decision_rule_priority_matches_roadmap() -> None:
    config = TrustDecisionConfig(
        alert_threshold=0.7,
        watch_threshold=0.4,
        trust_threshold=0.5,
        uncertainty_threshold=0.8,
    )

    levels = assign_trust_decisions(
        calibrated_probabilities=np.array([0.8, 0.8, 0.3, 0.2]),
        uncertainty_scores=np.array([0.2, 0.9, 0.9, 0.2]),
        trust_scores=np.array([0.7, 0.3, 0.1, 0.1]),
        config=config,
    )

    assert levels.tolist() == ["alert", "watch", "abstain", "no_alert"]


def test_trust_decision_rejects_watch_threshold_above_alert_threshold() -> None:
    try:
        TrustDecisionConfig(
            alert_threshold=0.5,
            watch_threshold=0.6,
            trust_threshold=0.4,
            uncertainty_threshold=0.8,
        )
    except ValueError as error:
        assert "watch_threshold" in str(error)
    else:
        raise AssertionError("Expected ValueError for invalid thresholds")
