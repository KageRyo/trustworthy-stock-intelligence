"""Sweep trust warning thresholds over an existing prediction artifact."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from tsi.evaluation.warning_metrics import trust_warning_metrics
from tsi.trust.decision import compute_watch_threshold
from tsi.trust.trust_score import compute_trust_score


def parse_float_grid(raw: str) -> list[float]:
    """Parse a comma-separated float grid."""

    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        raise ValueError("float grid must not be empty")
    return [float(value) for value in values]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prediction CSV input.")
    parser.add_argument("--output", type=Path, required=True, help="Sweep CSV output.")
    parser.add_argument("--label-col", default="risk_label")
    parser.add_argument("--prob-col", default="calibrated_risk_probability")
    parser.add_argument("--uncertainty-col", default="uncertainty_score")
    parser.add_argument("--alert-threshold-col", default="alert_threshold")
    parser.add_argument("--watch-threshold-ratios", default="0.6,0.7,0.8,0.9")
    parser.add_argument("--trust-thresholds", default="0.3,0.4,0.5,0.6,0.7")
    parser.add_argument("--uncertainty-thresholds", default="0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--uncertainty-penalties", default="0.25,0.5,0.75")
    parser.add_argument("--min-watch-threshold", type=float, default=0.05)
    parser.add_argument("--print-rows", type=int, default=20, help="Rows to print after writing CSV.")
    return parser.parse_args(argv)


def assign_swept_warning_levels(
    *,
    calibrated_probabilities: np.ndarray,
    alert_thresholds: np.ndarray,
    uncertainty_scores: np.ndarray,
    trust_scores: np.ndarray,
    watch_threshold_ratio: float,
    min_watch_threshold: float,
    trust_threshold: float,
    uncertainty_threshold: float,
) -> np.ndarray:
    """Assign warning levels with per-row alert thresholds."""

    probabilities = np.asarray(calibrated_probabilities, dtype=float)
    alerts = np.asarray(alert_thresholds, dtype=float)
    uncertainty = np.asarray(uncertainty_scores, dtype=float)
    trust = np.asarray(trust_scores, dtype=float)
    if not (
        probabilities.shape == alerts.shape == uncertainty.shape == trust.shape
    ):
        raise ValueError("all input arrays must have the same shape")

    watch_thresholds = np.asarray(
        [
            compute_watch_threshold(
                float(alert_threshold),
                watch_threshold_ratio=watch_threshold_ratio,
                min_watch_threshold=min_watch_threshold,
            )
            for alert_threshold in alerts
        ],
        dtype=float,
    )

    levels = np.full(probabilities.shape, "no_alert", dtype=object)
    levels[uncertainty >= uncertainty_threshold] = "abstain"
    levels[probabilities >= watch_thresholds] = "watch"
    levels[(probabilities >= alerts) & (trust >= trust_threshold)] = "alert"
    return levels


def run_sweep(
    predictions: pd.DataFrame,
    *,
    watch_threshold_ratios: Sequence[float],
    trust_thresholds: Sequence[float],
    uncertainty_thresholds: Sequence[float],
    uncertainty_penalties: Sequence[float],
    min_watch_threshold: float,
    label_col: str = "risk_label",
    prob_col: str = "calibrated_risk_probability",
    uncertainty_col: str = "uncertainty_score",
    alert_threshold_col: str = "alert_threshold",
) -> pd.DataFrame:
    """Run a threshold grid over fixed prediction probabilities."""

    labels = predictions[label_col].to_numpy()
    probabilities = predictions[prob_col].to_numpy(dtype=float)
    uncertainty = predictions[uncertainty_col].to_numpy(dtype=float)
    alert_thresholds = predictions[alert_threshold_col].to_numpy(dtype=float)

    rows: list[dict[str, object]] = []
    for ratio, trust_threshold, uncertainty_threshold, penalty in product(
        watch_threshold_ratios,
        trust_thresholds,
        uncertainty_thresholds,
        uncertainty_penalties,
    ):
        trust_scores = compute_trust_score(
            probabilities,
            uncertainty,
            uncertainty_penalty=float(penalty),
        )
        warning_levels = assign_swept_warning_levels(
            calibrated_probabilities=probabilities,
            alert_thresholds=alert_thresholds,
            uncertainty_scores=uncertainty,
            trust_scores=trust_scores,
            watch_threshold_ratio=float(ratio),
            min_watch_threshold=min_watch_threshold,
            trust_threshold=float(trust_threshold),
            uncertainty_threshold=float(uncertainty_threshold),
        )
        metrics = trust_warning_metrics(
            labels,
            warning_levels,
            trust_scores=trust_scores,
            uncertainty_scores=uncertainty,
        )
        flat_metrics = {
            key: value
            for key, value in metrics.items()
            if not isinstance(value, dict)
        }
        rows.append(
            {
                "watch_threshold_ratio": float(ratio),
                "trust_threshold": float(trust_threshold),
                "uncertainty_threshold": float(uncertainty_threshold),
                "uncertainty_penalty": float(penalty),
                "min_watch_threshold": float(min_watch_threshold),
                **flat_metrics,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    predictions = pd.read_csv(args.input)
    results = run_sweep(
        predictions,
        watch_threshold_ratios=parse_float_grid(args.watch_threshold_ratios),
        trust_thresholds=parse_float_grid(args.trust_thresholds),
        uncertainty_thresholds=parse_float_grid(args.uncertainty_thresholds),
        uncertainty_penalties=parse_float_grid(args.uncertainty_penalties),
        min_watch_threshold=args.min_watch_threshold,
        label_col=args.label_col,
        prob_col=args.prob_col,
        uncertainty_col=args.uncertainty_col,
        alert_threshold_col=args.alert_threshold_col,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    if args.print_rows > 0:
        print(results.head(args.print_rows).to_string(index=False))


if __name__ == "__main__":
    main()
