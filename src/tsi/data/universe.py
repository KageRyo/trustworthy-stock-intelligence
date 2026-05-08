"""Stock universe definitions and loaders.

The pilot downloader uses Wikipedia as a convenient source for index
constituents. This is suitable for reproducible pipeline smoke tests, but
formal research should document the exact universe snapshot and data vendor.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Literal

import pandas as pd
import requests

UniverseName = Literal["sp100", "sp500"]

SP100_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/S%26P_100"
SP500_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HTTP_HEADERS = {
    "User-Agent": (
        "trustworthy-stock-intelligence/0.1 "
        "(research pilot; https://github.com/KageRyo/trustworthy-stock-intelligence)"
    )
}


@dataclass(frozen=True)
class Universe:
    """A stock universe snapshot for pilot experiments."""

    name: UniverseName
    source_url: str
    tickers: list[str]


def normalize_yfinance_ticker(ticker: str) -> str:
    """Convert common index symbols to Yahoo Finance ticker format."""

    return ticker.strip().replace(".", "-")


def load_sp100_tickers() -> Universe:
    """Load the current S&P 100 constituents from Wikipedia."""

    tables = read_wikipedia_tables(SP100_WIKIPEDIA_URL)
    candidates = [table for table in tables if "Symbol" in table.columns]
    if not candidates:
        raise RuntimeError("Could not find an S&P 100 constituents table with a Symbol column.")

    tickers = (
        candidates[0]["Symbol"]
        .dropna()
        .astype(str)
        .map(normalize_yfinance_ticker)
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return Universe(name="sp100", source_url=SP100_WIKIPEDIA_URL, tickers=tickers)


def load_sp500_tickers() -> Universe:
    """Load the current S&P 500 constituents from Wikipedia."""

    tables = read_wikipedia_tables(SP500_WIKIPEDIA_URL)
    candidates = [table for table in tables if "Symbol" in table.columns]
    if not candidates:
        raise RuntimeError("Could not find an S&P 500 constituents table with a Symbol column.")

    tickers = (
        candidates[0]["Symbol"]
        .dropna()
        .astype(str)
        .map(normalize_yfinance_ticker)
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return Universe(name="sp500", source_url=SP500_WIKIPEDIA_URL, tickers=tickers)


def load_universe(name: UniverseName) -> Universe:
    """Load a supported pilot universe."""

    if name == "sp100":
        return load_sp100_tickers()
    if name == "sp500":
        return load_sp500_tickers()
    raise ValueError(f"Unsupported universe: {name}")


def read_wikipedia_tables(url: str) -> list[pd.DataFrame]:
    """Read Wikipedia tables with an explicit User-Agent."""

    response = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()
    return pd.read_html(StringIO(response.text))
