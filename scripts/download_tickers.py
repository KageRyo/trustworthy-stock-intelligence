"""Download OHLCV data for explicit stock tickers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from tsi.data.download import download_ticker_list, result_to_json


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="Ticker symbols or Taiwan numeric stock codes, for example NVDA 2330.",
    )
    parser.add_argument(
        "--market",
        choices=["auto", "us", "twse", "tpex", "emerging"],
        default="auto",
        help="Ticker market resolver. auto maps numeric tickers to TWSE yfinance symbols.",
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
        "--output-dir",
        type=Path,
        default=Path("data/raw/watchlist"),
        help="Directory where downloaded CSV artifacts are written.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="Number of yfinance query symbols per download batch.",
    )
    parser.add_argument(
        "--interval",
        choices=["1m", "5m", "1d"],
        default="1d",
        help="OHLCV interval to request from yfinance.",
    )
    parser.add_argument(
        "--dataset-name",
        default="watchlist",
        help="Dataset name written into metadata.",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    result = download_ticker_list(
        tickers=args.tickers,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        market=args.market,
        interval=args.interval,
        batch_size=args.batch_size,
        dataset_name=args.dataset_name,
    )
    print(result_to_json(result))


if __name__ == "__main__":
    main()
