"""Probability calibration utilities for binary risk warnings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

CalibrationMethod = Literal["none", "platt", "isotonic"]


class ProbabilityCalibrator(Protocol):
    """Simple calibrator interface."""

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        """Return calibrated probabilities."""


@dataclass
class IdentityCalibrator:
    """Pass-through calibrator used when calibration is disabled."""

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)


@dataclass
class PlattCalibrator:
    """Platt scaling over base model probabilities."""

    random_state: int = 42

    def __post_init__(self) -> None:
        self.model = LogisticRegression(random_state=self.random_state, max_iter=1000)

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> "PlattCalibrator":
        features = np.asarray(probabilities, dtype=float).reshape(-1, 1)
        targets = np.asarray(labels, dtype=int)
        self.model.fit(features, targets)
        return self

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        features = np.asarray(probabilities, dtype=float).reshape(-1, 1)
        return self.model.predict_proba(features)[:, 1]


@dataclass
class IsotonicCalibrator:
    """Isotonic regression over base model probabilities."""

    out_of_bounds: str = "clip"

    def __post_init__(self) -> None:
        self.model = IsotonicRegression(out_of_bounds=self.out_of_bounds)

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> "IsotonicCalibrator":
        features = np.asarray(probabilities, dtype=float)
        targets = np.asarray(labels, dtype=int)
        self.model.fit(features, targets)
        return self

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        features = np.asarray(probabilities, dtype=float)
        return np.asarray(self.model.predict(features), dtype=float)


def fit_probability_calibrator(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    method: CalibrationMethod,
    random_state: int = 42,
) -> ProbabilityCalibrator:
    """Fit a probability calibrator on a dedicated calibration window.

    When the calibration window contains a single class, the function falls back
    to an identity calibrator because Platt and isotonic fitting would be ill-posed.
    """

    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels, dtype=int)

    if method == "none":
        return IdentityCalibrator()

    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have the same length")
    if len(probabilities) == 0:
        raise ValueError("calibration data must not be empty")
    if np.unique(labels).size < 2:
        return IdentityCalibrator()

    if method == "platt":
        return PlattCalibrator(random_state=random_state).fit(probabilities, labels)
    if method == "isotonic":
        return IsotonicCalibrator().fit(probabilities, labels)
    raise ValueError(f"Unsupported calibration method: {method}")
