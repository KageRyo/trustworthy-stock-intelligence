"""Pilot OHLCV downloader for Yahoo Finance.

Yahoo Finance is used for early pipeline validation only. Formal research
should prefer a licensed and versioned market data source.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from tsi.data.universe import Universe, UniverseName, load_universe

OHLCV_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


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


def batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    """Yield fixed-size batches."""

    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _normalize_download_frame(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Convert yfinance output into a tidy OHLCV table."""

    if raw.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    frames: list[pd.DataFrame] = []
    if isinstance(raw.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            ticker_frame = raw[ticker].copy()
            ticker_frame["ticker"] = ticker
            frames.append(ticker_frame)
    else:
        ticker_frame = raw.copy()
        ticker_frame["ticker"] = tickers[0]
        frames.append(ticker_frame)

    if not frames:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    data = pd.concat(frames).reset_index()
    data = data.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    data["date"] = pd.to_datetime(data["date"]).dt.date.astype(str)

    for column in OHLCV_COLUMNS:
        if column not in data.columns:
            data[column] = pd.NA

    data = data[OHLCV_COLUMNS]
    data = data.dropna(subset=["date", "ticker", "open", "high", "low", "close", "adj_close"])
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
