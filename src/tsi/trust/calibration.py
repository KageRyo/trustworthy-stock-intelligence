"""Probability calibration utilities for binary risk warnings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, get_args

import numpy as np
from pydantic import BaseModel, ConfigDict
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

CalibrationMethod = Literal["none", "platt", "platt_monotone", "isotonic"]
CALIBRATION_METHODS: tuple[str, ...] = get_args(CalibrationMethod)
_LOGIT_CLIP = 1e-6


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
class MonotonePlattCalibrator:
    """Platt scaling that never reverses the base model's ranking.

    A non-positive Platt slope means the calibration window gives no evidence that higher base
    scores carry higher risk; applying it would rank the riskiest rows as the safest. In that case
    the calibrator keeps the base ranking and shifts the base log-odds so the mean calibrated
    probability matches the window's event rate. ``reversed`` records that fallback.
    """

    random_state: int = 42
    slope: float = field(init=False, default=float("nan"))
    reversed: bool = field(init=False, default=False)
    offset: float = field(init=False, default=0.0)

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> "MonotonePlattCalibrator":
        scores = np.asarray(probabilities, dtype=float)
        targets = np.asarray(labels, dtype=int)
        self._platt = PlattCalibrator(random_state=self.random_state).fit(scores, targets)
        self.slope = float(self._platt.model.coef_[0][0])
        self.reversed = self.slope <= 0.0
        if self.reversed:
            self.offset = _base_rate_offset(_clipped_logit(scores), float(targets.mean()))
        return self

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        if not self.reversed:
            return self._platt.predict(probabilities)
        return _sigmoid(_clipped_logit(np.asarray(probabilities, dtype=float)) + self.offset)


CALIBRATION_SLOPE_NONPOSITIVE = "calibration_slope_nonpositive"


class CalibratorParams(BaseModel):
    """Fitted values of a storable calibrator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["none", "platt", "platt_monotone"]
    slope: float | None = None
    intercept: float | None = None
    reversed: bool = False
    offset: float = 0.0


@dataclass(frozen=True)
class StoredCalibrator:
    """Apply ``CalibratorParams`` exactly as the fitted calibrator does."""

    params: CalibratorParams

    @property
    def reversed(self) -> bool:
        return self.params.reversed

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        values = np.asarray(probabilities, dtype=float)
        if self.params.method == "none":
            return values
        if self.params.reversed:
            return _sigmoid(_clipped_logit(values) + self.params.offset)
        assert self.params.slope is not None and self.params.intercept is not None
        return 1.0 / (1.0 + np.exp(-(self.params.slope * values + self.params.intercept)))


def calibrator_params(calibrator: ProbabilityCalibrator) -> CalibratorParams:
    """Export a fitted identity, Platt, or monotone Platt calibrator."""

    if isinstance(calibrator, StoredCalibrator):
        return calibrator.params
    if isinstance(calibrator, IdentityCalibrator):
        return CalibratorParams(method="none")
    if isinstance(calibrator, MonotonePlattCalibrator):
        platt = calibrator._platt.model
        return CalibratorParams(
            method="platt_monotone",
            slope=float(platt.coef_[0][0]),
            intercept=float(platt.intercept_[0]),
            reversed=calibrator.reversed,
            offset=calibrator.offset,
        )
    if isinstance(calibrator, PlattCalibrator):
        return CalibratorParams(
            method="platt",
            slope=float(calibrator.model.coef_[0][0]),
            intercept=float(calibrator.model.intercept_[0]),
        )
    raise ValueError(
        f"{type(calibrator).__name__} cannot be stored; isotonic calibration is not supported"
    )


def calibration_reason_codes(calibrator: ProbabilityCalibrator) -> list[str]:
    """Reason codes for every row scored with ``calibrator``."""

    reversed_fit = isinstance(calibrator, (MonotonePlattCalibrator, StoredCalibrator))
    if reversed_fit and calibrator.reversed:
        return [CALIBRATION_SLOPE_NONPOSITIVE]
    return []


def _clipped_logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, _LOGIT_CLIP, 1.0 - _LOGIT_CLIP)
    return np.log(clipped) - np.log1p(-clipped)


def _sigmoid(log_odds: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * log_odds))


def _base_rate_offset(log_odds: np.ndarray, event_rate: float) -> float:
    """Shift whose sigmoid mean equals ``event_rate``; the mean rises monotonically with it."""

    low, high = -50.0, 50.0
    for _ in range(200):
        middle = 0.5 * (low + high)
        if _sigmoid(log_odds + middle).mean() < event_rate:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


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
    if method == "platt_monotone":
        return MonotonePlattCalibrator(random_state=random_state).fit(probabilities, labels)
    if method == "isotonic":
        return IsotonicCalibrator().fit(probabilities, labels)
    raise ValueError(f"Unsupported calibration method: {method}")
