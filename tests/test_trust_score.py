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


def test_reliability_trust_does_not_depend_on_risk_probability() -> None:
    from tsi.trust.trust_score import compute_reliability_trust

    scores = compute_reliability_trust(
        epistemic_uncertainty=np.array([0.2, 0.2]),
        data_quality=np.array([1.0, 1.0]),
    )

    np.testing.assert_allclose(scores, np.array([0.8, 0.8]))


def test_reliability_trust_scales_by_data_quality() -> None:
    from tsi.trust.trust_score import compute_reliability_trust

    scores = compute_reliability_trust(
        epistemic_uncertainty=np.array([0.0, 0.5, 1.0]),
        data_quality=np.array([0.5, 1.0, 1.0]),
    )

    np.testing.assert_allclose(scores, np.array([0.5, 0.5, 0.0]))


def test_reliability_trust_rejects_out_of_range_inputs() -> None:
    from tsi.trust.trust_score import compute_reliability_trust

    try:
        compute_reliability_trust(
            epistemic_uncertainty=np.array([1.5]),
            data_quality=np.array([1.0]),
        )
    except ValueError as error:
        assert "epistemic_uncertainty must be in [0, 1]" in str(error)
    else:
        raise AssertionError("Expected ValueError for out-of-range uncertainty")


def test_combine_epistemic_uncertainty_averages_percentile_signals() -> None:
    from tsi.trust.trust_score import combine_epistemic_uncertainty

    combined = combine_epistemic_uncertainty(
        disagreement_percentile=np.array([0.2, 1.0]),
        novelty_percentile=np.array([0.4, 0.0]),
    )

    np.testing.assert_allclose(combined, np.array([0.3, 0.5]))


def test_data_quality_penalizes_short_history_and_stale_rows() -> None:
    from tsi.trust.trust_score import data_quality_scores

    scores = data_quality_scores(
        history_rows=np.array([252, 126, 500, 252]),
        required_history_rows=252,
        stale=np.array([False, False, False, True]),
        stale_penalty=0.5,
    )

    np.testing.assert_allclose(scores, np.array([1.0, 0.5, 1.0, 0.5]))


def test_reliability_trust_can_ignore_epistemic_uncertainty() -> None:
    from tsi.trust.trust_score import compute_reliability_trust

    scores = compute_reliability_trust(
        epistemic_uncertainty=np.array([0.0, 0.9]),
        data_quality=np.array([0.8, 0.8]),
        epistemic_weight=0.0,
    )

    np.testing.assert_allclose(scores, np.array([0.8, 0.8]))
