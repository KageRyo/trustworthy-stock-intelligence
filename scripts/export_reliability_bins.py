"""Export calibration reliability bins from a predictions CSV."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from tsi.evaluation.calibration import reliability_bins


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Predictions CSV input.")
    parser.add_argument("--output", type=Path, required=True, help="Reliability bins CSV output.")
    parser.add_argument("--label-col", default="risk_label", help="Binary label column.")
    parser.add_argument(
        "--prob-col",
        default="calibrated_risk_probability",
        help="Probability column to bin.",
    )
    parser.add_argument("--bins", type=int, default=10, help="Number of equal-width bins.")
    return parser.parse_args(argv)


def export_reliability_bins(args: argparse.Namespace) -> pd.DataFrame:
    frame = pd.read_csv(args.input)
    missing = [column for column in (args.label_col, args.prob_col) if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    bins = reliability_bins(
        frame[args.label_col].to_numpy(),
        frame[args.prob_col].to_numpy(),
        n_bins=args.bins,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bins.to_csv(args.output, index=False)
    return bins


def main() -> None:
    args = parse_args()
    bins = export_reliability_bins(args)
    print(f"Wrote {len(bins)} reliability bins to {args.output}")


if __name__ == "__main__":
    main()
