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
