"""Tests for probability calibration utilities."""

from __future__ import annotations

import numpy as np

from tsi.trust.calibration import IdentityCalibrator, fit_probability_calibrator


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
