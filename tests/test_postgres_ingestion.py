from __future__ import annotations

import pandas as pd

from tsi.data.download import DownloadFrameResult, DownloadTicker
from tsi.data.postgres import (
    ResolvedTickerSchema,
    _resolve_prediction_record_ticker,
    _upsert_prediction_ticker,
    build_ingestion_summary,
    build_market_bar_rows,
    build_resolved_tickers,
    infer_market,
    validate_interval,
)


def test_infer_market_maps_provider_suffixes() -> None:
    assert infer_market("2330", "2330.TW") == "twse"
    assert infer_market("6488", "6488.TWO") == "tpex"
    assert infer_market("5240", "5240.EMERGING") == "emerging"
    assert infer_market("NVDA", "NVDA") == "us"


def test_prediction_record_resolver_maps_taiwan_alphanumeric_codes_to_twse() -> None:
    resolved = _resolve_prediction_record_ticker(EmptyTickerLookupConnection(), "00981A")

    assert resolved.symbol == "00981A"
    assert resolved.query_symbol == "00981A.TW"
    assert resolved.market == "twse"


def test_prediction_record_resolver_prefers_existing_emerging_ticker() -> None:
    resolved = _resolve_prediction_record_ticker(
        StaticTickerLookupConnection(("5240", "5240.EMERGING", "emerging")),
        "5240",
    )

    assert resolved.symbol == "5240"
    assert resolved.query_symbol == "5240.EMERGING"
    assert resolved.market == "emerging"


def test_prediction_ticker_upsert_merges_stale_taiwan_us_alias() -> None:
    connection = RecordingTickerMergeConnection(stale_rows=[("stale-us-id",)])

    ticker_id = _upsert_prediction_ticker(
        connection,
        ResolvedTickerSchema(symbol="00981A", query_symbol="00981A.TW", market="twse"),
    )

    assert ticker_id == "target-id"
    assert any("SELECT id" in query and "market = 'us'" in query for query, _ in connection.calls)
    assert ("DELETE FROM tickers WHERE id = %s", ("stale-us-id",)) in connection.normalized_calls


def test_prediction_ticker_upsert_does_not_merge_us_ticker_alias() -> None:
    connection = RecordingTickerMergeConnection(stale_rows=[("stale-us-id",)])

    ticker_id = _upsert_prediction_ticker(
        connection,
        ResolvedTickerSchema(symbol="AAPL", query_symbol="AAPL", market="us"),
    )

    assert ticker_id == "target-id"
    assert all("market = 'us'" not in query for query, _ in connection.calls)


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


def test_build_market_bar_rows_uses_resolved_emerging_market() -> None:
    result = DownloadFrameResult(
        dataset_name="watchlist",
        tickers=[DownloadTicker(ticker="5240", query_symbol="5240.EMERGING", market="emerging")],
        ohlcv=pd.DataFrame(
            {
                "date": ["2026-06-18"],
                "ticker": ["5240"],
                "open": [23.0],
                "high": [23.95],
                "low": [23.0],
                "close": [23.0],
                "adj_close": [23.0],
                "volume": [3001],
            }
        ),
        start="2026-06-01",
        end=None,
        interval="1d",
        failed_batches=[],
    )

    rows = build_market_bar_rows(result, provider="tpex")

    assert rows[0].market == "emerging"
    assert build_resolved_tickers(result)[0].market == "emerging"


class EmptyTickerLookupConnection:
    def execute(self, *_args, **_kwargs):
        return StaticTickerLookupCursor(None)


class StaticTickerLookupConnection:
    def __init__(self, row):
        self.row = row

    def execute(self, *_args, **_kwargs):
        return StaticTickerLookupCursor(self.row)


class StaticTickerLookupCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class RecordingTickerMergeConnection:
    def __init__(self, stale_rows):
        self.stale_rows = stale_rows
        self.calls = []
        self.normalized_calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        normalized_query = " ".join(query.split())
        self.normalized_calls.append((normalized_query, params))
        if normalized_query.startswith("INSERT INTO tickers"):
            return RecordingCursor(fetchone_row=("target-id",))
        if normalized_query.startswith("SELECT id FROM tickers"):
            return RecordingCursor(fetchall_rows=self.stale_rows)
        return RecordingCursor()


class RecordingCursor:
    def __init__(self, fetchone_row=None, fetchall_rows=None):
        self.fetchone_row = fetchone_row
        self.fetchall_rows = fetchall_rows or []

    def fetchone(self):
        return self.fetchone_row

    def fetchall(self):
        return self.fetchall_rows
