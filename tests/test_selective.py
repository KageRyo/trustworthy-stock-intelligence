"""Tests for selective prediction (risk-coverage) evaluation."""

from __future__ import annotations

import numpy as np
import pytest

from tsi.evaluation.selective import risk_coverage_curve, selective_summary


def _noisy_rows() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(5)
    labels = (rng.random(2000) < 0.2).astype(int)
    reliable = rng.random(2000) < 0.5
    probabilities = np.where(
        reliable,
        np.where(labels == 1, 0.7, 0.1),
        rng.random(2000),
    )
    return labels, probabilities, reliable.astype(float)


def test_risk_coverage_curve_keeps_highest_confidence_rows_first() -> None:
    labels, probabilities, confidence = _noisy_rows()

    curve = risk_coverage_curve(labels, probabilities, confidence, coverages=(0.5, 1.0))

    assert list(curve["coverage"]) == [0.5, 1.0]
    assert list(curve["rows"]) == [1000, 2000]
    half, full = curve.iloc[0], curve.iloc[1]
    assert half["brier_score"] < full["brier_score"]
    assert half["brier_skill_score"] > full["brier_skill_score"]
    assert half["auc"] > full["auc"]


def test_selective_summary_rewards_informative_confidence() -> None:
    labels, probabilities, confidence = _noisy_rows()
    rng = np.random.default_rng(9)

    informative = selective_summary(labels, probabilities, confidence)
    random_order = selective_summary(labels, probabilities, rng.random(len(labels)))

    assert informative["aurc_brier"] < random_order["aurc_brier"]
    assert informative["mean_brier_skill_score"] > random_order["mean_brier_skill_score"]
    assert informative["full_coverage_brier"] == pytest.approx(random_order["full_coverage_brier"])


def test_risk_coverage_curve_rejects_invalid_coverage() -> None:
    labels, probabilities, confidence = _noisy_rows()

    with pytest.raises(ValueError, match="coverages"):
        risk_coverage_curve(labels, probabilities, confidence, coverages=(0.0,))


def test_risk_coverage_curve_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        risk_coverage_curve(np.array([0, 1]), np.array([0.1]), np.array([0.5, 0.5]))
