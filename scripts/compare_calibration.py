"""Compare raw and calibrated probabilities across folds and time periods."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from tsi.evaluation.metrics import classification_metrics

CALIBRATION_METRICS = ("brier_score", "ece")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prediction CSV input.")
    parser.add_argument("--label-col", default="risk_label")
    parser.add_argument("--raw-prob-col", default="risk_probability")
    parser.add_argument(
        "--calibrated-prob-col",
        default="calibrated_risk_probability",
    )
    parser.add_argument(
        "--group-cols",
        nargs="*",
        default=["fold_id"],
        help="Columns used for separate comparisons, such as fold_id, market, or sector.",
    )
    parser.add_argument("--date-col", default="date")
    parser.add_argument(
        "--period",
        choices=["none", "year", "quarter"],
        default="year",
        help="Optional temporal robustness breakdown.",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def compare_probabilities(
    labels: pd.Series,
    raw_probabilities: pd.Series,
    calibrated_probabilities: pd.Series,
    *,
    threshold: float,
) -> dict[str, object]:
    """Return raw/calibrated metrics and paired deltas on the same rows."""

    raw = classification_metrics(
        labels.to_numpy(),
        raw_probabilities.to_numpy(),
        threshold=threshold,
    )
    calibrated = classification_metrics(
        labels.to_numpy(),
        calibrated_probabilities.to_numpy(),
        threshold=threshold,
    )
    deltas: dict[str, float | None] = {}
    for metric in raw:
        raw_value = raw[metric]
        calibrated_value = calibrated[metric]
        if math.isfinite(raw_value) and math.isfinite(calibrated_value):
            deltas[metric] = calibrated_value - raw_value
        else:
            deltas[metric] = None
    return {
        "row_count": int(len(labels)),
        "raw": {
            metric: value if math.isfinite(value) else None for metric, value in raw.items()
        },
        "calibrated": {
            metric: value if math.isfinite(value) else None
            for metric, value in calibrated.items()
        },
        "delta_calibrated_minus_raw": deltas,
    }


def _json_scalar(value: object) -> object:
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


def _dimension_comparisons(
    predictions: pd.DataFrame,
    *,
    dimension: str,
    label_col: str,
    raw_prob_col: str,
    calibrated_prob_col: str,
    threshold: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group, frame in predictions.groupby(dimension, dropna=False, sort=True):
        rows.append(
            {
                "group": _json_scalar(group),
                **compare_probabilities(
                    frame[label_col],
                    frame[raw_prob_col],
                    frame[calibrated_prob_col],
                    threshold=threshold,
                ),
            }
        )
    return rows


def _improvement_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, Any] = {"group_count": len(rows)}
    for metric in CALIBRATION_METRICS:
        deltas = pd.Series(
            [
                row["delta_calibrated_minus_raw"][metric]  # type: ignore[index]
                for row in rows
            ],
            dtype=float,
        )
        summary[metric] = {
            "mean_delta_calibrated_minus_raw": float(deltas.mean()),
            "std_delta_calibrated_minus_raw": (
                float(deltas.std()) if not pd.isna(deltas.std()) else None
            ),
            "improved_group_count": int((deltas < 0.0).sum()),
            "unchanged_group_count": int((deltas == 0.0).sum()),
            "worsened_group_count": int((deltas > 0.0).sum()),
        }
    return summary


def run_comparison(args: argparse.Namespace) -> dict[str, object]:
    """Load one prediction artifact and compare calibration by requested dimensions."""

    predictions = pd.read_csv(args.input)
    required = {
        args.label_col,
        args.raw_prob_col,
        args.calibrated_prob_col,
        *args.group_cols,
    }
    if args.period != "none":
        required.add(args.date_col)
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    dimensions = list(args.group_cols)
    if args.period != "none":
        dates = pd.to_datetime(predictions[args.date_col], errors="raise")
        period_frequency = "Y" if args.period == "year" else "Q"
        period_column = f"__{args.period}"
        predictions[period_column] = dates.dt.to_period(period_frequency).astype(str)
        dimensions.append(period_column)

    by_dimension: dict[str, object] = {}
    for dimension in dimensions:
        rows = _dimension_comparisons(
            predictions,
            dimension=dimension,
            label_col=args.label_col,
            raw_prob_col=args.raw_prob_col,
            calibrated_prob_col=args.calibrated_prob_col,
            threshold=args.threshold,
        )
        display_name = dimension.removeprefix("__")
        by_dimension[display_name] = {
            "groups": rows,
            "improvement_summary": _improvement_summary(rows),
        }

    return {
        "input": str(args.input),
        "label_col": args.label_col,
        "raw_prob_col": args.raw_prob_col,
        "calibrated_prob_col": args.calibrated_prob_col,
        "threshold": args.threshold,
        "overall": compare_probabilities(
            predictions[args.label_col],
            predictions[args.raw_prob_col],
            predictions[args.calibrated_prob_col],
            threshold=args.threshold,
        ),
        "by_dimension": by_dimension,
    }


def main() -> None:
    args = parse_args()
    result = run_comparison(args)
    output = json.dumps(result, indent=2, allow_nan=False)
    print(output)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
