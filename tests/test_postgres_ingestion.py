from __future__ import annotations

import pandas as pd

from tsi.data.download import DownloadFrameResult, DownloadTicker
from tsi.data.postgres import (
    build_ingestion_summary,
    build_market_bar_rows,
    build_resolved_tickers,
    infer_market,
    validate_interval,
)


def test_infer_market_maps_provider_suffixes() -> None:
    assert infer_market("2330", "2330.TW") == "twse"
    assert infer_market("6488", "6488.TWO") == "tpex"
    assert infer_market("NVDA", "NVDA") == "us"


def test_validate_interval_accepts_database_supported_intervals() -> None:
    assert validate_interval("1m") == "1m"
    assert validate_interval("5m") == "5m"
    assert validate_interval("1d") == "1d"


def test_build_market_bar_rows_validates_taiwan_5m_rows() -> None:
    result = DownloadFrameResult(
        dataset_name="watchlist",
        tickers=[DownloadTicker(ticker="2330", query_symbol="2330.TW")],
        ohlcv=pd.DataFrame(
            {
                "date": ["2026-06-18T01:00:00Z"],
                "ticker": ["2330"],
                "open": [100.0],
                "high": [103.0],
                "low": [99.0],
                "close": [102.0],
                "adj_close": [102.0],
                "volume": [1000],
            }
        ),
        start="2026-06-18",
        end=None,
        interval="5m",
        failed_batches=[],
    )

    rows = build_market_bar_rows(result, provider="yfinance")

    assert len(rows) == 1
    assert rows[0].symbol == "2330"
    assert rows[0].query_symbol == "2330.TW"
    assert rows[0].market == "twse"
    assert rows[0].interval == "5m"
    assert rows[0].provider == "yfinance"
    assert rows[0].ts.isoformat() == "2026-06-18T01:00:00+00:00"


def test_build_ingestion_summary_is_schema_first() -> None:
    result = DownloadFrameResult(
        dataset_name="watchlist",
        tickers=[
            DownloadTicker(ticker="NVDA", query_symbol="NVDA"),
            DownloadTicker(ticker="2330", query_symbol="2330.TW"),
        ],
        ohlcv=pd.DataFrame(
            {
                "date": ["2026-06-18T01:00:00Z", "2026-06-18T01:05:00Z"],
                "ticker": ["NVDA", "2330"],
                "open": [100.0, 200.0],
                "high": [103.0, 203.0],
                "low": [99.0, 199.0],
                "close": [102.0, 202.0],
                "adj_close": [102.0, 202.0],
                "volume": [1000, 2000],
            }
        ),
        start="2026-06-18",
        end=None,
        interval="5m",
        failed_batches=[],
    )

    rows = build_market_bar_rows(result, provider="yfinance")
    summary = build_ingestion_summary(
        result,
        rows,
        provider="yfinance",
        universe_name="watchlist",
        status="dry_run",
        database_write=False,
    )

    assert summary.schema_version == "market_data_ingestion.v1"
    assert summary.status == "dry_run"
    assert summary.database_write is False
    assert summary.downloaded_tickers == ["2330", "NVDA"]
    assert summary.row_count == 2
    assert summary.data_start == "2026-06-18T01:00:00+00:00"
    assert summary.data_end == "2026-06-18T01:05:00+00:00"
    assert build_resolved_tickers(result)[1].market == "twse"
