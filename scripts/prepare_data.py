"""Prepare pilot OHLCV datasets for risk warning experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from tsi.data.download import download_universe, result_to_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--universe",
        choices=["sp100", "sp500", "all"],
        default="all",
        help="Universe to download.",
    )
    parser.add_argument(
        "--start",
        default="2015-01-01",
        help="Inclusive start date passed to yfinance, formatted as YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Exclusive end date passed to yfinance, formatted as YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/raw"),
        help="Directory where downloaded CSV artifacts are written.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="Number of tickers per yfinance batch.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universes = ["sp100", "sp500"] if args.universe == "all" else [args.universe]

    for universe in universes:
        result = download_universe(
            name=universe,
            output_root=args.output_root,
            start=args.start,
            end=args.end,
            batch_size=args.batch_size,
        )
        print(result_to_json(result))


if __name__ == "__main__":
    main()
