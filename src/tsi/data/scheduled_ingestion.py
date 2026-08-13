"""Safe, per-ticker scheduling primitives for five-minute watchlist ingestion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import sleep
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tsi.data.download import (
    DownloadFrameResult,
    DownloadUnavailableError,
    TickerMarket,
    download_ticker_frame,
)
from tsi.data.postgres import (
    MarketDataIngestionSummary,
    read_latest_market_bar,
    read_watchlist_tickers,
    write_download_to_postgres,
    write_provider_health_to_postgres,
)
from tsi.data.provider_health import ProviderHealthSnapshot, RetryPolicy
from tsi.observability import log_event

ScheduledStatus = Literal["success", "partial", "failed", "disabled", "no_tickers"]
TickerIngestionStatus = Literal["success", "failed", "skipped"]


class ScheduledIngestionConfig(BaseModel):
    """Configuration for one safe scheduler tick and its optional loop."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "scheduled_ingestion.v1"
    enabled: bool = False
    # Disabled schedules are intentionally constructible without credentials so
    # a safe default configuration can be loaded in local development.
    database_url: str = ""
    watchlist_name: str = Field(default="default", min_length=1)
    universe_name: str = Field(default="watchlist", min_length=1)
    provider: Literal["yfinance"] = "yfinance"
    market: TickerMarket = "auto"
    interval: Literal["5m"] = "5m"
    batch_size: int = Field(default=80, ge=1, le=500)
    poll_seconds: int = Field(default=300, ge=30, le=86400)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class TickerIngestionOutcome(BaseModel):
    """Isolated outcome for one watchlist ticker."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    status: TickerIngestionStatus
    row_count: int = Field(default=0, ge=0)
    provider_health_count: int = Field(default=0, ge=0)
    ingestion_run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ScheduledIngestionSummary(BaseModel):
    """Schema-first summary for one scheduler tick."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "scheduled_ingestion.v1"
    status: ScheduledStatus
    enabled: bool
    watchlist_name: str
    universe_name: str
    provider: str
    interval: Literal["5m"]
    started_at: str
    completed_at: str
    requested_tickers: list[str]
    succeeded_tickers: list[str]
    failed_tickers: list[str]
    skipped_tickers: list[str]
    row_count: int = Field(ge=0)
    provider_health_count: int = Field(ge=0)
    outcomes: list[TickerIngestionOutcome]


ReadWatchlist = Callable[[str, str], list[str]]
ReadLatestBar = Callable[..., datetime | None]
DownloadTickerFrame = Callable[..., DownloadFrameResult]
WriteDownload = Callable[..., MarketDataIngestionSummary]
WriteProviderHealth = Callable[[str, list[ProviderHealthSnapshot]], int]


def _timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _unique_tickers(tickers: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if normalized and normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique


def run_scheduled_ingestion_once(
    config: ScheduledIngestionConfig,
    *,
    read_watchlist: ReadWatchlist = read_watchlist_tickers,
    read_latest_bar: ReadLatestBar | None = None,
    download: DownloadTickerFrame = download_ticker_frame,
    write_download: WriteDownload = write_download_to_postgres,
    write_provider_health: WriteProviderHealth = write_provider_health_to_postgres,
    started_at: datetime | None = None,
) -> ScheduledIngestionSummary:
    """Ingest each active watchlist ticker independently.

    A failed provider request never aborts neighboring tickers.  Successful
    writes use the existing market-bar primary key/upsert path, so rerunning a
    scheduler tick updates a bar rather than inserting a duplicate.
    """

    started = _timestamp(started_at)
    log_event(
        "ingestion_started",
        service="scheduled_ingestion",
        watchlist_name=config.watchlist_name,
        provider=config.provider,
        interval=config.interval,
        enabled=config.enabled,
    )
    if not config.enabled:
        return ScheduledIngestionSummary(
            status="disabled",
            enabled=False,
            watchlist_name=config.watchlist_name,
            universe_name=config.universe_name,
            provider=config.provider,
            interval=config.interval,
            started_at=started.isoformat(),
            completed_at=started.isoformat(),
            requested_tickers=[],
            succeeded_tickers=[],
            failed_tickers=[],
            skipped_tickers=[],
            row_count=0,
            provider_health_count=0,
            outcomes=[],
        )

    if not config.database_url.strip():
        raise ValueError("database_url is required when scheduled ingestion is enabled")

    tickers = _unique_tickers(read_watchlist(config.database_url, config.watchlist_name))
    if not tickers:
        return ScheduledIngestionSummary(
            status="no_tickers",
            enabled=True,
            watchlist_name=config.watchlist_name,
            universe_name=config.universe_name,
            provider=config.provider,
            interval=config.interval,
            started_at=started.isoformat(),
            completed_at=_timestamp(None).isoformat(),
            requested_tickers=[],
            succeeded_tickers=[],
            failed_tickers=[],
            skipped_tickers=[],
            row_count=0,
            provider_health_count=0,
            outcomes=[],
        )

    # Custom watchlist readers are commonly used by tests and job adapters. In
    # the built-in DB path, use the latest stored bar as a provider cursor; an
    # explicit callback lets adapters keep that lookup replaceable.
    latest_reader = read_latest_bar
    if latest_reader is None and read_watchlist is read_watchlist_tickers:
        latest_reader = read_latest_market_bar

    outcomes: list[TickerIngestionOutcome] = []
    row_count = 0
    provider_health_count = 0
    for ticker in tickers:
        try:
            latest = (
                latest_reader(
                    config.database_url,
                    ticker,
                    interval=config.interval,
                    provider=config.provider,
                )
                if latest_reader is not None
                else None
            )
            next_start = _timestamp(latest) + timedelta(minutes=5) if latest is not None else None
            if next_start is not None and next_start >= started:
                outcomes.append(
                    TickerIngestionOutcome(
                        ticker=ticker,
                        status="skipped",
                        error_code="up_to_date",
                        error_message="stored market bar is current for the scheduler interval",
                    )
                )
                continue
            result = download(
                tickers=[ticker],
                start=(next_start.isoformat() if next_start is not None else started.date().isoformat()),
                market=config.market,
                interval=config.interval,
                batch_size=config.batch_size,
                dataset_name=config.universe_name,
                retry_policy=config.retry_policy,
            )
            summary = write_download(
                config.database_url,
                result,
                provider=config.provider,
                universe_name=config.universe_name,
            )
            rows = len(result.ohlcv)
            health_count = len(result.provider_health)
            outcomes.append(
                TickerIngestionOutcome(
                    ticker=ticker,
                    status="success",
                    row_count=rows,
                    provider_health_count=health_count,
                    ingestion_run_id=summary.ingestion_run_id,
                )
            )
            row_count += rows
            provider_health_count += health_count
        except DownloadUnavailableError as exc:
            health_count = 0
            try:
                health_count = write_provider_health(config.database_url, exc.provider_health)
            except Exception as health_exc:  # keep neighboring ticker work isolated
                error_message = f"{exc}; provider health persistence failed: {health_exc}"
            else:
                error_message = str(exc)
            outcomes.append(
                TickerIngestionOutcome(
                    ticker=ticker,
                    status="failed",
                    provider_health_count=health_count,
                    error_code="provider_unavailable",
                    error_message=error_message[:2000],
                )
            )
            provider_health_count += health_count
        except Exception as exc:  # one ticker/provider must not stop the schedule
            outcomes.append(
                TickerIngestionOutcome(
                    ticker=ticker,
                    status="failed",
                    error_code="ingestion_failed",
                    error_message=str(exc)[:2000],
                )
            )

    succeeded = [outcome.ticker for outcome in outcomes if outcome.status == "success"]
    failed = [outcome.ticker for outcome in outcomes if outcome.status == "failed"]
    skipped = [outcome.ticker for outcome in outcomes if outcome.status == "skipped"]
    if failed and (succeeded or skipped):
        status: ScheduledStatus = "partial"
    elif succeeded or skipped:
        status = "success"
    else:
        status = "failed"
    summary = ScheduledIngestionSummary(
        status=status,
        enabled=True,
        watchlist_name=config.watchlist_name,
        universe_name=config.universe_name,
        provider=config.provider,
        interval=config.interval,
        started_at=started.isoformat(),
        completed_at=_timestamp(None).isoformat(),
        requested_tickers=tickers,
        succeeded_tickers=succeeded,
        failed_tickers=failed,
        skipped_tickers=skipped,
        row_count=row_count,
        provider_health_count=provider_health_count,
        outcomes=outcomes,
    )
    log_event(
        "ingestion_completed",
        service="scheduled_ingestion",
        watchlist_name=config.watchlist_name,
        provider=config.provider,
        interval=config.interval,
        status=summary.status,
        requested_count=len(summary.requested_tickers),
        succeeded_count=len(summary.succeeded_tickers),
        failed_count=len(summary.failed_tickers),
        skipped_count=len(summary.skipped_tickers),
        row_count=summary.row_count,
    )
    return summary


def run_scheduler(
    config: ScheduledIngestionConfig,
    *,
    run_once: Callable[[ScheduledIngestionConfig], ScheduledIngestionSummary] = run_scheduled_ingestion_once,
    sleep_fn: Callable[[float], None] = sleep,
) -> None:
    """Run indefinitely until interrupted; use ``--once`` in jobs and tests."""

    if not config.enabled:
        print(run_once(config).model_dump_json(indent=2))
        return
    while True:
        print(run_once(config).model_dump_json(indent=2))
        sleep_fn(config.poll_seconds)
