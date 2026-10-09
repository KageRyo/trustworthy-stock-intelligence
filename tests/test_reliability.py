"""Tests for the reliability assessor that feeds serving trust scores."""

from __future__ import annotations

import numpy as np
import pytest

from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import fit_probability_calibrator
from tsi.trust.reliability import ReliabilityAssessor, ReliabilityConfig, ReliabilityParams


def _fitted_assessor(
    config: ReliabilityConfig | None = None,
) -> tuple[ReliabilityAssessor, np.ndarray]:
    rng = np.random.default_rng(11)
    features = rng.normal(size=(3000, 3))
    labels = (features[:, 0] + rng.normal(0, 1, 3000) > 1.2).astype(int)
    dates = np.repeat(np.arange(150), 20)
    train, calibration = slice(0, 2000), slice(2000, 3000)
    model = LogisticRiskModel().fit(features[train], labels[train])
    raw_calibration = model.predict_proba(features[calibration])
    calibrator = fit_probability_calibrator(raw_calibration, labels[calibration], method="platt")
    calibrated_calibration = calibrator.predict(raw_calibration)
    assessor = ReliabilityAssessor(config or ReliabilityConfig(n_members=6, random_state=0)).fit(
        train_features=features[train],
        train_labels=labels[train],
        train_groups=dates[train],
        calibration_features=features[calibration],
        calibration_labels=labels[calibration],
        calibrated_calibration_probabilities=calibrated_calibration,
        calibrator=calibrator,
    )
    return assessor, calibrated_calibration


def test_assessor_scores_are_bounded_and_aligned() -> None:
    assessor, _ = _fitted_assessor()
    query = np.array([[0.0, 0.0, 0.0], [0.5, -0.5, 0.2]])

    scores = assessor.score(
        query,
        calibrated_probabilities=np.array([0.1, 0.3]),
        data_quality=np.array([1.0, 0.5]),
    )

    for values in (scores.disagreement, scores.novelty_percentile, scores.uncertainty, scores.trust):
        assert values.shape == (2,)
        assert np.all((values >= 0.0) & (values <= 1.0))
    np.testing.assert_allclose(scores.trust, np.array([1.0, 0.5]))


def test_out_of_distribution_rows_get_higher_uncertainty_not_lower_default_trust() -> None:
    assessor, _ = _fitted_assessor()
    query = np.array([[0.0, 0.0, 0.0], [12.0, -12.0, 12.0]])

    scores = assessor.score(
        query,
        calibrated_probabilities=np.array([0.2, 0.2]),
        data_quality=np.array([1.0, 1.0]),
    )

    assert scores.novelty_percentile[1] == pytest.approx(1.0)
    assert scores.uncertainty[1] > scores.uncertainty[0]
    np.testing.assert_allclose(scores.trust, np.array([1.0, 1.0]))
    assert "input_out_of_distribution" in scores.reason_codes[1]
    assert "input_out_of_distribution" not in scores.reason_codes[0]


def test_trust_is_identical_for_same_features_at_different_risk() -> None:
    assessor, _ = _fitted_assessor()
    query = np.array([[0.3, 0.1, -0.2], [0.3, 0.1, -0.2]])

    scores = assessor.score(
        query,
        calibrated_probabilities=np.array([0.05, 0.6]),
        data_quality=np.array([1.0, 1.0]),
    )

    assert scores.trust[0] == pytest.approx(scores.trust[1])


def test_reason_codes_include_conformal_set_and_data_quality() -> None:
    assessor, _ = _fitted_assessor()

    scores = assessor.score(
        np.zeros((1, 3)),
        calibrated_probabilities=np.array([0.2]),
        data_quality=np.array([0.4]),
    )

    codes = scores.reason_codes[0]
    assert scores.conformal_sets is not None and scores.conformal_sets.shape == (1, 2)
    assert any(code.startswith("conformal_set_") for code in codes)
    assert "limited_data_quality" in codes


def test_unavailable_scores_fail_closed() -> None:
    scores = ReliabilityAssessor.unavailable(3)

    np.testing.assert_allclose(scores.trust, np.zeros(3))
    np.testing.assert_allclose(scores.uncertainty, np.ones(3))
    assert all("reliability_unavailable" in codes for codes in scores.reason_codes)


def test_score_requires_fit() -> None:
    with pytest.raises(ValueError, match="fit"):
        ReliabilityAssessor().score(
            np.zeros((1, 3)),
            calibrated_probabilities=np.array([0.1]),
            data_quality=np.array([1.0]),
        )


def test_epistemic_trust_weight_lowers_trust_for_novel_rows() -> None:
    assessor, _ = _fitted_assessor(
        ReliabilityConfig(n_members=6, random_state=0, epistemic_trust_weight=1.0)
    )

    scores = assessor.score(
        np.array([[0.0, 0.0, 0.0], [12.0, -12.0, 12.0]]),
        calibrated_probabilities=np.array([0.2, 0.2]),
        data_quality=np.array([1.0, 1.0]),
    )

    assert scores.trust[1] < scores.trust[0]


def test_assessor_restored_from_params_scores_identically() -> None:
    assessor, calibrated_calibration = _fitted_assessor()
    rng = np.random.default_rng(5)
    query = np.vstack([rng.normal(size=(40, 3)), rng.normal(loc=4.0, size=(5, 3))])
    query[3, 1] = np.nan
    probabilities = np.clip(rng.uniform(size=45), 0.0, 1.0)
    quality = np.linspace(0.5, 1.0, 45)

    params = assessor.params()
    restored = ReliabilityAssessor.from_params(
        ReliabilityParams.model_validate_json(params.model_dump_json())
    )
    expected = assessor.score(query, calibrated_probabilities=probabilities, data_quality=quality)
    actual = restored.score(query, calibrated_probabilities=probabilities, data_quality=quality)

    np.testing.assert_allclose(actual.disagreement, expected.disagreement, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(actual.disagreement_percentile, expected.disagreement_percentile)
    np.testing.assert_array_equal(actual.novelty_percentile, expected.novelty_percentile)
    np.testing.assert_array_equal(actual.uncertainty, expected.uncertainty)
    np.testing.assert_array_equal(actual.trust, expected.trust)
    assert actual.reason_codes == expected.reason_codes
    assert len(params.members) == 6


def test_assessor_params_require_a_fitted_assessor() -> None:
    assessor = ReliabilityAssessor()

    with pytest.raises(ValueError, match="fit"):
        assessor.params()
