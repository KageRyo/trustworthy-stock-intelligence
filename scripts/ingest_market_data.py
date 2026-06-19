"""Fetch market data from a provider and upsert it into PostgreSQL."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from tsi.data.download import download_ticker_frame
from tsi.data.postgres import (
    build_ingestion_summary,
    build_market_bar_rows,
    read_watchlist_tickers,
    write_download_to_postgres,
)

DEFAULT_DATABASE_URL = "postgresql://tsi:tsi_local_password@localhost:55432/tsi"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Ticker symbols or Taiwan numeric stock codes, for example NVDA 2330.",
    )
    parser.add_argument(
        "--watchlist-name",
        default=None,
        help="Read active ticker symbols from this PostgreSQL watchlist when --tickers is omitted.",
    )
    parser.add_argument(
        "--market",
        choices=["auto", "us", "twse", "tpex"],
        default="auto",
        help="Ticker market resolver. auto maps numeric tickers to TWSE yfinance symbols.",
    )
    parser.add_argument(
        "--interval",
        choices=["1m", "5m", "1d"],
        default="5m",
        help="OHLCV interval to request and store.",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Inclusive provider start date. Defaults to 7 days ago for intraday, 2015-01-01 for daily.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Exclusive provider end date.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="Number of provider query symbols per download batch.",
    )
    parser.add_argument(
        "--provider",
        choices=["yfinance"],
        default="yfinance",
        help="Market data provider.",
    )
    parser.add_argument(
        "--universe-name",
        default="watchlist",
        help="Universe name to upsert and attach tickers to.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL connection URL. Defaults to TSI_DATABASE_URL or local docker-compose.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and validate rows without writing to PostgreSQL.",
    )
    return parser.parse_args(argv)


def default_start_for_interval(interval: str) -> str:
    """Return a provider-friendly default start for the selected interval."""

    if interval in {"1m", "5m"}:
        return (datetime.now(UTC).date() - timedelta(days=7)).isoformat()
    return "2015-01-01"


def main() -> None:
    args = parse_args()
    tickers = list(args.tickers or [])
    if not tickers and args.watchlist_name:
        tickers = read_watchlist_tickers(args.database_url, args.watchlist_name)
    if not tickers:
        raise ValueError("--tickers or --watchlist-name with active DB tickers is required")
    start = args.start or default_start_for_interval(args.interval)
    result = download_ticker_frame(
        tickers=tickers,
        start=start,
        end=args.end,
        market=args.market,
        interval=args.interval,
        batch_size=args.batch_size,
        dataset_name=args.universe_name,
    )
    if args.dry_run:
        rows = build_market_bar_rows(result, provider=args.provider)
        summary = build_ingestion_summary(
            result,
            rows,
            provider=args.provider,
            universe_name=args.universe_name,
            status="dry_run",
            database_write=False,
        )
    else:
        summary = write_download_to_postgres(
            args.database_url,
            result,
            provider=args.provider,
            universe_name=args.universe_name,
        )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
