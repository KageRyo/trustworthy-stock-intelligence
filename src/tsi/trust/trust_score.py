"""Trust score computation for calibrated risk warnings."""

from __future__ import annotations

from typing import Literal

import numpy as np

TrustScoreMethod = Literal["subtractive", "multiplicative"]


def compute_trust_score(
    calibrated_probabilities: np.ndarray,
    uncertainty_scores: np.ndarray,
    *,
    uncertainty_penalty: float = 0.5,
    method: TrustScoreMethod = "subtractive",
) -> np.ndarray:
    """Compute trust score from calibrated probability and uncertainty.

    ``subtractive`` directly subtracts the uncertainty penalty. ``multiplicative``
    scales calibrated risk probability by an uncertainty discount and is less
    likely to collapse scores to zero when entropy uncertainty is high.
    """

    probabilities = np.asarray(calibrated_probabilities, dtype=float)
    uncertainty = np.asarray(uncertainty_scores, dtype=float)
    if probabilities.shape != uncertainty.shape:
        raise ValueError("calibrated_probabilities and uncertainty_scores must have the same shape")
    if uncertainty_penalty < 0.0:
        raise ValueError("uncertainty_penalty must be non-negative")
    if method == "subtractive":
        scores = probabilities - (uncertainty_penalty * uncertainty)
    elif method == "multiplicative":
        scores = probabilities * (1.0 - (uncertainty_penalty * uncertainty))
    else:
        raise ValueError(f"Unsupported trust score method: {method}")
    return np.clip(scores, 0.0, 1.0)
