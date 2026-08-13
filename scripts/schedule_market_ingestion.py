"""Run the DB-backed five-minute watchlist ingestion schedule."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from tsi.data.scheduled_ingestion import (
    ScheduledIngestionConfig,
    run_scheduled_ingestion_once,
    run_scheduler,
)
from tsi.data.postgres import read_latest_market_bar


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value (true/false)")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse scheduler settings from flags, with safe environment defaults."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to TSI_DATABASE_URL.",
    )
    parser.add_argument(
        "--watchlist-name",
        default=os.getenv("TSI_INGESTION_WATCHLIST", "default"),
        help="Active PostgreSQL watchlist to ingest.",
    )
    parser.add_argument(
        "--universe-name",
        default=os.getenv("TSI_INGESTION_UNIVERSE", "watchlist"),
        help="Universe name used for ingestion metadata and upserts.",
    )
    parser.add_argument(
        "--market",
        choices=["auto", "us", "twse", "tpex", "emerging"],
        default=os.getenv("TSI_INGESTION_MARKET", "auto"),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("TSI_INGESTION_BATCH_SIZE", "80")),
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.getenv("TSI_INGESTION_POLL_SECONDS", "300")),
        help="Seconds between scheduler ticks (minimum 30).",
    )
    parser.add_argument(
        "--retry-max-attempts",
        type=int,
        default=int(os.getenv("TSI_INGESTION_RETRY_MAX_ATTEMPTS", "3")),
    )
    parser.add_argument(
        "--retry-initial-backoff-seconds",
        type=float,
        default=float(os.getenv("TSI_INGESTION_RETRY_INITIAL_BACKOFF_SECONDS", "0.5")),
    )
    parser.add_argument(
        "--retry-max-backoff-seconds",
        type=float,
        default=float(os.getenv("TSI_INGESTION_RETRY_MAX_BACKOFF_SECONDS", "5.0")),
    )
    enabled = parser.add_mutually_exclusive_group()
    enabled.add_argument("--enabled", action="store_true", help="Enable scheduled writes.")
    enabled.add_argument("--disabled", action="store_true", help="Disable writes safely.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one tick and exit. Without this flag, keep polling until interrupted.",
    )
    args = parser.parse_args(argv)
    if args.enabled:
        args.ingestion_enabled = True
    elif args.disabled:
        args.ingestion_enabled = False
    else:
        args.ingestion_enabled = _env_bool("TSI_INGESTION_ENABLED", False)
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = ScheduledIngestionConfig(
        enabled=args.ingestion_enabled,
        database_url=args.database_url,
        watchlist_name=args.watchlist_name,
        universe_name=args.universe_name,
        market=args.market,
        batch_size=args.batch_size,
        poll_seconds=args.poll_seconds,
        retry_policy={
            "max_attempts": args.retry_max_attempts,
            "initial_backoff_seconds": args.retry_initial_backoff_seconds,
            "max_backoff_seconds": args.retry_max_backoff_seconds,
        },
    )
    if args.once or not config.enabled:
        print(
            run_scheduled_ingestion_once(
                config,
                read_latest_bar=read_latest_market_bar,
            ).model_dump_json(indent=2)
        )
        return
    run_scheduler(config)


if __name__ == "__main__":
    main()
