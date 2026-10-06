"""Tests for predictive uncertainty scores."""

from __future__ import annotations

import numpy as np
import pytest

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


def test_ensemble_disagreement_is_zero_when_members_agree() -> None:
    from tsi.trust.uncertainty import ensemble_disagreement

    members = np.array([[0.1, 0.6], [0.1, 0.6], [0.1, 0.6]])

    np.testing.assert_allclose(ensemble_disagreement(members), np.array([0.0, 0.0]), atol=1e-12)


def test_ensemble_disagreement_does_not_depend_on_mean_probability() -> None:
    from tsi.trust.uncertainty import ensemble_disagreement

    members = np.array([[0.05, 0.45], [0.15, 0.55]])

    scores = ensemble_disagreement(members)

    np.testing.assert_allclose(scores[0], scores[1])
    assert scores[0] > 0.0


def test_ensemble_disagreement_rejects_single_member() -> None:
    from tsi.trust.uncertainty import ensemble_disagreement

    with pytest.raises(ValueError, match="at least two ensemble members"):
        ensemble_disagreement(np.array([[0.1, 0.2]]))


def test_empirical_percentile_ranks_against_reference() -> None:
    from tsi.trust.uncertainty import empirical_percentile

    reference = np.array([1.0, 2.0, 3.0, 4.0])

    scores = empirical_percentile(np.array([0.0, 2.0, 2.5, 10.0]), reference)

    np.testing.assert_allclose(scores, np.array([0.0, 0.5, 0.5, 1.0]))


def test_feature_novelty_flags_rows_far_from_training_distribution() -> None:
    from tsi.trust.uncertainty import FeatureNoveltyScorer

    rng = np.random.default_rng(0)
    train = rng.normal(size=(500, 3))
    scorer = FeatureNoveltyScorer().fit(train)

    distances = scorer.distance(np.array([[0.0, 0.0, 0.0], [8.0, -8.0, 8.0]]))

    assert distances[0] < 1.0
    assert distances[1] > 5.0


def test_feature_novelty_ignores_missing_values_with_training_medians() -> None:
    from tsi.trust.uncertainty import FeatureNoveltyScorer

    train = np.array([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0]])
    scorer = FeatureNoveltyScorer().fit(train)

    distances = scorer.distance(np.array([[np.nan, np.nan]]))

    assert np.isfinite(distances).all()


def test_class_conditional_conformal_sets_cover_each_class() -> None:
    from tsi.trust.uncertainty import ClassConditionalConformal

    rng = np.random.default_rng(1)
    labels = (rng.random(4000) < 0.2).astype(int)
    probabilities = np.clip(0.2 + 0.3 * (labels - 0.2) + rng.normal(0, 0.15, 4000), 0, 1)
    conformal = ClassConditionalConformal(alpha=0.1).fit(probabilities[:2000], labels[:2000])

    sets = conformal.prediction_sets(probabilities[2000:])
    test_labels = labels[2000:]

    for label in (0, 1):
        covered = sets[test_labels == label, label].mean()
        assert covered >= 0.87


def test_conformal_ambiguity_marks_two_label_sets() -> None:
    from tsi.trust.uncertainty import ClassConditionalConformal

    conformal = ClassConditionalConformal(alpha=0.1)
    conformal.thresholds_ = {0: 0.5, 1: 0.5}

    ambiguous = conformal.ambiguity(np.array([0.05, 0.5, 0.95]))

    np.testing.assert_array_equal(ambiguous, np.array([False, True, False]))


def test_conformal_requires_both_classes() -> None:
    from tsi.trust.uncertainty import ClassConditionalConformal

    with pytest.raises(ValueError, match="both classes"):
        ClassConditionalConformal(alpha=0.1).fit(np.array([0.1, 0.2]), np.array([0, 0]))
