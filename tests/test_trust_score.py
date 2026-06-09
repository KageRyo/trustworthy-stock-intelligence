"""Tests for trust score computation."""

from __future__ import annotations

import numpy as np

from tsi.trust.trust_score import compute_trust_score


def test_trust_score_penalizes_uncertainty() -> None:
    probabilities = np.array([0.8, 0.8])
    uncertainty = np.array([0.1, 0.5])

    scores = compute_trust_score(probabilities, uncertainty, uncertainty_penalty=0.5)

    np.testing.assert_allclose(scores, np.array([0.75, 0.55]))


def test_multiplicative_trust_score_scales_probability_by_uncertainty() -> None:
    probabilities = np.array([0.8, 0.8])
    uncertainty = np.array([0.1, 0.5])

    scores = compute_trust_score(
        probabilities,
        uncertainty,
        uncertainty_penalty=0.5,
        method="multiplicative",
    )

    np.testing.assert_allclose(scores, np.array([0.76, 0.6]))


def test_trust_score_is_clipped_to_unit_interval() -> None:
    scores = compute_trust_score(
        np.array([0.1, 1.2]),
        np.array([0.5, 0.0]),
        uncertainty_penalty=1.0,
    )

    np.testing.assert_allclose(scores, np.array([0.0, 1.0]))


def test_trust_score_rejects_shape_mismatch() -> None:
    try:
        compute_trust_score(np.array([0.5]), np.array([0.1, 0.2]))
    except ValueError as error:
        assert "same shape" in str(error)
    else:
        raise AssertionError("Expected ValueError for shape mismatch")


def test_trust_score_rejects_unknown_method() -> None:
    try:
        compute_trust_score(np.array([0.5]), np.array([0.1]), method="unknown")
    except ValueError as error:
        assert "Unsupported trust score method" in str(error)
    else:
        raise AssertionError("Expected ValueError for unknown trust score method")
