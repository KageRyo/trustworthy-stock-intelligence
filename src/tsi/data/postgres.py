"""PostgreSQL ingestion helpers for market data bars."""

from __future__ import annotations

import math
import json
from datetime import UTC, datetime
from typing import Any, Literal, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi.data.download import DownloadFrameResult, is_taiwan_local_ticker
from tsi.serving.schema import PredictionBatch

MarketBarInterval = Literal["1m", "5m", "1d"]
TickerMarketName = Literal["us", "twse", "tpex", "emerging", "taiwan", "unknown"]
IngestionStatus = Literal["success", "dry_run"]
INGESTION_SCHEMA_VERSION = "market_data_ingestion.v1"
PREDICTION_WRITE_SCHEMA_VERSION = "prediction_batch_write.v1"
SUPPORTED_INTERVALS: set[str] = {"1m", "5m", "1d"}
TAIWAN_MARKETS: set[str] = {"twse", "tpex", "emerging", "taiwan"}


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


class PredictionBatchWriteSummary(BaseModel):
    """Schema-first summary for writing a prediction batch into PostgreSQL."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PREDICTION_WRITE_SCHEMA_VERSION
    status: Literal["success"]
    run_id: str
    data_as_of: str
    generated_at: str
    feature_interval: MarketBarInterval
    record_count: int = Field(ge=0)
    tickers: list[str]
    prediction_batch_id: str


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
    if normalized_query.endswith(".EMERGING"):
        return "emerging"
    if is_taiwan_local_ticker(normalized_symbol):
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
            market=resolve_download_ticker_market(
                ticker.ticker,
                ticker.query_symbol,
                ticker.market,
            ),
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
                market=resolve_download_ticker_market(symbol, resolved.query_symbol, resolved.market),
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


def read_watchlist_tickers(database_url: str, watchlist_name: str = "default") -> list[str]:
    """Read active ticker symbols from a PostgreSQL watchlist."""

    with connect_database(database_url) as connection:
        rows = connection.execute(
            """
            SELECT t.symbol
            FROM watchlist_tickers wt
            JOIN watchlists w ON w.id = wt.watchlist_id
            JOIN tickers t ON t.id = wt.ticker_id
            WHERE w.name = %s AND wt.removed_at IS NULL
            ORDER BY t.symbol
            """,
            (watchlist_name,),
        ).fetchall()
    return [str(row[0]) for row in rows]


def write_prediction_batch_to_postgres(
    database_url: str,
    batch: PredictionBatch,
    *,
    feature_interval: str = "1d",
) -> PredictionBatchWriteSummary:
    """Upsert a serving prediction batch into PostgreSQL warning tables."""

    interval = validate_interval(feature_interval)
    model_name, model_bundle = _infer_batch_model_metadata(batch)
    data_as_of = _to_utc_datetime(batch.data_as_of or _infer_batch_record_date(batch))
    generated_at = _to_utc_datetime(batch.generated_at)

    with connect_database(database_url) as connection:
        with connection.transaction():
            batch_id = _upsert_prediction_batch(
                connection,
                batch=batch,
                data_as_of=data_as_of,
                generated_at=generated_at,
                model_name=model_name,
                model_bundle=model_bundle,
                feature_interval=interval,
            )
            connection.execute("DELETE FROM warning_records WHERE batch_id = %s", (batch_id,))
            for record in batch.records:
                resolved = _resolve_prediction_record_ticker(connection, record.ticker)
                ticker_id = _upsert_prediction_ticker(connection, resolved)
                connection.execute(
                    """
                    INSERT INTO warning_records (
                        batch_id, ticker_id, prediction_date, risk_probability,
                        calibrated_risk_probability, calibration_method,
                        uncertainty_score, trust_score, alert_threshold,
                        watch_threshold, warning_level, reason_codes, feature_attributions
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (batch_id, ticker_id)
                    DO UPDATE SET
                        prediction_date = EXCLUDED.prediction_date,
                        risk_probability = EXCLUDED.risk_probability,
                        calibrated_risk_probability = EXCLUDED.calibrated_risk_probability,
                        calibration_method = EXCLUDED.calibration_method,
                        uncertainty_score = EXCLUDED.uncertainty_score,
                        trust_score = EXCLUDED.trust_score,
                        alert_threshold = EXCLUDED.alert_threshold,
                        watch_threshold = EXCLUDED.watch_threshold,
                        warning_level = EXCLUDED.warning_level,
                        reason_codes = EXCLUDED.reason_codes,
                        feature_attributions = EXCLUDED.feature_attributions
                    """,
                    (
                        batch_id,
                        ticker_id,
                        _to_utc_datetime(record.date),
                        record.risk_probability,
                        record.calibrated_risk_probability,
                        record.calibration_method,
                        record.uncertainty_score,
                        record.trust_score,
                        record.alert_threshold,
                        record.watch_threshold,
                        record.warning_level,
                        record.reason_codes,
                        json.dumps(
                            [item.model_dump(mode="json") for item in record.feature_attributions],
                            separators=(",", ":"),
                        ),
                    ),
                )
        connection.commit()

    return PredictionBatchWriteSummary(
        status="success",
        run_id=batch.run_id,
        data_as_of=data_as_of.isoformat(),
        generated_at=generated_at.isoformat(),
        feature_interval=interval,
        record_count=len(batch.records),
        tickers=sorted({record.ticker for record in batch.records}),
        prediction_batch_id=batch_id,
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


def _infer_batch_model_metadata(batch: PredictionBatch) -> tuple[str, str]:
    if not batch.records:
        return "unknown", "unknown"
    first = batch.records[0]
    return first.model, first.model_bundle


def _infer_batch_record_date(batch: PredictionBatch) -> str:
    if not batch.records:
        return datetime.now(UTC).date().isoformat()
    return max(record.date for record in batch.records)


def resolve_download_ticker_market(
    symbol: str,
    query_symbol: str,
    market: str,
) -> TickerMarketName:
    """Resolve downloaded ticker market, preferring schema metadata over suffix guesses."""

    if market in {"us", "twse", "tpex", "emerging", "taiwan"}:
        return cast(TickerMarketName, market)
    return infer_market(symbol, query_symbol)


def _resolve_prediction_record_ticker(connection: Any, ticker: str) -> ResolvedTickerSchema:
    symbol = ticker.strip().upper()
    if is_taiwan_local_ticker(symbol):
        existing = _lookup_existing_taiwan_ticker(connection, symbol)
        if existing is not None:
            return existing
        return ResolvedTickerSchema(symbol=symbol, query_symbol=f"{symbol}.TW", market="twse")
    return ResolvedTickerSchema(
        symbol=symbol.replace(".", "-"),
        query_symbol=symbol.replace(".", "-"),
        market="us",
    )


def _lookup_existing_taiwan_ticker(connection: Any, symbol: str) -> ResolvedTickerSchema | None:
    row = connection.execute(
        """
        SELECT symbol, query_symbol, market
        FROM tickers
        WHERE upper(symbol) = upper(%s)
          AND market IN ('twse', 'tpex', 'emerging', 'taiwan')
        ORDER BY
          updated_at DESC,
          CASE market
            WHEN 'twse' THEN 1
            WHEN 'tpex' THEN 2
            WHEN 'emerging' THEN 3
            WHEN 'taiwan' THEN 4
            ELSE 5
          END
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    if row is None:
        return None
    return ResolvedTickerSchema(symbol=str(row[0]), query_symbol=str(row[1]), market=str(row[2]))


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
        ticker_id = str(cursor.fetchone()[0])
        _merge_stale_us_ticker_alias(connection, ticker, ticker_id)
        ticker_ids[(ticker.market, ticker.symbol)] = ticker_id
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


def _upsert_prediction_batch(
    connection: Any,
    *,
    batch: PredictionBatch,
    data_as_of: datetime,
    generated_at: datetime,
    model_name: str,
    model_bundle: str,
    feature_interval: MarketBarInterval,
) -> str:
    from psycopg.types.json import Jsonb

    cursor = connection.execute(
        """
        INSERT INTO prediction_batches (
            schema_version, run_id, data_as_of, generated_at, model,
            model_bundle, feature_interval, record_count, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id)
        DO UPDATE SET
            schema_version = EXCLUDED.schema_version,
            data_as_of = EXCLUDED.data_as_of,
            generated_at = EXCLUDED.generated_at,
            model = EXCLUDED.model,
            model_bundle = EXCLUDED.model_bundle,
            feature_interval = EXCLUDED.feature_interval,
            record_count = EXCLUDED.record_count,
            metadata = EXCLUDED.metadata
        RETURNING id
        """,
        (
            batch.schema_version,
            batch.run_id,
            data_as_of,
            generated_at,
            model_name,
            model_bundle,
            feature_interval,
            len(batch.records),
            Jsonb({"source_schema": batch.schema_version}),
        ),
    )
    return str(cursor.fetchone()[0])


def _upsert_prediction_ticker(connection: Any, ticker: ResolvedTickerSchema) -> str:
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
    ticker_id = str(cursor.fetchone()[0])
    _merge_stale_us_ticker_alias(connection, ticker, ticker_id)
    return ticker_id


def _should_merge_stale_us_ticker_alias(ticker: ResolvedTickerSchema) -> bool:
    return ticker.market in TAIWAN_MARKETS and is_taiwan_local_ticker(ticker.symbol)


def _merge_stale_us_ticker_alias(
    connection: Any,
    ticker: ResolvedTickerSchema,
    target_ticker_id: str,
) -> None:
    """Move references from stale US rows created before Taiwan-code detection existed."""

    if not _should_merge_stale_us_ticker_alias(ticker):
        return

    stale_rows = connection.execute(
        """
        SELECT id
        FROM tickers
        WHERE upper(symbol) = upper(%s)
          AND market = 'us'
          AND id <> %s
        """,
        (ticker.symbol, target_ticker_id),
    ).fetchall()
    for row in stale_rows:
        stale_ticker_id = str(row[0])
        _move_universe_ticker_references(connection, stale_ticker_id, target_ticker_id)
        _move_watchlist_ticker_references(connection, stale_ticker_id, target_ticker_id)
        _move_market_bar_references(connection, stale_ticker_id, target_ticker_id)
        _move_warning_record_references(connection, stale_ticker_id, target_ticker_id)
        connection.execute("DELETE FROM tickers WHERE id = %s", (stale_ticker_id,))


def _move_universe_ticker_references(
    connection: Any,
    stale_ticker_id: str,
    target_ticker_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO universe_tickers (universe_id, ticker_id, added_at, removed_at)
        SELECT universe_id, %s, added_at, removed_at
        FROM universe_tickers
        WHERE ticker_id = %s
        ON CONFLICT (universe_id, ticker_id)
        DO UPDATE SET
            added_at = LEAST(universe_tickers.added_at, EXCLUDED.added_at),
            removed_at = CASE
                WHEN universe_tickers.removed_at IS NULL OR EXCLUDED.removed_at IS NULL THEN NULL
                ELSE LEAST(universe_tickers.removed_at, EXCLUDED.removed_at)
            END
        """,
        (target_ticker_id, stale_ticker_id),
    )
    connection.execute("DELETE FROM universe_tickers WHERE ticker_id = %s", (stale_ticker_id,))


def _move_watchlist_ticker_references(
    connection: Any,
    stale_ticker_id: str,
    target_ticker_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO watchlist_tickers (watchlist_id, ticker_id, added_at, removed_at, notes)
        SELECT watchlist_id, %s, added_at, removed_at, notes
        FROM watchlist_tickers
        WHERE ticker_id = %s
        ON CONFLICT (watchlist_id, ticker_id)
        DO UPDATE SET
            added_at = LEAST(watchlist_tickers.added_at, EXCLUDED.added_at),
            removed_at = CASE
                WHEN watchlist_tickers.removed_at IS NULL OR EXCLUDED.removed_at IS NULL THEN NULL
                ELSE LEAST(watchlist_tickers.removed_at, EXCLUDED.removed_at)
            END,
            notes = CASE
                WHEN watchlist_tickers.notes = '' THEN EXCLUDED.notes
                ELSE watchlist_tickers.notes
            END
        """,
        (target_ticker_id, stale_ticker_id),
    )
    connection.execute("DELETE FROM watchlist_tickers WHERE ticker_id = %s", (stale_ticker_id,))


def _move_market_bar_references(
    connection: Any,
    stale_ticker_id: str,
    target_ticker_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO market_bars (
            ticker_id, ts, interval, provider, open, high, low, close,
            adj_close, volume, ingestion_run_id, created_at
        )
        SELECT
            %s, ts, interval, provider, open, high, low, close,
            adj_close, volume, ingestion_run_id, created_at
        FROM market_bars
        WHERE ticker_id = %s
        ON CONFLICT (ticker_id, interval, ts, provider)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume,
            ingestion_run_id = COALESCE(EXCLUDED.ingestion_run_id, market_bars.ingestion_run_id)
        """,
        (target_ticker_id, stale_ticker_id),
    )
    connection.execute("DELETE FROM market_bars WHERE ticker_id = %s", (stale_ticker_id,))


def _move_warning_record_references(
    connection: Any,
    stale_ticker_id: str,
    target_ticker_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO warning_records (
            batch_id, ticker_id, prediction_date, risk_probability,
            calibrated_risk_probability, calibration_method,
            uncertainty_score, trust_score, alert_threshold,
            watch_threshold, warning_level, reason_codes, created_at
        )
        SELECT
            batch_id, %s, prediction_date, risk_probability,
            calibrated_risk_probability, calibration_method,
            uncertainty_score, trust_score, alert_threshold,
            watch_threshold, warning_level, reason_codes, created_at
        FROM warning_records
        WHERE ticker_id = %s
        ON CONFLICT (batch_id, ticker_id)
        DO UPDATE SET
            prediction_date = EXCLUDED.prediction_date,
            risk_probability = EXCLUDED.risk_probability,
            calibrated_risk_probability = EXCLUDED.calibrated_risk_probability,
            calibration_method = EXCLUDED.calibration_method,
            uncertainty_score = EXCLUDED.uncertainty_score,
            trust_score = EXCLUDED.trust_score,
            alert_threshold = EXCLUDED.alert_threshold,
            watch_threshold = EXCLUDED.watch_threshold,
            warning_level = EXCLUDED.warning_level,
            reason_codes = EXCLUDED.reason_codes
        """,
        (target_ticker_id, stale_ticker_id),
    )
    connection.execute("DELETE FROM warning_records WHERE ticker_id = %s", (stale_ticker_id,))
