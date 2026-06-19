"""Pilot OHLCV downloader for Yahoo Finance.

Yahoo Finance is used for early pipeline validation only. Formal research
should prefer a licensed and versioned market data source.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd
import yfinance as yf

from tsi.data.universe import Universe, UniverseName, load_universe

OHLCV_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
TickerMarket = Literal["auto", "us", "twse", "tpex"]


@dataclass(frozen=True)
class DownloadResult:
    """Paths and counts produced by a universe download."""

    universe: str
    ticker_count: int
    row_count: int
    start: str
    end: str | None
    output_dir: str
    ohlcv_path: str
    tickers_path: str
    metadata_path: str


@dataclass(frozen=True)
class DownloadTicker:
    """A display ticker and its provider query symbol."""

    ticker: str
    query_symbol: str


@dataclass(frozen=True)
class DownloadFrameResult:
    """Downloaded OHLCV frame and provider symbol metadata."""

    dataset_name: str
    tickers: list[DownloadTicker]
    ohlcv: pd.DataFrame
    start: str
    end: str | None
    interval: str
    failed_batches: list[list[str]]


def batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    """Yield fixed-size batches."""

    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def resolve_yfinance_ticker(ticker: str, *, market: TickerMarket = "auto") -> DownloadTicker:
    """Resolve an input ticker to a yfinance query symbol.

    Taiwan listed stocks use numeric local codes in the dashboard, while
    yfinance expects exchange suffixes such as ``.TW`` or ``.TWO``.
    """

    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")

    if market == "auto":
        if normalized.isdigit():
            return DownloadTicker(ticker=normalized, query_symbol=f"{normalized}.TW")
        return DownloadTicker(ticker=normalize_yfinance_symbol(normalized), query_symbol=normalized)
    if market == "us":
        symbol = normalize_yfinance_symbol(normalized)
        return DownloadTicker(ticker=symbol, query_symbol=symbol)
    if market == "twse":
        numeric = normalized.removesuffix(".TW")
        if not numeric.isdigit():
            raise ValueError("twse market requires a numeric Taiwan stock code")
        return DownloadTicker(ticker=numeric, query_symbol=f"{numeric}.TW")
    if market == "tpex":
        numeric = normalized.removesuffix(".TWO")
        if not numeric.isdigit():
            raise ValueError("tpex market requires a numeric Taiwan stock code")
        return DownloadTicker(ticker=numeric, query_symbol=f"{numeric}.TWO")
    raise ValueError(f"Unsupported market: {market}")


def normalize_yfinance_symbol(ticker: str) -> str:
    """Convert common stock symbols to Yahoo Finance query format."""

    return ticker.strip().upper().replace(".", "-")


def _normalize_download_frame(
    raw: pd.DataFrame,
    tickers: list[str],
    ticker_aliases: dict[str, str] | None = None,
    *,
    preserve_timestamp: bool = False,
) -> pd.DataFrame:
    """Convert yfinance output into a tidy OHLCV table."""

    if raw.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    aliases = ticker_aliases or {}
    frames: list[pd.DataFrame] = []
    if isinstance(raw.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            ticker_frame = raw[ticker].copy()
            ticker_frame["ticker"] = aliases.get(ticker, ticker)
            frames.append(ticker_frame)
    else:
        ticker_frame = raw.copy()
        ticker_frame["ticker"] = aliases.get(tickers[0], tickers[0])
        frames.append(ticker_frame)

    if not frames:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    data = pd.concat(frames).reset_index()
    data = data.rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    if preserve_timestamp:
        timestamps = pd.to_datetime(data["date"], utc=True)
        data["date"] = timestamps.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        data["date"] = pd.to_datetime(data["date"]).dt.date.astype(str)

    if "adj_close" not in data.columns and "close" in data.columns:
        data["adj_close"] = data["close"]
    elif "adj_close" in data.columns and "close" in data.columns:
        data["adj_close"] = data["adj_close"].fillna(data["close"])

    for column in OHLCV_COLUMNS:
        if column not in data.columns:
            data[column] = pd.NA

    data = data[OHLCV_COLUMNS]
    data = data.dropna(
        subset=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    )
    data = data.sort_values(["ticker", "date"]).reset_index(drop=True)
    return data


def download_ohlcv(
    universe: Universe,
    output_root: Path,
    start: str,
    end: str | None = None,
    batch_size: int = 80,
) -> DownloadResult:
    """Download daily OHLCV data for a universe and write local CSV artifacts."""

    output_dir = output_root / universe.name
    output_dir.mkdir(parents=True, exist_ok=True)

    all_frames: list[pd.DataFrame] = []
    failed_batches: list[list[str]] = []

    for ticker_batch in batched(universe.tickers, batch_size):
        raw = yf.download(
            tickers=ticker_batch,
            start=start,
            end=end,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            threads=True,
            progress=False,
        )
        normalized = _normalize_download_frame(raw, ticker_batch)
        if normalized.empty:
            failed_batches.append(ticker_batch)
        else:
            all_frames.append(normalized)

    if not all_frames:
        raise RuntimeError(f"No OHLCV rows downloaded for universe {universe.name}.")

    ohlcv = pd.concat(all_frames, ignore_index=True)
    ohlcv = ohlcv.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])

    ohlcv_path = output_dir / "ohlcv.csv"
    tickers_path = output_dir / "tickers.csv"
    metadata_path = output_dir / "metadata.json"

    ohlcv.to_csv(ohlcv_path, index=False)
    pd.DataFrame({"ticker": universe.tickers}).to_csv(tickers_path, index=False)

    metadata = {
        "universe": universe.name,
        "source": "Yahoo Finance via yfinance",
        "universe_source_url": universe.source_url,
        "downloaded_at_utc": datetime.now(UTC).isoformat(),
        "start": start,
        "end": end,
        "ticker_count": len(universe.tickers),
        "downloaded_ticker_count": int(ohlcv["ticker"].nunique()),
        "row_count": int(len(ohlcv)),
        "columns": OHLCV_COLUMNS,
        "failed_batches": failed_batches,
        "research_note": "Yahoo Finance is used for pilot experiments only.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return DownloadResult(
        universe=universe.name,
        ticker_count=len(universe.tickers),
        row_count=len(ohlcv),
        start=start,
        end=end,
        output_dir=str(output_dir),
        ohlcv_path=str(ohlcv_path),
        tickers_path=str(tickers_path),
        metadata_path=str(metadata_path),
    )


def download_ticker_list(
    tickers: list[str],
    output_dir: Path,
    start: str,
    end: str | None = None,
    *,
    market: TickerMarket = "auto",
    interval: str = "1d",
    batch_size: int = 80,
    dataset_name: str = "custom",
) -> DownloadResult:
    """Download daily OHLCV data for explicit ticker inputs."""

    result = download_ticker_frame(
        tickers=tickers,
        start=start,
        end=end,
        market=market,
        interval=interval,
        batch_size=batch_size,
        dataset_name=dataset_name,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    ohlcv_path = output_dir / "ohlcv.csv"
    tickers_path = output_dir / "tickers.csv"
    metadata_path = output_dir / "metadata.json"

    result.ohlcv.to_csv(ohlcv_path, index=False)
    pd.DataFrame(
        {
            "ticker": [ticker.ticker for ticker in result.tickers],
            "query_symbol": [ticker.query_symbol for ticker in result.tickers],
        }
    ).to_csv(tickers_path, index=False)

    metadata = {
        "universe": dataset_name,
        "source": "Yahoo Finance via yfinance",
        "downloaded_at_utc": datetime.now(UTC).isoformat(),
        "start": start,
        "end": end,
        "interval": interval,
        "market": market,
        "ticker_count": len(result.tickers),
        "downloaded_ticker_count": int(result.ohlcv["ticker"].nunique()),
        "row_count": int(len(result.ohlcv)),
        "columns": OHLCV_COLUMNS,
        "tickers": [asdict(ticker) for ticker in result.tickers],
        "failed_batches": result.failed_batches,
        "research_note": "Yahoo Finance is used for pilot experiments only.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return DownloadResult(
        universe=dataset_name,
        ticker_count=len(result.tickers),
        row_count=len(result.ohlcv),
        start=start,
        end=end,
        output_dir=str(output_dir),
        ohlcv_path=str(ohlcv_path),
        tickers_path=str(tickers_path),
        metadata_path=str(metadata_path),
    )


def download_ticker_frame(
    tickers: list[str],
    start: str,
    end: str | None = None,
    *,
    market: TickerMarket = "auto",
    interval: str = "1d",
    batch_size: int = 80,
    dataset_name: str = "custom",
) -> DownloadFrameResult:
    """Download OHLCV data for explicit tickers and return it in memory."""

    if interval not in {"1m", "5m", "1d"}:
        raise ValueError("interval must be one of 1m, 5m, 1d")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    resolved = [resolve_yfinance_ticker(ticker, market=market) for ticker in tickers]
    if not resolved:
        raise ValueError("tickers must not be empty")

    query_symbols = [ticker.query_symbol for ticker in resolved]
    aliases = {ticker.query_symbol: ticker.ticker for ticker in resolved}
    failed_batches: list[list[str]] = []
    all_frames: list[pd.DataFrame] = []

    for ticker_batch in batched(query_symbols, batch_size):
        raw = yf.download(
            tickers=ticker_batch,
            start=start,
            end=end,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            threads=True,
            progress=False,
        )
        normalized = _normalize_download_frame(
            raw,
            ticker_batch,
            aliases,
            preserve_timestamp=interval != "1d",
        )
        if normalized.empty:
            failed_batches.append(ticker_batch)
        else:
            all_frames.append(normalized)

    if not all_frames:
        raise RuntimeError(f"No OHLCV rows downloaded for ticker list {dataset_name}.")

    ohlcv = pd.concat(all_frames, ignore_index=True)
    ohlcv = ohlcv.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])
    return DownloadFrameResult(
        dataset_name=dataset_name,
        tickers=resolved,
        ohlcv=ohlcv.reset_index(drop=True),
        start=start,
        end=end,
        interval=interval,
        failed_batches=failed_batches,
    )


def download_universe(
    name: UniverseName,
    output_root: Path,
    start: str,
    end: str | None = None,
    batch_size: int = 80,
) -> DownloadResult:
    """Load a universe definition and download its OHLCV data."""

    universe = load_universe(name)
    return download_ohlcv(
        universe=universe,
        output_root=output_root,
        start=start,
        end=end,
        batch_size=batch_size,
    )


def result_to_json(result: DownloadResult) -> str:
    """Serialize a download result for CLI output."""

    return json.dumps(asdict(result), indent=2)
