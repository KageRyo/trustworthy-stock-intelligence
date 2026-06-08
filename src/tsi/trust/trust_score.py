"""Trust score computation for calibrated risk warnings."""

from __future__ import annotations

import numpy as np


def compute_trust_score(
    calibrated_probabilities: np.ndarray,
    uncertainty_scores: np.ndarray,
    *,
    uncertainty_penalty: float = 0.5,
) -> np.ndarray:
    """Compute trust score from calibrated probability and uncertainty.

    The first version follows:

    ```text
    trust_score = calibrated_probability - lambda * uncertainty_score
    ```
    """

    probabilities = np.asarray(calibrated_probabilities, dtype=float)
    uncertainty = np.asarray(uncertainty_scores, dtype=float)
    if probabilities.shape != uncertainty.shape:
        raise ValueError("calibrated_probabilities and uncertainty_scores must have the same shape")
    if uncertainty_penalty < 0.0:
        raise ValueError("uncertainty_penalty must be non-negative")
    scores = probabilities - (uncertainty_penalty * uncertainty)
    return np.clip(scores, 0.0, 1.0)
