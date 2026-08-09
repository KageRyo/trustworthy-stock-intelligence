"""Stock universe definitions and loaders.

The pilot downloader uses Wikipedia as a convenient source for index
constituents. This is suitable for reproducible pipeline smoke tests, but
formal research should document the exact universe snapshot and data vendor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
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


class PointInTimeMembership(BaseModel):
    """One half-open membership interval: ``[valid_from, valid_to)``."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    valid_from: date
    valid_to: date | None = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_interval(self) -> "PointInTimeMembership":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class PointInTimeUniverse(BaseModel):
    """Auditable historical universe membership with explicit source metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["point_in_time_universe.v1"] = "point_in_time_universe.v1"
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_license: str = Field(min_length=1)
    memberships: list[PointInTimeMembership]

    @model_validator(mode="after")
    def validate_non_overlapping_intervals(self) -> "PointInTimeUniverse":
        if not self.memberships:
            raise ValueError("memberships must not be empty")
        by_ticker: dict[str, list[PointInTimeMembership]] = {}
        for membership in self.memberships:
            by_ticker.setdefault(membership.ticker, []).append(membership)
        for ticker, intervals in by_ticker.items():
            ordered = sorted(intervals, key=lambda item: item.valid_from)
            for previous, current in zip(ordered, ordered[1:]):
                if previous.valid_to is None or current.valid_from < previous.valid_to:
                    raise ValueError(f"overlapping membership intervals for ticker {ticker!r}")
        return self

    def membership_fingerprint(self) -> str:
        """Return a stable SHA-256 fingerprint of canonical membership rows."""

        rows = [
            membership.model_dump(mode="json")
            for membership in sorted(
                self.memberships,
                key=lambda item: (item.ticker, item.valid_from, item.valid_to or date.max),
            )
        ]
        canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def active_tickers(self, as_of: date | str | pd.Timestamp) -> tuple[str, ...]:
        """Return symbols active at a given evaluation date."""

        evaluation_date = _coerce_date(as_of, field_name="as_of")
        return tuple(
            sorted(
                {
                    membership.ticker
                    for membership in self.memberships
                    if membership.valid_from <= evaluation_date
                    and (membership.valid_to is None or evaluation_date < membership.valid_to)
                }
            )
        )

    def manifest(self) -> dict[str, object]:
        """Return a compact, reproducibility-focused manifest."""

        starts = [membership.valid_from for membership in self.memberships]
        ends = [membership.valid_to for membership in self.memberships if membership.valid_to]
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "source": self.source,
            "source_license": self.source_license,
            "interval_semantics": "[valid_from, valid_to); null valid_to means open-ended",
            "membership_count": len(self.memberships),
            "ticker_count": len({membership.ticker for membership in self.memberships}),
            "valid_from": min(starts).isoformat() if starts else None,
            "valid_to": max(ends).isoformat() if ends else None,
            "membership_sha256": self.membership_fingerprint(),
        }


def load_point_in_time_universe(
    path: str | bytes | Path,
    *,
    name: str,
    source: str,
    source_license: str,
) -> PointInTimeUniverse:
    """Load and validate a point-in-time membership CSV without storing raw data."""

    if not name.strip() or not source.strip() or not source_license.strip():
        raise ValueError("name, source, and source_license must not be empty")
    frame = pd.read_csv(path, dtype={"ticker": "string"})
    required = {"ticker", "valid_from", "valid_to"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"membership CSV is missing columns: {', '.join(missing)}")

    memberships: list[PointInTimeMembership] = []
    for _, row in frame.iterrows():
        if pd.isna(row["ticker"]):
            raise ValueError("ticker must not be empty")
        memberships.append(
            PointInTimeMembership(
                ticker=str(row["ticker"]),
                valid_from=_coerce_date(row["valid_from"], field_name="valid_from"),
                valid_to=(
                    None
                    if pd.isna(row["valid_to"])
                    else _coerce_date(row["valid_to"], field_name="valid_to")
                ),
            )
        )
    return PointInTimeUniverse(
        name=name.strip(),
        source=source.strip(),
        source_license=source_license.strip(),
        memberships=memberships,
    )


def filter_frame_by_point_in_time_universe(
    frame: pd.DataFrame,
    universe: PointInTimeUniverse,
    *,
    date_column: str = "date",
    ticker_column: str = "ticker",
) -> pd.DataFrame:
    """Keep only rows whose symbol was active on that row's evaluation date."""

    missing = [column for column in (date_column, ticker_column) if column not in frame.columns]
    if missing:
        raise ValueError(f"frame is missing columns: {', '.join(missing)}")

    intervals: dict[str, tuple[PointInTimeMembership, ...]] = {}
    for membership in universe.memberships:
        intervals.setdefault(membership.ticker, tuple())
        intervals[membership.ticker] = (*intervals[membership.ticker], membership)

    mask = [
        any(
            membership.valid_from <= evaluation_date
            and (membership.valid_to is None or evaluation_date < membership.valid_to)
            for membership in intervals.get(str(ticker).strip(), ())
        )
        for ticker, evaluation_date in zip(
            frame[ticker_column],
            pd.to_datetime(frame[date_column]).dt.date,
            strict=True,
        )
    ]
    return frame.loc[mask].copy().reset_index(drop=True)


def _coerce_date(value: object, *, field_name: str) -> date:
    if pd.isna(value):
        raise ValueError(f"{field_name} must not be empty")
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO-compatible date") from exc


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
