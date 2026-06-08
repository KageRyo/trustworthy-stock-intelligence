"""Evaluate trust-aware warning-level prediction artifacts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from tsi.evaluation.warning_metrics import trust_warning_metrics


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to prediction CSV input.")
    parser.add_argument("--label-col", default="risk_label", help="Binary ground-truth label column.")
    parser.add_argument("--warning-col", default="warning_level", help="Warning-level column.")
    parser.add_argument("--trust-col", default="trust_score", help="Optional trust score column.")
    parser.add_argument(
        "--uncertainty-col",
        default="uncertainty_score",
        help="Optional uncertainty score column.",
    )
    parser.add_argument(
        "--group-col",
        default="fold_id",
        help="Optional grouping column for per-group metrics. Use an empty string to disable.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args(argv)


def _optional_array(frame: pd.DataFrame, column: str):
    if not column or column not in frame.columns:
        return None
    return frame[column].to_numpy()


def _evaluate_frame(frame: pd.DataFrame, args: argparse.Namespace) -> dict[str, object]:
    return trust_warning_metrics(
        frame[args.label_col].to_numpy(),
        frame[args.warning_col].to_numpy(),
        trust_scores=_optional_array(frame, args.trust_col),
        uncertainty_scores=_optional_array(frame, args.uncertainty_col),
    )


def run_evaluation(args: argparse.Namespace) -> dict[str, object]:
    predictions = pd.read_csv(args.input)
    overall = _evaluate_frame(predictions, args)

    by_group: list[dict[str, object]] = []
    if args.group_col:
        for group_value, group_frame in predictions.groupby(args.group_col):
            by_group.append(
                {
                    "group": int(group_value)
                    if isinstance(group_value, int | float) and float(group_value).is_integer()
                    else group_value,
                    "row_count": int(len(group_frame)),
                    "metrics": _evaluate_frame(group_frame, args),
                }
            )

    return {
        "input": str(args.input),
        "label_col": args.label_col,
        "warning_col": args.warning_col,
        "trust_col": args.trust_col if args.trust_col in predictions.columns else None,
        "uncertainty_col": args.uncertainty_col if args.uncertainty_col in predictions.columns else None,
        "group_col": args.group_col,
        "row_count": int(len(predictions)),
        "overall": overall,
        "by_group": by_group,
    }


def main() -> None:
    args = parse_args()
    results = run_evaluation(args)
    output = json.dumps(results, indent=2)
    print(output)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
