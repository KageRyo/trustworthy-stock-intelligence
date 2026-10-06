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


def _unit_interval(name: str, values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)) or np.any((array < 0.0) | (array > 1.0)):
        raise ValueError(f"{name} must be in [0, 1]")
    return array


def combine_epistemic_uncertainty(
    *,
    disagreement_percentile: np.ndarray,
    novelty_percentile: np.ndarray,
) -> np.ndarray:
    """Average model-disagreement and input-novelty percentiles into one score.

    Both inputs are percentiles against the calibration window, so 0.5 means
    "as uncertain as a typical calibration row". Neither depends on the risk level.
    """

    disagreement = _unit_interval("disagreement_percentile", disagreement_percentile)
    novelty = _unit_interval("novelty_percentile", novelty_percentile)
    if disagreement.shape != novelty.shape:
        raise ValueError("disagreement_percentile and novelty_percentile must have the same shape")
    return (disagreement + novelty) / 2.0


def data_quality_scores(
    *,
    history_rows: np.ndarray,
    required_history_rows: int,
    stale: np.ndarray,
    stale_penalty: float = 0.5,
) -> np.ndarray:
    """Score per-ticker input quality from history depth and staleness."""

    if required_history_rows < 1:
        raise ValueError("required_history_rows must be at least 1")
    if not 0.0 <= stale_penalty <= 1.0:
        raise ValueError("stale_penalty must be in [0, 1]")
    rows = np.asarray(history_rows, dtype=float)
    stale_mask = np.asarray(stale, dtype=bool)
    if rows.shape != stale_mask.shape:
        raise ValueError("history_rows and stale must have the same shape")
    coverage = np.clip(rows / float(required_history_rows), 0.0, 1.0)
    return coverage * np.where(stale_mask, 1.0 - stale_penalty, 1.0)


def compute_reliability_trust(
    *,
    epistemic_uncertainty: np.ndarray,
    data_quality: np.ndarray,
) -> np.ndarray:
    """Compute how usable a prediction is, independent of how risky it says the ticker is.

    ``trust = data_quality * (1 - epistemic_uncertainty)``. Unlike
    :func:`compute_trust_score`, a high risk probability does not raise trust.
    """

    uncertainty = _unit_interval("epistemic_uncertainty", epistemic_uncertainty)
    quality = _unit_interval("data_quality", data_quality)
    if uncertainty.shape != quality.shape:
        raise ValueError("epistemic_uncertainty and data_quality must have the same shape")
    return np.clip(quality * (1.0 - uncertainty), 0.0, 1.0)
