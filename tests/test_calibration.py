"""Tests for probability calibration utilities."""

from __future__ import annotations

import numpy as np
import pytest

from tsi.trust.calibration import (
    CALIBRATION_METHODS,
    CalibratorParams,
    IdentityCalibrator,
    MonotonePlattCalibrator,
    StoredCalibrator,
    calibration_reason_codes,
    calibrator_params,
    fit_probability_calibrator,
)


def test_platt_calibration_returns_probabilities_in_unit_interval() -> None:
    base_probabilities = np.array([0.1, 0.2, 0.8, 0.9])
    labels = np.array([0, 0, 1, 1])

    calibrator = fit_probability_calibrator(base_probabilities, labels, method="platt")
    calibrated = calibrator.predict(np.array([0.15, 0.85]))

    assert np.all(calibrated >= 0.0)
    assert np.all(calibrated <= 1.0)
    assert calibrated[0] < calibrated[1]


def test_isotonic_calibration_is_monotonic() -> None:
    base_probabilities = np.array([0.1, 0.2, 0.6, 0.9])
    labels = np.array([0, 0, 1, 1])

    calibrator = fit_probability_calibrator(base_probabilities, labels, method="isotonic")
    calibrated = calibrator.predict(np.array([0.15, 0.5, 0.85]))

    assert np.all(np.diff(calibrated) >= 0.0)


def test_single_class_calibration_falls_back_to_identity() -> None:
    calibrator = fit_probability_calibrator(
        np.array([0.1, 0.2, 0.3]),
        np.array([0, 0, 0]),
        method="platt",
    )

    assert isinstance(calibrator, IdentityCalibrator)


def _reversed_window() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7)
    scores = rng.uniform(0.05, 0.95, size=400)
    labels = (rng.uniform(size=400) < 0.4 - 0.3 * scores).astype(int)
    return scores, labels


def test_calibration_methods_list_every_supported_method() -> None:
    assert CALIBRATION_METHODS == ("none", "platt", "platt_monotone", "isotonic")


def test_monotone_platt_matches_platt_when_the_slope_is_positive() -> None:
    scores = np.array([0.1, 0.2, 0.3, 0.6, 0.8, 0.9])
    labels = np.array([0, 0, 1, 0, 1, 1])

    platt = fit_probability_calibrator(scores, labels, method="platt")
    monotone = fit_probability_calibrator(scores, labels, method="platt_monotone")

    assert isinstance(monotone, MonotonePlattCalibrator)
    assert monotone.slope > 0.0
    assert not monotone.reversed
    np.testing.assert_array_equal(monotone.predict(scores), platt.predict(scores))


def test_monotone_platt_keeps_the_model_ranking_when_the_window_reverses_it() -> None:
    scores, labels = _reversed_window()
    grid = np.linspace(0.05, 0.95, 11)

    platt = fit_probability_calibrator(scores, labels, method="platt")
    monotone = fit_probability_calibrator(scores, labels, method="platt_monotone")

    assert np.all(np.diff(platt.predict(grid)) < 0.0)
    assert isinstance(monotone, MonotonePlattCalibrator)
    assert monotone.slope <= 0.0
    assert monotone.reversed
    assert np.all(np.diff(monotone.predict(grid)) > 0.0)
    assert monotone.predict(scores).mean() == pytest.approx(labels.mean(), abs=1e-9)


def test_monotone_platt_handles_extreme_scores() -> None:
    scores, labels = _reversed_window()
    calibrator = fit_probability_calibrator(scores, labels, method="platt_monotone")

    calibrated = calibrator.predict(np.array([0.0, 1e-12, 0.5, 1.0 - 1e-12, 1.0]))

    assert np.all(np.isfinite(calibrated))
    assert np.all((calibrated > 0.0) & (calibrated < 1.0))
    assert np.all(np.diff(calibrated) >= 0.0)


def test_monotone_platt_single_class_falls_back_to_identity() -> None:
    calibrator = fit_probability_calibrator(
        np.array([0.1, 0.2, 0.3]), np.array([1, 1, 1]), method="platt_monotone"
    )

    assert isinstance(calibrator, IdentityCalibrator)


@pytest.mark.parametrize("method", ["none", "platt", "platt_monotone"])
@pytest.mark.parametrize("reversed_window", [False, True])
def test_stored_calibrator_reproduces_the_fitted_calibrator(
    method: str, reversed_window: bool
) -> None:
    if reversed_window:
        scores, labels = _reversed_window()
    else:
        rng = np.random.default_rng(3)
        scores = rng.uniform(0.05, 0.95, size=300)
        labels = (rng.uniform(size=300) < scores * 0.4).astype(int)
    fitted = fit_probability_calibrator(scores, labels, method=method)
    grid = np.linspace(0.0, 1.0, 41)

    params = calibrator_params(fitted)
    stored = StoredCalibrator(CalibratorParams.model_validate_json(params.model_dump_json()))

    np.testing.assert_allclose(stored.predict(grid), fitted.predict(grid), rtol=0, atol=1e-12)
    assert calibration_reason_codes(stored) == calibration_reason_codes(fitted)


def test_isotonic_calibration_cannot_be_stored() -> None:
    calibrator = fit_probability_calibrator(
        np.array([0.1, 0.2, 0.6, 0.9]), np.array([0, 0, 1, 1]), method="isotonic"
    )

    with pytest.raises(ValueError, match="isotonic"):
        calibrator_params(calibrator)
