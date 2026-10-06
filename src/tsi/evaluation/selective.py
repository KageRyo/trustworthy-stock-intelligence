"""Selective prediction (risk-coverage) evaluation for trust signals.

A useful trust score lets users ignore low-trust predictions and get better
predictions on the rest. These helpers keep the highest-confidence rows first and
measure quality on the retained subset. Brier skill is computed against the
retained subset's own event rate so that a score which merely keeps low-risk rows
does not look better by lowering the base rate.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from tsi.evaluation.metrics import expected_calibration_error

DEFAULT_COVERAGES: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def risk_coverage_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    confidence: np.ndarray,
    *,
    coverages: Sequence[float] = DEFAULT_COVERAGES,
) -> pd.DataFrame:
    """Return retained-subset quality metrics at each coverage level."""

    labels = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(y_prob, dtype=float)
    scores = np.asarray(confidence, dtype=float)
    if not (len(labels) == len(probabilities) == len(scores)):
        raise ValueError("y_true, y_prob, and confidence must have the same length")
    if len(labels) == 0:
        raise ValueError("y_true must not be empty")
    if not coverages or any(not 0.0 < coverage <= 1.0 for coverage in coverages):
        raise ValueError("coverages must be in (0, 1]")

    order = np.argsort(-scores, kind="stable")
    rows: list[dict[str, float]] = []
    for coverage in coverages:
        retained = order[: max(1, int(round(coverage * len(labels))))]
        subset_labels = labels[retained]
        subset_probabilities = probabilities[retained]
        event_rate = float(subset_labels.mean())
        brier = float(np.mean((subset_probabilities - subset_labels) ** 2))
        reference = event_rate * (1.0 - event_rate)
        auc = (
            float(roc_auc_score(subset_labels, subset_probabilities))
            if np.unique(subset_labels).size == 2
            else float("nan")
        )
        rows.append(
            {
                "coverage": float(coverage),
                "rows": float(len(retained)),
                "event_rate": event_rate,
                "brier_score": brier,
                "brier_skill_score": 1.0 - brier / reference if reference > 0 else float("nan"),
                "ece": expected_calibration_error(subset_labels, subset_probabilities),
                "auc": auc,
                "min_confidence": float(scores[retained].min()),
            }
        )
    curve = pd.DataFrame(rows)
    curve["rows"] = curve["rows"].astype(int)
    return curve


def selective_summary(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    confidence: np.ndarray,
    *,
    coverages: Sequence[float] = DEFAULT_COVERAGES,
) -> dict[str, float]:
    """Summarize a risk-coverage curve; lower AURC and higher skill are better."""

    curve = risk_coverage_curve(y_true, y_prob, confidence, coverages=coverages)
    full = curve.iloc[-1]
    return {
        "aurc_brier": float(curve["brier_score"].mean()),
        "mean_brier_skill_score": float(curve["brier_skill_score"].mean(skipna=True)),
        "mean_ece": float(curve["ece"].mean()),
        "mean_auc": float(curve["auc"].mean(skipna=True)),
        "full_coverage_brier": float(full["brier_score"]),
    }
