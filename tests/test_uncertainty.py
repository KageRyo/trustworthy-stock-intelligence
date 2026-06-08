"""Tests for predictive uncertainty scores."""

from __future__ import annotations

import numpy as np

from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty


def test_binary_entropy_uncertainty_is_normalized() -> None:
    probabilities = np.array([0.0, 0.5, 1.0])

    scores = binary_entropy_uncertainty(probabilities)

    np.testing.assert_allclose(scores, np.array([0.0, 1.0, 0.0]), atol=1e-6)


def test_margin_uncertainty_is_highest_near_half() -> None:
    probabilities = np.array([0.0, 0.25, 0.5, 0.75, 1.0])

    scores = margin_uncertainty(probabilities)

    np.testing.assert_allclose(scores, np.array([0.0, 0.5, 1.0, 0.5, 0.0]))


def test_uncertainty_rejects_probabilities_outside_unit_interval() -> None:
    try:
        binary_entropy_uncertainty(np.array([-0.1, 0.2]))
    except ValueError as error:
        assert "probabilities must be in [0, 1]" in str(error)
    else:
        raise AssertionError("Expected ValueError for invalid probabilities")
