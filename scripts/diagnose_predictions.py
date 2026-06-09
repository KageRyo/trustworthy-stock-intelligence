"""Diagnose probability, uncertainty, and trust distributions in prediction CSVs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from tsi.trust.decision import compute_watch_threshold

QUANTILES = (0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prediction CSV input.")
    parser.add_argument("--output", type=Path, default=None, help="Optional diagnostics JSON output.")
    parser.add_argument("--label-col", default="risk_label")
    parser.add_argument("--prob-col", default="calibrated_risk_probability")
    parser.add_argument("--raw-prob-col", default="risk_probability")
    parser.add_argument("--uncertainty-col", default="uncertainty_score")
    parser.add_argument("--trust-col", default="trust_score")
    parser.add_argument("--alert-threshold-col", default="alert_threshold")
    parser.add_argument("--watch-threshold-ratio", type=float, default=0.8)
    parser.add_argument("--min-watch-threshold", type=float, default=0.05)
    parser.add_argument("--trust-threshold", type=float, default=0.5)
    return parser.parse_args(argv)


def _to_float(value: object) -> float | None:
    number = float(value)
    if np.isnan(number):
        return None
    return number


def _numeric_summary(values: pd.Series) -> dict[str, object]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {"count": 0}
    quantiles = numeric.quantile(list(QUANTILES))
    return {
        "count": int(numeric.shape[0]),
        "mean": _to_float(numeric.mean()),
        "std": _to_float(numeric.std()),
        "min": _to_float(numeric.min()),
        "max": _to_float(numeric.max()),
        "quantiles": {f"{quantile:.2f}": _to_float(value) for quantile, value in quantiles.items()},
    }


def _column_summary(frame: pd.DataFrame, columns: Sequence[str]) -> dict[str, object]:
    return {column: _numeric_summary(frame[column]) for column in columns if column in frame.columns}


def _watch_thresholds(
    alert_thresholds: pd.Series,
    *,
    watch_threshold_ratio: float,
    min_watch_threshold: float,
) -> pd.Series:
    numeric_alerts = pd.to_numeric(alert_thresholds, errors="coerce").dropna()
    values = [
        compute_watch_threshold(
            float(alert_threshold),
            watch_threshold_ratio=watch_threshold_ratio,
            min_watch_threshold=min_watch_threshold,
        )
        for alert_threshold in numeric_alerts
    ]
    return pd.Series(values, dtype=float)


def run_diagnostics(args: argparse.Namespace) -> dict[str, object]:
    """Run diagnostics and optionally write them as JSON."""

    frame = pd.read_csv(args.input)
    required = [
        args.label_col,
        args.prob_col,
        args.uncertainty_col,
        args.trust_col,
        args.alert_threshold_col,
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    labels = pd.to_numeric(frame[args.label_col], errors="coerce")
    positive_rate = _to_float((labels == 1).mean())
    columns = [
        args.raw_prob_col,
        args.prob_col,
        args.uncertainty_col,
        args.trust_col,
        args.alert_threshold_col,
    ]
    column_summaries = _column_summary(frame, columns)
    column_summaries["watch_threshold"] = _numeric_summary(
        _watch_thresholds(
            frame[args.alert_threshold_col],
            watch_threshold_ratio=args.watch_threshold_ratio,
            min_watch_threshold=args.min_watch_threshold,
        )
    )

    probabilities = pd.to_numeric(frame[args.prob_col], errors="coerce")
    trust_scores = pd.to_numeric(frame[args.trust_col], errors="coerce")
    alert_thresholds = pd.to_numeric(frame[args.alert_threshold_col], errors="coerce")
    p_ge_alert = probabilities >= alert_thresholds
    trust_ge_threshold = trust_scores >= args.trust_threshold

    by_label = {}
    for label, group in frame.groupby(args.label_col, dropna=False):
        by_label[str(label)] = {
            "row_count": int(group.shape[0]),
            "columns": _column_summary(
                group,
                [args.raw_prob_col, args.prob_col, args.uncertainty_col, args.trust_col],
            ),
        }

    diagnostics = {
        "input": str(args.input),
        "row_count": int(frame.shape[0]),
        "positive_rate": positive_rate,
        "columns": column_summaries,
        "decision_readiness": {
            "trust_threshold": float(args.trust_threshold),
            "rows_p_ge_alert": int(p_ge_alert.sum()),
            "rows_trust_ge_threshold": int(trust_ge_threshold.sum()),
            "rows_p_ge_alert_and_trust_ge_threshold": int((p_ge_alert & trust_ge_threshold).sum()),
        },
        "by_label": by_label,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    return diagnostics


def main() -> None:
    args = parse_args()
    diagnostics = run_diagnostics(args)
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
