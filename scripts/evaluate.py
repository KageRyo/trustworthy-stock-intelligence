"""Evaluate stock risk warning prediction artifacts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from tsi.evaluation.metrics import classification_metrics


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to prediction CSV input.")
    parser.add_argument(
        "--label-col",
        default="risk_label",
        help="Binary ground-truth label column.",
    )
    parser.add_argument(
        "--prob-col",
        default="risk_probability",
        help="Predicted probability column.",
    )
    parser.add_argument(
        "--group-col",
        default="fold_id",
        help="Optional grouping column for per-group metrics. Use an empty string to disable.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Decision threshold for binary metrics.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser.parse_args(argv)


def run_evaluation(args: argparse.Namespace) -> dict[str, object]:
    predictions = pd.read_csv(args.input)
    overall = classification_metrics(
        predictions[args.label_col].to_numpy(),
        predictions[args.prob_col].to_numpy(),
        threshold=args.threshold,
    )

    by_group: list[dict[str, object]] = []
    if args.group_col:
        for group_value, group_frame in predictions.groupby(args.group_col):
            by_group.append(
                {
                    "group": group_value,
                    "metrics": classification_metrics(
                        group_frame[args.label_col].to_numpy(),
                        group_frame[args.prob_col].to_numpy(),
                        threshold=args.threshold,
                    ),
                }
            )

    return {
        "input": str(args.input),
        "label_col": args.label_col,
        "prob_col": args.prob_col,
        "group_col": args.group_col,
        "threshold": args.threshold,
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
