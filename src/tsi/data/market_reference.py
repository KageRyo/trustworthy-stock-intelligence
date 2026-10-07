"""US market reference series used by market-relative features.

The reference set is the broad market ETF (SPY), the CBOE volatility index (^VIX),
and the Select Sector SPDR ETF for each universe ticker's Yahoo sector. Sector
assignments are a current snapshot, not point-in-time history, so historical
features inherit today's classification (for example, GOOGL as Communication
Services before the 2018 GICS change). XLC starts in 2018-06 and XLRE in 2015-10;
feature code falls back to the market series before a sector ETF has prices.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
import yfinance as yf

from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.data.download import (
    DownloadFrameResult,
    download_ticker_frame,
    is_taiwan_local_ticker,
    normalize_yfinance_symbol,
)

US_MARKET_SYMBOL = "SPY"
US_VOLATILITY_SYMBOL = "^VIX"
SECTOR_ETF_BY_SECTOR_KEY: dict[str, str] = {
    "basic-materials": "XLB",
    "communication-services": "XLC",
    "consumer-cyclical": "XLY",
    "consumer-defensive": "XLP",
    "energy": "XLE",
    "financial-services": "XLF",
    "healthcare": "XLV",
    "industrials": "XLI",
    "real-estate": "XLRE",
    "technology": "XLK",
    "utilities": "XLU",
}
SECTOR_MAP_COLUMNS = ["ticker", "sector", "sector_key", "sector_etf"]

InfoFetcher = Callable[[str], Mapping[str, object]]
FrameDownloader = Callable[..., DownloadFrameResult]


class YahooSectorInfo(BaseModel):
    """Sector fields read from a yfinance ``Ticker.info`` payload."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    sector: str | None = None
    sector_key: str | None = Field(default=None, alias="sectorKey")


class TickerSectorRecord(BaseModel):
    """One universe ticker and the sector ETF used as its peer benchmark."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    sector: str | None = None
    sector_key: str | None = None
    sector_etf: str | None = None
    error: str = ""


@dataclass(frozen=True)
class MarketReferenceResult:
    """Paths and symbols written by :func:`download_market_reference`."""

    symbols: list[str]
    row_count: int
    output_dir: str
    ohlcv_path: str
    sector_map_path: str
    metadata_path: str


@dataclass(frozen=True)
class MarketReference:
    """Reference OHLCV plus the market, volatility, and per-ticker sector symbols."""

    ohlcv: pd.DataFrame
    market_symbol: str
    volatility_symbol: str | None
    sector_etf_by_ticker: dict[str, str]


def sector_etf_for(sector_key: str | None) -> str | None:
    """Return the Select Sector SPDR ETF for a Yahoo ``sectorKey``."""

    if not sector_key:
        return None
    return SECTOR_ETF_BY_SECTOR_KEY.get(sector_key)


def yfinance_info(symbol: str) -> Mapping[str, object]:
    """Fetch the yfinance ``Ticker.info`` payload for ``symbol``."""

    return yf.Ticker(symbol).info


def fetch_ticker_sectors(
    tickers: Sequence[str],
    *,
    info_fetcher: InfoFetcher = yfinance_info,
) -> list[TickerSectorRecord]:
    """Look up each US ticker's Yahoo sector; provider failures are recorded, not raised."""

    taiwan = [ticker for ticker in tickers if is_taiwan_local_ticker(ticker)]
    if taiwan:
        raise ValueError(
            "Sector ETF mapping supports US tickers only; got Taiwan codes: " + ", ".join(taiwan)
        )
    records: list[TickerSectorRecord] = []
    for ticker in tickers:
        symbol = normalize_yfinance_symbol(ticker)
        try:
            info = YahooSectorInfo.model_validate(dict(info_fetcher(symbol)))
        except Exception as error:  # noqa: BLE001 - provider failures become audit records
            records.append(TickerSectorRecord(ticker=symbol, error=str(error)))
            continue
        records.append(
            TickerSectorRecord(
                ticker=symbol,
                sector=info.sector,
                sector_key=info.sector_key,
                sector_etf=sector_etf_for(info.sector_key),
            )
        )
    return records


def download_market_reference(
    tickers: Sequence[str],
    *,
    output_dir: Path,
    start: str,
    end: str | None = None,
    info_fetcher: InfoFetcher = yfinance_info,
    frame_downloader: FrameDownloader = download_ticker_frame,
) -> MarketReferenceResult:
    """Download SPY, ^VIX, and the universe's sector ETFs, then write CSV artifacts."""

    sectors = fetch_ticker_sectors(tickers, info_fetcher=info_fetcher)
    sector_etfs = sorted({record.sector_etf for record in sectors if record.sector_etf})
    symbols = [US_MARKET_SYMBOL, US_VOLATILITY_SYMBOL, *sector_etfs]
    downloaded = frame_downloader(
        symbols, start, end, market="us", interval="1d", dataset_name="market_reference"
    )
    missing = sorted(set(symbols) - set(downloaded.ohlcv["ticker"]))
    if US_MARKET_SYMBOL in missing:
        raise RuntimeError(f"Market reference download returned no {US_MARKET_SYMBOL} rows")

    output_dir.mkdir(parents=True, exist_ok=True)
    ohlcv_path = output_dir / "ohlcv.csv"
    sector_map_path = output_dir / "sector_map.csv"
    metadata_path = output_dir / "metadata.json"
    downloaded.ohlcv.to_csv(ohlcv_path, index=False)
    pd.DataFrame(
        [record.model_dump(include=set(SECTOR_MAP_COLUMNS)) for record in sectors],
        columns=SECTOR_MAP_COLUMNS,
    ).to_csv(sector_map_path, index=False)

    metadata = {
        "dataset": "market_reference",
        "source": "Yahoo Finance via yfinance",
        "downloaded_at_utc": datetime.now(UTC).isoformat(),
        "start": start,
        "end": end,
        "interval": "1d",
        "market_symbol": US_MARKET_SYMBOL,
        "volatility_symbol": US_VOLATILITY_SYMBOL,
        "sector_etfs": sector_etfs,
        "missing_symbols": missing,
        "universe_ticker_count": len(sectors),
        "unmapped_tickers": [record.ticker for record in sectors if record.sector_etf is None],
        "sector_lookup_errors": {record.ticker: record.error for record in sectors if record.error},
        "row_count": int(len(downloaded.ohlcv)),
        "ohlcv_sha256": file_sha256(ohlcv_path),
        "sector_map_sha256": file_sha256(sector_map_path),
        "research_note": (
            "Sector assignments are a current snapshot applied to all history. "
            "Yahoo Finance is used for pilot experiments only."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return MarketReferenceResult(
        symbols=symbols,
        row_count=int(len(downloaded.ohlcv)),
        output_dir=str(output_dir),
        ohlcv_path=str(ohlcv_path),
        sector_map_path=str(sector_map_path),
        metadata_path=str(metadata_path),
    )


def load_market_reference(directory: Path) -> MarketReference:
    """Load reference artifacts written by :func:`download_market_reference`."""

    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    sector_map = pd.read_csv(directory / "sector_map.csv", dtype=str, keep_default_na=False)
    records = [
        TickerSectorRecord.model_validate(
            {column: (row[column] or None) for column in SECTOR_MAP_COLUMNS}
        )
        for row in sector_map.to_dict("records")
    ]
    return MarketReference(
        ohlcv=read_ohlcv_csv(directory / "ohlcv.csv"),
        market_symbol=str(metadata["market_symbol"]),
        volatility_symbol=metadata.get("volatility_symbol"),
        sector_etf_by_ticker={
            record.ticker: record.sector_etf for record in records if record.sector_etf
        },
    )
