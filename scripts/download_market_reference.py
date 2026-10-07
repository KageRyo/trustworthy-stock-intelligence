"""Download market reference series (US: SPY, ^VIX, sector ETFs; Taiwan: ^TWII)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from tsi.data.market_reference import download_market_reference


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--tickers-file",
        type=Path,
        help="CSV with a ticker column, for example data/raw/sp100/tickers.csv.",
    )
    source.add_argument("--tickers", nargs="+", help="Explicit ticker symbols.")
    parser.add_argument("--market", choices=["us", "taiwan"], default="us")
    parser.add_argument("--start", default="2015-01-01", help="Inclusive start date.")
    parser.add_argument("--end", default=None, help="Exclusive end date.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/market/us"),
        help="Directory for ohlcv.csv, sector_map.csv, and metadata.json.",
    )
    return parser.parse_args(argv)


def resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        return list(args.tickers)
    frame = pd.read_csv(args.tickers_file, dtype={"ticker": "string"})
    return frame["ticker"].dropna().astype(str).str.strip().tolist()


def main() -> None:
    args = parse_args()
    result = download_market_reference(
        resolve_tickers(args),
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        market=args.market,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
