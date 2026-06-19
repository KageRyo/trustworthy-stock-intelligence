"""PostgreSQL ingestion helpers for market data bars."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi.data.download import DownloadFrameResult

MarketBarInterval = Literal["1m", "5m", "1d"]
TickerMarketName = Literal["us", "twse", "tpex", "taiwan", "unknown"]
IngestionStatus = Literal["success", "dry_run"]
INGESTION_SCHEMA_VERSION = "market_data_ingestion.v1"
SUPPORTED_INTERVALS: set[str] = {"1m", "5m", "1d"}


class ResolvedTickerSchema(BaseModel):
    """Provider-resolved ticker metadata stored before market bars."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    query_symbol: str
    market: TickerMarketName


class MarketBarRow(BaseModel):
    """One validated market bar ready for PostgreSQL insertion."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    query_symbol: str
    market: TickerMarketName
    ts: datetime
    interval: MarketBarInterval
    provider: str
    open: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    low: float = Field(ge=0.0)
    close: float = Field(ge=0.0)
    adj_close: float | None = Field(default=None, ge=0.0)
    volume: float = Field(ge=0.0)


class MarketDataIngestionSummary(BaseModel):
    """Schema-first CLI/API-style summary for a market-data ingestion run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = INGESTION_SCHEMA_VERSION
    status: IngestionStatus
    provider: str
    interval: MarketBarInterval
    universe_name: str
    start: str
    end: str | None
    data_start: str | None
    data_end: str | None
    requested_tickers: list[str]
    resolved_tickers: list[ResolvedTickerSchema]
    downloaded_tickers: list[str]
    row_count: int = Field(ge=0)
    failed_batches: list[list[str]]
    database_write: bool
    ingestion_run_id: str | None = None


def validate_interval(interval: str) -> MarketBarInterval:
    """Validate a bar interval supported by the database schema."""

    if interval not in SUPPORTED_INTERVALS:
        raise ValueError("interval must be one of 1m, 5m, 1d")
    return cast(MarketBarInterval, interval)


def infer_market(symbol: str, query_symbol: str) -> TickerMarketName:
    """Infer the database market enum from user and provider symbols."""

    normalized_symbol = symbol.strip().upper()
    normalized_query = query_symbol.strip().upper()
    if normalized_query.endswith(".TW"):
        return "twse"
    if normalized_query.endswith(".TWO"):
        return "tpex"
    if normalized_symbol.isdigit():
        return "taiwan"
    if normalized_symbol:
        return "us"
    return "unknown"


def build_resolved_tickers(result: DownloadFrameResult) -> list[ResolvedTickerSchema]:
    """Build schema-validated ticker metadata from a download result."""

    return [
        ResolvedTickerSchema(
            symbol=ticker.ticker,
            query_symbol=ticker.query_symbol,
            market=infer_market(ticker.ticker, ticker.query_symbol),
        )
        for ticker in result.tickers
    ]


def build_market_bar_rows(
    result: DownloadFrameResult,
    *,
    provider: str = "yfinance",
) -> list[MarketBarRow]:
    """Convert a normalized OHLCV frame into validated PostgreSQL bar rows."""

    interval = validate_interval(result.interval)
    required_columns = {"date", "ticker", "open", "high", "low", "close", "adj_close", "volume"}
    missing = sorted(required_columns.difference(result.ohlcv.columns))
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {', '.join(missing)}")

    resolved_by_symbol = {ticker.ticker: ticker for ticker in result.tickers}
    rows: list[MarketBarRow] = []
    for _, frame_row in result.ohlcv.iterrows():
        symbol = str(frame_row["ticker"])
        resolved = resolved_by_symbol.get(symbol)
        if resolved is None:
            raise ValueError(f"Downloaded row has unknown ticker: {symbol}")
        rows.append(
            MarketBarRow(
                symbol=symbol,
                query_symbol=resolved.query_symbol,
                market=infer_market(symbol, resolved.query_symbol),
                ts=_to_utc_datetime(frame_row["date"]),
                interval=interval,
                provider=provider,
                open=_finite_float(frame_row["open"], "open"),
                high=_finite_float(frame_row["high"], "high"),
                low=_finite_float(frame_row["low"], "low"),
                close=_finite_float(frame_row["close"], "close"),
                adj_close=_nullable_finite_float(frame_row["adj_close"], "adj_close"),
                volume=_finite_float(frame_row["volume"], "volume"),
            )
        )
    return rows


def build_ingestion_summary(
    result: DownloadFrameResult,
    rows: list[MarketBarRow],
    *,
    provider: str = "yfinance",
    universe_name: str = "watchlist",
    status: IngestionStatus = "success",
    database_write: bool = True,
    ingestion_run_id: str | None = None,
) -> MarketDataIngestionSummary:
    """Build a schema-validated ingestion summary."""

    timestamps = sorted(row.ts for row in rows)
    return MarketDataIngestionSummary(
        status=status,
        provider=provider,
        interval=validate_interval(result.interval),
        universe_name=universe_name,
        start=result.start,
        end=result.end,
        data_start=timestamps[0].isoformat() if timestamps else None,
        data_end=timestamps[-1].isoformat() if timestamps else None,
        requested_tickers=[ticker.ticker for ticker in result.tickers],
        resolved_tickers=build_resolved_tickers(result),
        downloaded_tickers=sorted({row.symbol for row in rows}),
        row_count=len(rows),
        failed_batches=result.failed_batches,
        database_write=database_write,
        ingestion_run_id=ingestion_run_id,
    )


def write_download_to_postgres(
    database_url: str,
    result: DownloadFrameResult,
    *,
    provider: str = "yfinance",
    universe_name: str = "watchlist",
) -> MarketDataIngestionSummary:
    """Upsert a downloaded OHLCV frame into PostgreSQL."""

    rows = build_market_bar_rows(result, provider=provider)
    resolved_tickers = build_resolved_tickers(result)
    downloaded_symbols = sorted({row.symbol for row in rows})

    with connect_database(database_url) as connection:
        ingestion_run_id = _create_ingestion_run(
            connection,
            provider=provider,
            universe_name=universe_name,
            interval=validate_interval(result.interval),
            requested_symbols=[ticker.ticker for ticker in result.tickers],
        )
        connection.commit()
        try:
            with connection.transaction():
                universe_id = _upsert_universe(connection, universe_name)
                ticker_ids = _upsert_tickers(connection, resolved_tickers)
                _attach_universe_tickers(connection, universe_id, ticker_ids)
                _upsert_market_bars(connection, rows, ticker_ids, ingestion_run_id)
            _mark_ingestion_success(connection, ingestion_run_id, downloaded_symbols)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            _mark_ingestion_failed(connection, ingestion_run_id, str(exc))
            connection.commit()
            raise

    return build_ingestion_summary(
        result,
        rows,
        provider=provider,
        universe_name=universe_name,
        status="success",
        database_write=True,
        ingestion_run_id=ingestion_run_id,
    )


def connect_database(database_url: str) -> Any:
    """Connect to PostgreSQL using psycopg, loaded only for DB workflows."""

    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PostgreSQL ingestion requires psycopg. Install with: "
            "python -m pip install -e '.[db]'"
        ) from exc
    return psycopg.connect(database_url)


def _to_utc_datetime(value: object) -> datetime:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("date must not be null")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.to_pydatetime()


def _finite_float(value: object, column: str) -> float:
    if pd.isna(value):
        raise ValueError(f"{column} must not be null")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{column} must be finite")
    return numeric


def _nullable_finite_float(value: object, column: str) -> float | None:
    if pd.isna(value):
        return None
    return _finite_float(value, column)


def _create_ingestion_run(
    connection: Any,
    *,
    provider: str,
    universe_name: str,
    interval: MarketBarInterval,
    requested_symbols: list[str],
) -> str:
    cursor = connection.execute(
        """
        INSERT INTO ingestion_runs (
            provider, universe_name, interval, status, requested_symbols
        )
        VALUES (%s, %s, %s, 'running', %s)
        RETURNING id
        """,
        (provider, universe_name, interval, requested_symbols),
    )
    return str(cursor.fetchone()[0])


def _upsert_universe(connection: Any, universe_name: str) -> str:
    cursor = connection.execute(
        """
        INSERT INTO universes (name, description)
        VALUES (%s, %s)
        ON CONFLICT (name)
        DO UPDATE SET updated_at = now()
        RETURNING id
        """,
        (universe_name, "Ingested market-data universe"),
    )
    return str(cursor.fetchone()[0])


def _upsert_tickers(
    connection: Any,
    resolved_tickers: list[ResolvedTickerSchema],
) -> dict[tuple[str, str], str]:
    ticker_ids: dict[tuple[str, str], str] = {}
    for ticker in resolved_tickers:
        cursor = connection.execute(
            """
            INSERT INTO tickers (symbol, query_symbol, market)
            VALUES (%s, %s, %s)
            ON CONFLICT (market, symbol)
            DO UPDATE SET query_symbol = EXCLUDED.query_symbol, updated_at = now()
            RETURNING id
            """,
            (ticker.symbol, ticker.query_symbol, ticker.market),
        )
        ticker_ids[(ticker.market, ticker.symbol)] = str(cursor.fetchone()[0])
    return ticker_ids


def _attach_universe_tickers(
    connection: Any,
    universe_id: str,
    ticker_ids: dict[tuple[str, str], str],
) -> None:
    for ticker_id in ticker_ids.values():
        connection.execute(
            """
            INSERT INTO universe_tickers (universe_id, ticker_id)
            VALUES (%s, %s)
            ON CONFLICT (universe_id, ticker_id)
            DO UPDATE SET removed_at = NULL
            """,
            (universe_id, ticker_id),
        )


def _upsert_market_bars(
    connection: Any,
    rows: list[MarketBarRow],
    ticker_ids: dict[tuple[str, str], str],
    ingestion_run_id: str,
) -> None:
    for row in rows:
        ticker_id = ticker_ids[(row.market, row.symbol)]
        connection.execute(
            """
            INSERT INTO market_bars (
                ticker_id, ts, interval, provider, open, high, low, close,
                adj_close, volume, ingestion_run_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker_id, interval, ts, provider)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                adj_close = EXCLUDED.adj_close,
                volume = EXCLUDED.volume,
                ingestion_run_id = EXCLUDED.ingestion_run_id
            """,
            (
                ticker_id,
                row.ts,
                row.interval,
                row.provider,
                row.open,
                row.high,
                row.low,
                row.close,
                row.adj_close,
                row.volume,
                ingestion_run_id,
            ),
        )


def _mark_ingestion_success(
    connection: Any,
    ingestion_run_id: str,
    downloaded_symbols: list[str],
) -> None:
    connection.execute(
        """
        UPDATE ingestion_runs
        SET completed_at = now(), status = 'success', downloaded_symbols = %s
        WHERE id = %s
        """,
        (downloaded_symbols, ingestion_run_id),
    )


def _mark_ingestion_failed(connection: Any, ingestion_run_id: str, error_message: str) -> None:
    connection.execute(
        """
        UPDATE ingestion_runs
        SET completed_at = now(), status = 'failed', error_message = %s
        WHERE id = %s
        """,
        (error_message[:2000], ingestion_run_id),
    )
