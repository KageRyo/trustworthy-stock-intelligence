"""Predictive uncertainty scores for binary risk probabilities."""

from __future__ import annotations

import numpy as np


def _validate_probabilities(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("probabilities must be finite")
    if np.any((values < 0.0) | (values > 1.0)):
        raise ValueError("probabilities must be in [0, 1]")
    return values


def binary_entropy_uncertainty(probabilities: np.ndarray, *, epsilon: float = 1e-12) -> np.ndarray:
    """Return normalized binary entropy uncertainty in ``[0, 1]``.

    Scores are lowest near 0 or 1 and highest at 0.5.
    """

    values = _validate_probabilities(probabilities)
    clipped = np.clip(values, epsilon, 1.0 - epsilon)
    entropy = -(clipped * np.log2(clipped) + (1.0 - clipped) * np.log2(1.0 - clipped))
    return np.clip(entropy, 0.0, 1.0)


def margin_uncertainty(probabilities: np.ndarray) -> np.ndarray:
    """Return uncertainty based on distance from the binary decision boundary."""

    values = _validate_probabilities(probabilities)
    return 1.0 - np.abs((2.0 * values) - 1.0)


def ensemble_disagreement(member_probabilities: np.ndarray) -> np.ndarray:
    """Return epistemic disagreement across ensemble members in ``[0, 1]``.

    ``member_probabilities`` has shape ``(n_members, n_samples)``. The score is the
    across-member standard deviation scaled by 0.5, the largest possible standard
    deviation for values in ``[0, 1]``. It measures how much refitting the model on
    resampled history changes the prediction, not how close the mean is to 0.5.
    """

    members = _validate_probabilities(member_probabilities)
    if members.ndim != 2:
        raise ValueError("member_probabilities must have shape (n_members, n_samples)")
    if members.shape[0] < 2:
        raise ValueError("member_probabilities must contain at least two ensemble members")
    return np.clip(members.std(axis=0) / 0.5, 0.0, 1.0)


def empirical_percentile(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Return the share of ``reference`` values less than or equal to each value."""

    query = np.asarray(values, dtype=float)
    ordered = np.sort(np.asarray(reference, dtype=float).ravel())
    if ordered.size == 0:
        raise ValueError("reference must not be empty")
    if not np.all(np.isfinite(ordered)) or not np.all(np.isfinite(query)):
        raise ValueError("values and reference must be finite")
    return np.searchsorted(ordered, query, side="right") / ordered.size


class FeatureNoveltyScorer:
    """Score how far feature rows sit from the training feature distribution.

    Distances are shrinkage-regularized Mahalanobis distances divided by the square
    root of the feature count, so a typical in-distribution row scores near 1
    regardless of dimensionality. Missing values are filled with training medians.
    """

    def __init__(self) -> None:
        self.medians_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.precision_: np.ndarray | None = None

    def fit(self, features: np.ndarray) -> "FeatureNoveltyScorer":
        from sklearn.covariance import LedoitWolf

        values = np.asarray(features, dtype=float)
        if values.ndim != 2 or values.shape[0] < 2:
            raise ValueError("features must be a 2D array with at least two rows")
        medians = np.nanmedian(values, axis=0)
        if not np.all(np.isfinite(medians)):
            raise ValueError("every feature column needs at least one finite training value")
        self.medians_ = medians
        filled = self._fill(values)
        estimator = LedoitWolf().fit(filled)
        self.mean_ = estimator.location_
        self.precision_ = estimator.precision_
        return self

    def distance(self, features: np.ndarray) -> np.ndarray:
        if self.precision_ is None or self.mean_ is None:
            raise ValueError("FeatureNoveltyScorer must be fit before scoring")
        centered = self._fill(np.asarray(features, dtype=float)) - self.mean_
        squared = np.einsum("ij,jk,ik->i", centered, self.precision_, centered)
        return np.sqrt(np.maximum(squared, 0.0) / centered.shape[1])

    def _fill(self, values: np.ndarray) -> np.ndarray:
        assert self.medians_ is not None
        if values.ndim != 2 or values.shape[1] != self.medians_.shape[0]:
            raise ValueError("features must match the fitted feature count")
        return np.where(np.isfinite(values), values, self.medians_)


class ClassConditionalConformal:
    """Class-conditional (Mondrian) split conformal sets for binary risk labels.

    Each class gets its own nonconformity threshold so the rare drawdown class keeps
    ``1 - alpha`` coverage instead of being averaged away by the majority class. A
    prediction set containing both labels means the calibrated model cannot separate
    the outcomes at the requested coverage for this row.
    """

    def __init__(self, alpha: float = 0.1) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = alpha
        self.thresholds_: dict[int, float] | None = None

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> "ClassConditionalConformal":
        values = _validate_probabilities(probabilities)
        targets = np.asarray(labels).astype(int)
        if values.shape != targets.shape:
            raise ValueError("probabilities and labels must have the same shape")
        if set(np.unique(targets)) != {0, 1}:
            raise ValueError("conformal calibration requires both classes")
        thresholds: dict[int, float] = {}
        for label in (0, 1):
            scores = np.sort(_nonconformity(values[targets == label], label))
            rank = int(np.ceil((scores.size + 1) * (1.0 - self.alpha)))
            thresholds[label] = float(scores[rank - 1]) if rank <= scores.size else np.inf
        self.thresholds_ = thresholds
        return self

    def prediction_sets(self, probabilities: np.ndarray) -> np.ndarray:
        """Return a boolean ``(n_samples, 2)`` membership matrix for labels 0 and 1."""

        if self.thresholds_ is None:
            raise ValueError("ClassConditionalConformal must be fit before predicting")
        values = _validate_probabilities(probabilities)
        return np.column_stack(
            [_nonconformity(values, label) <= self.thresholds_[label] for label in (0, 1)]
        )

    def ambiguity(self, probabilities: np.ndarray) -> np.ndarray:
        """Return True where the conformal set contains both labels."""

        return self.prediction_sets(probabilities).all(axis=1)


def _nonconformity(probabilities: np.ndarray, label: int) -> np.ndarray:
    return 1.0 - probabilities if label == 1 else probabilities
