"""Reproducible uncertainty intervals for paired fold-level experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BootstrapInterval:
    """A percentile bootstrap interval over independent resampling units."""

    estimate: float
    lower: float
    upper: float
    sample_count: int
    resamples: int
    confidence: float

    def as_dict(self) -> dict[str, float | int]:
        """Return a JSON-serializable representation."""

        return {
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "sample_count": self.sample_count,
            "resamples": self.resamples,
            "confidence": self.confidence,
        }


def bootstrap_mean_interval(
    values: Sequence[float] | np.ndarray,
    *,
    seed: int = 42,
    resamples: int = 4_000,
    confidence: float = 0.95,
) -> BootstrapInterval:
    """Estimate a mean and percentile interval by resampling whole units.

    For the research reports the units are temporal test folds, not individual
    rows. This keeps the interval paired with the walk-forward evaluation
    design and avoids claiming independent observations within a fold.
    """

    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if array.size == 0:
        raise ValueError("values must not be empty")
    if not np.all(np.isfinite(array)):
        raise ValueError("values must contain only finite numbers")
    _validate_bootstrap_options(resamples=resamples, confidence=confidence)

    rng = np.random.default_rng(seed)
    if array.size == 1:
        means = np.full(resamples, array[0], dtype=float)
    else:
        sample_indices = rng.integers(0, array.size, size=(resamples, array.size))
        means = array[sample_indices].mean(axis=1)

    alpha = (1.0 - confidence) / 2.0
    return BootstrapInterval(
        estimate=float(array.mean()),
        lower=float(np.quantile(means, alpha)),
        upper=float(np.quantile(means, 1.0 - alpha)),
        sample_count=int(array.size),
        resamples=resamples,
        confidence=confidence,
    )


def paired_fold_metric_intervals(
    baseline_folds: Sequence[Mapping[str, object]],
    comparison_folds: Sequence[Mapping[str, object]],
    *,
    metrics: Sequence[str],
    seed: int = 42,
    resamples: int = 4_000,
    confidence: float = 0.95,
) -> dict[str, object]:
    """Compare two models using paired, fold-level percentile bootstraps.

    ``baseline_folds`` and ``comparison_folds`` must contain the same ordered
    ``fold_id`` values. For each metric, the delta is defined as comparison
    minus baseline and is bootstrapped from the paired per-fold differences.
    Non-finite metric pairs are excluded together, which is important for AUC
    when a test fold contains a single class.
    """

    if not baseline_folds or not comparison_folds:
        raise ValueError("both fold collections must not be empty")
    if len(baseline_folds) != len(comparison_folds):
        raise ValueError("paired fold collections must have the same length")
    baseline_ids = [fold.get("fold_id") for fold in baseline_folds]
    comparison_ids = [fold.get("fold_id") for fold in comparison_folds]
    if baseline_ids != comparison_ids:
        raise ValueError("paired fold collections must have identical fold_id order")
    if not metrics:
        raise ValueError("metrics must not be empty")
    _validate_bootstrap_options(resamples=resamples, confidence=confidence)

    metric_results: dict[str, object] = {}
    for metric_index, metric in enumerate(metrics):
        baseline_values = _metric_values(baseline_folds, metric)
        comparison_values = _metric_values(comparison_folds, metric)
        finite_pairs = np.isfinite(baseline_values) & np.isfinite(comparison_values)
        if not np.any(finite_pairs):
            metric_results[metric] = {
                "baseline": None,
                "comparison": None,
                "delta": None,
                "excluded_non_finite_pairs": int(len(finite_pairs)),
            }
            continue

        baseline_values = baseline_values[finite_pairs]
        comparison_values = comparison_values[finite_pairs]
        baseline_interval = bootstrap_mean_interval(
            baseline_values,
            seed=seed + metric_index * 3,
            resamples=resamples,
            confidence=confidence,
        )
        comparison_interval = bootstrap_mean_interval(
            comparison_values,
            seed=seed + metric_index * 3 + 1,
            resamples=resamples,
            confidence=confidence,
        )
        delta_interval = bootstrap_mean_interval(
            comparison_values - baseline_values,
            seed=seed + metric_index * 3 + 2,
            resamples=resamples,
            confidence=confidence,
        )
        metric_results[metric] = {
            "baseline": baseline_interval.as_dict(),
            "comparison": comparison_interval.as_dict(),
            "delta": delta_interval.as_dict(),
            "excluded_non_finite_pairs": int((~finite_pairs).sum()),
        }

    return {
        "method": "percentile bootstrap over paired temporal test folds",
        "baseline_minus_comparison": "comparison - baseline",
        "fold_count": len(baseline_folds),
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "metrics": metric_results,
    }


def _metric_values(folds: Sequence[Mapping[str, object]], metric: str) -> np.ndarray:
    values: list[float] = []
    for fold in folds:
        value = fold.get(metric)
        if value is None:
            raise ValueError(f"missing metric {metric!r} in fold {fold.get('fold_id')!r}")
        try:
            values.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"metric {metric!r} is not numeric") from exc
    return np.asarray(values, dtype=float)


def _validate_bootstrap_options(*, resamples: int, confidence: float) -> None:
    if resamples < 1:
        raise ValueError("resamples must be at least 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
