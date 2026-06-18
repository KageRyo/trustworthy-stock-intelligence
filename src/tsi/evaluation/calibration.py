"""Calibration reliability diagnostics."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def reliability_bins(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Compute equal-width reliability bins for binary probabilities."""

    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have the same length")
    if len(y_true) == 0:
        raise ValueError("y_true and y_prob must not be empty")
    if np.any((y_prob < 0.0) | (y_prob > 1.0)):
        raise ValueError("y_prob values must be between 0 and 1")

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows: list[dict[str, float | int]] = []
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        if math.isclose(upper, 1.0):
            mask = (y_prob >= lower) & (y_prob <= upper)
        else:
            mask = (y_prob >= lower) & (y_prob < upper)
        count = int(mask.sum())
        if count:
            mean_probability = float(y_prob[mask].mean())
            observed_rate = float(y_true[mask].mean())
        else:
            mean_probability = float("nan")
            observed_rate = float("nan")
        rows.append(
            {
                "bin_lower": float(lower),
                "bin_upper": float(upper),
                "count": count,
                "mean_predicted_probability": mean_probability,
                "observed_positive_rate": observed_rate,
            }
        )
    return pd.DataFrame(rows)
