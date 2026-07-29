"""Pilot OHLCV downloader for Yahoo Finance.

Yahoo Finance is used for early pipeline validation only. Formal research
should prefer a licensed and versioned market data source.
"""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
import yfinance as yf

from tsi.data.universe import Universe, UniverseName, load_universe

OHLCV_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
TickerMarket = Literal["auto", "us", "twse", "tpex", "emerging"]
ResolvedTickerMarket = Literal["us", "twse", "tpex", "emerging", "taiwan", "unknown"]
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TPEX_DAILY_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
TPEX_EMERGING_HISTORICAL_URL = "https://www.tpex.org.tw/www/zh-tw/emerging/historical"


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
    market: ResolvedTickerMarket = "unknown"


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


@dataclass(frozen=True)
class TaiwanFallbackResult:
    """Official Taiwan exchange fallback data and resolved market metadata."""

    ohlcv: pd.DataFrame
    query_symbol: str
    market: ResolvedTickerMarket


def file_sha256(path: Path) -> str:
    """Return a stable SHA-256 fingerprint for a downloaded artifact."""

    digest = sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TWSEStockDayResponse(BaseModel):
    """Schema for TWSE STOCK_DAY monthly daily-bar responses."""

    model_config = ConfigDict(extra="ignore")

    stat: str
    date: str | None = None
    title: str | None = None
    fields: list[str] = Field(default_factory=list)
    data: list[list[str]] = Field(default_factory=list)


class TPEXTradingStockTable(BaseModel):
    """Schema for one TPEx daily trading table."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    subtitle: str | None = None
    date: str | None = None
    data: list[list[str]] = Field(default_factory=list)


class TPEXTradingStockResponse(BaseModel):
    """Schema for TPEx daily trading responses."""

    model_config = ConfigDict(extra="ignore")

    tables: list[TPEXTradingStockTable] = Field(default_factory=list)


class TPEXEmergingHistoricalTable(BaseModel):
    """Schema for one TPEx emerging-stock historical monthly table."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    subtitle: str | None = None
    date: str | None = None
    totalCount: int | None = None
    fields: list[str] = Field(default_factory=list)
    data: list[list[str]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TPEXEmergingHistoricalResponse(BaseModel):
    """Schema for TPEx emerging-stock historical trading responses."""

    model_config = ConfigDict(extra="ignore")

    stat: str
    date: str | None = None
    tables: list[TPEXEmergingHistoricalTable] = Field(default_factory=list)


def batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    """Yield fixed-size batches."""

    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def configure_yfinance_cache() -> None:
    """Point yfinance's timezone cache at a known writable local directory."""

    cache_dir = Path(os.getenv("TSI_YFINANCE_CACHE_DIR", "/tmp/tsi-yfinance-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    set_cache_location = getattr(yf, "set_tz_cache_location", None)
    if callable(set_cache_location):
        set_cache_location(str(cache_dir))


def is_taiwan_local_ticker(ticker: str) -> bool:
    """Return whether a ticker looks like a local Taiwan stock or ETF code."""

    normalized = (
        ticker.strip().upper().removesuffix(".TW").removesuffix(".TWO").removesuffix(".EMERGING")
    )
    if normalized.isdigit() and 4 <= len(normalized) <= 6:
        return True
    return re.fullmatch(r"[0-9]{4,6}[A-Z]", normalized) is not None


def resolve_yfinance_ticker(ticker: str, *, market: TickerMarket = "auto") -> DownloadTicker:
    """Resolve an input ticker to a yfinance query symbol.

    Taiwan listed stocks use numeric local codes in the dashboard, while
    yfinance expects exchange suffixes such as ``.TW`` or ``.TWO``.
    """

    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")

    if market == "auto":
        if normalized.endswith(".TW"):
            return DownloadTicker(
                ticker=normalized.removesuffix(".TW"),
                query_symbol=normalized,
                market="twse",
            )
        if normalized.endswith(".TWO"):
            return DownloadTicker(
                ticker=normalized.removesuffix(".TWO"),
                query_symbol=normalized,
                market="tpex",
            )
        if normalized.endswith(".EMERGING"):
            return DownloadTicker(
                ticker=normalized.removesuffix(".EMERGING"),
                query_symbol=normalized,
                market="emerging",
            )
        if is_taiwan_local_ticker(normalized):
            return DownloadTicker(ticker=normalized, query_symbol=f"{normalized}.TW", market="twse")
        return DownloadTicker(
            ticker=normalize_yfinance_symbol(normalized),
            query_symbol=normalized,
            market="us",
        )
    if market == "us":
        symbol = normalize_yfinance_symbol(normalized)
        return DownloadTicker(ticker=symbol, query_symbol=symbol, market="us")
    if market == "twse":
        code = normalized.removesuffix(".TW")
        if not is_taiwan_local_ticker(code):
            raise ValueError("twse market requires a Taiwan stock code")
        return DownloadTicker(ticker=code, query_symbol=f"{code}.TW", market="twse")
    if market == "tpex":
        code = normalized.removesuffix(".TWO")
        if not is_taiwan_local_ticker(code):
            raise ValueError("tpex market requires a Taiwan stock code")
        return DownloadTicker(ticker=code, query_symbol=f"{code}.TWO", market="tpex")
    if market == "emerging":
        code = normalized.removesuffix(".EMERGING")
        if not is_taiwan_local_ticker(code):
            raise ValueError("emerging market requires a Taiwan stock code")
        return DownloadTicker(ticker=code, query_symbol=f"{code}.EMERGING", market="emerging")
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

    configure_yfinance_cache()
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
        "ohlcv_sha256": file_sha256(ohlcv_path),
        "tickers_sha256": file_sha256(tickers_path),
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
            "market": [ticker.market for ticker in result.tickers],
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
        "ohlcv_sha256": file_sha256(ohlcv_path),
        "tickers_sha256": file_sha256(tickers_path),
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

    configure_yfinance_cache()
    if interval not in {"1m", "5m", "1d"}:
        raise ValueError("interval must be one of 1m, 5m, 1d")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    resolved = [resolve_yfinance_ticker(ticker, market=market) for ticker in tickers]
    if not resolved:
        raise ValueError("tickers must not be empty")

    query_symbols = [ticker.query_symbol for ticker in resolved]
    aliases = {ticker.query_symbol: ticker.ticker for ticker in resolved}
    resolved_by_query = {ticker.query_symbol: ticker for ticker in resolved}
    resolved_by_ticker = {ticker.ticker: ticker for ticker in resolved}
    failed_batches: list[list[str]] = []
    all_frames: list[pd.DataFrame] = []

    for ticker_batch in batched(query_symbols, batch_size):
        downloaded_aliases: set[str] = set()
        if all(resolved_by_query[query_symbol].market == "emerging" for query_symbol in ticker_batch):
            raw = pd.DataFrame()
        else:
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
        if not normalized.empty:
            all_frames.append(normalized)
            downloaded_aliases = set(normalized["ticker"].unique())
        for query_symbol in ticker_batch:
            resolved_ticker = resolved_by_query[query_symbol]
            if resolved_ticker.ticker in downloaded_aliases:
                continue
            fallback = download_taiwan_daily_fallback(
                resolved_ticker.ticker,
                start=start,
                end=end,
                market=market,
                interval=interval,
            )
            if fallback.ohlcv.empty:
                failed_batches.append([query_symbol])
            else:
                all_frames.append(fallback.ohlcv)
                resolved_by_ticker[resolved_ticker.ticker] = DownloadTicker(
                    ticker=resolved_ticker.ticker,
                    query_symbol=fallback.query_symbol,
                    market=fallback.market,
                )

    if not all_frames:
        raise RuntimeError(f"No OHLCV rows downloaded for ticker list {dataset_name}.")

    ohlcv = pd.concat(all_frames, ignore_index=True)
    ohlcv = ohlcv.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])
    return DownloadFrameResult(
        dataset_name=dataset_name,
        tickers=[resolved_by_ticker[ticker.ticker] for ticker in resolved],
        ohlcv=ohlcv.reset_index(drop=True),
        start=start,
        end=end,
        interval=interval,
        failed_batches=failed_batches,
    )


def download_taiwan_daily_fallback(
    ticker: str,
    *,
    start: str,
    end: str | None,
    market: TickerMarket,
    interval: str,
) -> TaiwanFallbackResult:
    """Fetch Taiwan daily bars from official TWSE/TPEx endpoints when yfinance misses."""

    if interval != "1d" or market == "us" or not is_taiwan_local_ticker(ticker):
        return empty_taiwan_fallback(ticker, market="unknown")
    if market == "emerging":
        frame = download_tpex_emerging_daily_frame(ticker, start=start, end=end)
        return TaiwanFallbackResult(frame, f"{ticker.strip().upper()}.EMERGING", "emerging")
    if market == "tpex":
        frame = download_tpex_daily_frame(ticker, start=start, end=end)
        return TaiwanFallbackResult(frame, f"{ticker.strip().upper()}.TWO", "tpex")
    if market == "twse":
        frame = download_twse_daily_frame(ticker, start=start, end=end)
        return TaiwanFallbackResult(frame, f"{ticker.strip().upper()}.TW", "twse")

    twse_frame = download_twse_daily_frame(ticker, start=start, end=end)
    if not twse_frame.empty:
        return TaiwanFallbackResult(twse_frame, f"{ticker.strip().upper()}.TW", "twse")
    tpex_frame = download_tpex_daily_frame(ticker, start=start, end=end)
    if not tpex_frame.empty:
        return TaiwanFallbackResult(tpex_frame, f"{ticker.strip().upper()}.TWO", "tpex")
    emerging_frame = download_tpex_emerging_daily_frame(ticker, start=start, end=end)
    if not emerging_frame.empty:
        return TaiwanFallbackResult(emerging_frame, f"{ticker.strip().upper()}.EMERGING", "emerging")
    return empty_taiwan_fallback(ticker, market="unknown")


def download_twse_daily_frame(ticker: str, *, start: str, end: str | None) -> pd.DataFrame:
    rows: list[list[str]] = []
    for month in month_starts(start, end):
        payload = TWSEStockDayResponse.model_validate(
            fetch_json(
                TWSE_STOCK_DAY_URL,
                {
                    "response": "json",
                    "date": month.strftime("%Y%m01"),
                    "stockNo": ticker,
                },
            )
        )
        if payload.stat != "OK":
            continue
        rows.extend(payload.data)
    return taiwan_rows_to_ohlcv(ticker, rows)


def download_tpex_daily_frame(ticker: str, *, start: str, end: str | None) -> pd.DataFrame:
    rows: list[list[str]] = []
    for month in month_starts(start, end):
        payload = TPEXTradingStockResponse.model_validate(
            fetch_json(
                TPEX_DAILY_URL,
                {
                    "code": ticker,
                    "date": month.strftime("%Y/%m/01"),
                    "id": "",
                    "response": "json",
                },
            )
        )
        for table in payload.tables:
            rows.extend(table.data)
    return taiwan_rows_to_ohlcv(ticker, rows)


def download_tpex_emerging_daily_frame(ticker: str, *, start: str, end: str | None) -> pd.DataFrame:
    rows: list[list[str]] = []
    for month in month_starts(start, end):
        payload = TPEXEmergingHistoricalResponse.model_validate(
            fetch_json_post(
                TPEX_EMERGING_HISTORICAL_URL,
                {
                    "date": month.strftime("%Y%m01"),
                    "code": ticker,
                    "type": "Monthly",
                    "response": "json",
                },
            )
        )
        if payload.stat != "ok":
            continue
        for table in payload.tables:
            rows.extend(table.data)
    return tpex_emerging_rows_to_ohlcv(ticker, rows)


def empty_taiwan_fallback(ticker: str, *, market: ResolvedTickerMarket) -> TaiwanFallbackResult:
    query_symbol = ticker.strip().upper()
    return TaiwanFallbackResult(pd.DataFrame(columns=OHLCV_COLUMNS), query_symbol, market)


def fetch_json(url: str, params: dict[str, str]) -> dict[str, object]:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"User-Agent": "trustworthy-stock-intelligence/0.1"},
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_json_post(url: str, params: dict[str, str]) -> dict[str, object]:
    request = Request(
        url,
        data=urlencode(params).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "trustworthy-stock-intelligence/0.1",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def month_starts(start: str, end: str | None) -> list[pd.Timestamp]:
    start_ts = pd.Timestamp(start).tz_localize(None).replace(day=1)
    end_ts = pd.Timestamp(end).tz_localize(None) if end else pd.Timestamp.now(tz=UTC).tz_localize(None)
    end_ts = end_ts.replace(day=1)
    if end_ts < start_ts:
        return []
    return list(pd.date_range(start_ts, end_ts, freq="MS"))


def taiwan_rows_to_ohlcv(ticker: str, rows: list[list[str]]) -> pd.DataFrame:
    parsed_rows = []
    for row in rows:
        if len(row) < 7:
            continue
        date = parse_minguo_date(row[0])
        values = [parse_taiwan_number(value) for value in row[1:7]]
        if date is None or any(value is None for value in values):
            continue
        volume, _, open_price, high_price, low_price, close_price = values
        parsed_rows.append(
            {
                "date": date,
                "ticker": ticker.strip().upper(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "adj_close": close_price,
                "volume": volume,
            }
        )
    if not parsed_rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    frame = pd.DataFrame(parsed_rows)
    return frame.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])


def tpex_emerging_rows_to_ohlcv(ticker: str, rows: list[list[str]]) -> pd.DataFrame:
    parsed_rows = []
    for row in rows:
        if len(row) < 13:
            continue
        date = parse_minguo_date(row[0])
        values = [parse_taiwan_number(value) for value in row[1:13]]
        if date is None or any(value is None for value in values):
            continue
        click_volume, click_amount, click_high, click_low, click_avg, _click_trades = values[:6]
        off_volume, off_amount, off_high, off_low, off_avg, _off_trades = values[6:12]
        total_volume = (click_volume or 0.0) + (off_volume or 0.0)
        total_amount = (click_amount or 0.0) + (off_amount or 0.0)
        if total_volume <= 0:
            continue
        high_candidates = [value for value in (click_high, off_high) if value and value > 0]
        low_candidates = [value for value in (click_low, off_low) if value and value > 0]
        average_candidates = [
            (click_avg, click_volume or 0.0),
            (off_avg, off_volume or 0.0),
        ]
        weighted_average = weighted_price(average_candidates)
        close_price = total_amount / total_volume if total_amount > 0 else weighted_average
        if close_price is None or close_price <= 0:
            continue
        high_price = max(high_candidates, default=close_price)
        low_price = min(low_candidates, default=close_price)
        parsed_rows.append(
            {
                "date": date,
                "ticker": ticker.strip().upper(),
                "open": close_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "adj_close": close_price,
                "volume": total_volume,
            }
        )
    if not parsed_rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    frame = pd.DataFrame(parsed_rows)
    return frame.drop_duplicates(subset=["date", "ticker"]).sort_values(["ticker", "date"])


def weighted_price(values: list[tuple[float | None, float]]) -> float | None:
    weighted_total = 0.0
    weight_total = 0.0
    for value, weight in values:
        if value is None or value <= 0 or weight <= 0:
            continue
        weighted_total += value * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return weighted_total / weight_total


def parse_minguo_date(value: str) -> str | None:
    parts = value.strip().split("/")
    if len(parts) != 3:
        return None
    try:
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_taiwan_number(value: object) -> float | None:
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "---", "X", "除權息"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


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
