from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from tsi.data.download import DownloadFrameResult, DownloadTicker, DownloadUnavailableError
from tsi.data.provider_health import ProviderHealthSnapshot
from tsi.data.scheduled_ingestion import (
    ScheduledIngestionConfig,
    run_scheduled_ingestion_once,
    run_scheduler,
)


def _health_snapshot(ticker: str, *, status: str = "healthy") -> ProviderHealthSnapshot:
    return ProviderHealthSnapshot(
        provider="yfinance",
        market="us",
        ticker=ticker,
        query_symbol=ticker,
        status=status,
        coverage="available" if status == "healthy" else "unavailable",
        attempt_count=1,
        success_count=1 if status == "healthy" else 0,
        failure_count=0 if status == "healthy" else 1,
        consecutive_failures=0 if status == "healthy" else 1,
        last_success_at=datetime(2026, 8, 13, tzinfo=UTC) if status == "healthy" else None,
        last_failure_at=None if status == "healthy" else datetime(2026, 8, 13, tzinfo=UTC),
        last_error_code="" if status == "healthy" else "provider_error",
        last_error_message="" if status == "healthy" else "provider unavailable",
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
    )


def _download_result(ticker: str) -> DownloadFrameResult:
    return DownloadFrameResult(
        dataset_name="watchlist",
        tickers=[DownloadTicker(ticker=ticker, query_symbol=ticker, market="us")],
        ohlcv=pd.DataFrame(
            {
                "date": ["2026-08-13T01:00:00Z"],
                "ticker": [ticker],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "adj_close": [100.5],
                "volume": [1000.0],
            }
        ),
        start="2026-08-13",
        end=None,
        interval="5m",
        failed_batches=[],
        provider_health=[_health_snapshot(ticker)],
    )


def test_scheduled_ingestion_isolates_tickers_and_persists_failed_health() -> None:
    config = ScheduledIngestionConfig(
        enabled=True,
        database_url="postgresql://test",
        watchlist_name="session-test",
    )
    download_calls: list[str] = []
    writes: list[str] = []
    health_writes: list[list[ProviderHealthSnapshot]] = []

    def fake_download(**kwargs):
        ticker = kwargs["tickers"][0]
        download_calls.append(ticker)
        if ticker == "2330":
            raise DownloadUnavailableError(
                "No rows for 2330",
                provider_health=[_health_snapshot(ticker, status="unavailable")],
            )
        return _download_result(ticker)

    def fake_write(_database_url, result, **_kwargs):
        writes.append(result.tickers[0].ticker)
        return SimpleNamespace(ingestion_run_id=f"run-{result.tickers[0].ticker}")

    def fake_health_write(_database_url, snapshots):
        health_writes.append(snapshots)
        return len(snapshots)

    summary = run_scheduled_ingestion_once(
        config,
        read_watchlist=lambda _database_url, _name: ["NVDA", "2330", "NVDA", "  "],
        download=fake_download,
        write_download=fake_write,
        write_provider_health=fake_health_write,
        started_at=datetime(2026, 8, 13, tzinfo=UTC),
    )

    assert summary.status == "partial"
    assert summary.requested_tickers == ["NVDA", "2330"]
    assert summary.succeeded_tickers == ["NVDA"]
    assert summary.failed_tickers == ["2330"]
    assert summary.skipped_tickers == []
    assert summary.row_count == 1
    assert summary.provider_health_count == 2
    assert download_calls == ["NVDA", "2330"]
    assert writes == ["NVDA"]
    assert len(health_writes) == 1
    assert health_writes[0][0].ticker == "2330"
    assert summary.outcomes[0].ingestion_run_id == "run-NVDA"
    assert summary.outcomes[1].error_code == "provider_unavailable"


def test_disabled_schedule_does_not_read_database() -> None:
    called = False

    def fail_if_read(*_args):
        nonlocal called
        called = True
        raise AssertionError("disabled schedule must not read the database")

    summary = run_scheduled_ingestion_once(
        ScheduledIngestionConfig(enabled=False),
        read_watchlist=fail_if_read,
    )

    assert summary.status == "disabled"
    assert summary.enabled is False
    assert summary.skipped_tickers == []
    assert called is False


def test_scheduler_prints_once_for_disabled_config(capsys) -> None:
    run_scheduler(ScheduledIngestionConfig(enabled=False))

    assert '"status": "disabled"' in capsys.readouterr().out


def test_scheduler_uses_latest_bar_cursor_and_skips_current_ticker() -> None:
    config = ScheduledIngestionConfig(enabled=True, database_url="postgresql://test")
    download_calls: list[str] = []

    def fake_download(**kwargs):
        download_calls.append(kwargs["tickers"][0])
        return _download_result(kwargs["tickers"][0])

    summary = run_scheduled_ingestion_once(
        config,
        read_watchlist=lambda _database_url, _name: ["NVDA", "AAPL"],
        read_latest_bar=lambda _database_url, ticker, **_kwargs: (
            datetime(2026, 8, 13, 0, 0, tzinfo=UTC) if ticker == "NVDA" else None
        ),
        download=fake_download,
        write_download=lambda *_args, **_kwargs: SimpleNamespace(ingestion_run_id="run-AAPL"),
        started_at=datetime(2026, 8, 13, 0, 4, tzinfo=UTC),
    )

    assert summary.status == "success"
    assert summary.skipped_tickers == ["NVDA"]
    assert summary.succeeded_tickers == ["AAPL"]
    assert download_calls == ["AAPL"]
