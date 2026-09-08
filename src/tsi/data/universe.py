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
POINT_IN_TIME_UNIVERSE_V2_SCHEMA = "point_in_time_universe.v2"

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
    universe: PointInTimeUniverse | PointInTimeUniverseV2,
    *,
    date_column: str = "date",
    ticker_column: str = "ticker",
) -> pd.DataFrame:
    """Keep only rows whose symbol was active on that row's evaluation date."""

    missing = [column for column in (date_column, ticker_column) if column not in frame.columns]
    if missing:
        raise ValueError(f"frame is missing columns: {', '.join(missing)}")

    intervals: dict[str, tuple[PointInTimeMembership | PointInTimeSecurityMembership, ...]] = {}
    for membership in universe.memberships:
        intervals.setdefault(membership.ticker, tuple())
        intervals[membership.ticker] = (*intervals[membership.ticker], membership)

    mask = [
        any(
            membership.valid_from <= evaluation_date
            and (membership.valid_to is None or evaluation_date < membership.valid_to)
            and (
                not isinstance(membership, PointInTimeSecurityMembership)
                or membership.known_at <= evaluation_date
            )
            for membership in intervals.get(str(ticker).strip(), ())
        )
        for ticker, evaluation_date in zip(
            frame[ticker_column],
            pd.to_datetime(frame[date_column]).dt.date,
            strict=True,
        )
    ]
    return frame.loc[mask].copy().reset_index(drop=True)


class PointInTimeSecurityMembership(BaseModel):
    """One stable-security identity interval in the v2 universe schema.

    ``valid_from``/``valid_to`` describe when the identity fact was effective;
    ``known_at`` records the earliest date on which the fact was knowable.  The
    latter is used by point-in-time filtering so a later correction cannot leak
    into an earlier evaluation date.
    """

    model_config = ConfigDict(extra="forbid")

    security_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    provider_symbol: str | None = None
    market: str = ""
    exchange: str = ""
    valid_from: date
    valid_to: date | None = None
    known_at: date
    change_reason: str | None = None

    @field_validator("security_id", "ticker", "provider_symbol", "market", "exchange")
    @classmethod
    def normalize_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None if value is None else ""
        return normalized

    @field_validator("change_reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None

    @model_validator(mode="after")
    def validate_interval(self) -> "PointInTimeSecurityMembership":
        if not self.security_id:
            raise ValueError("security_id must not be empty")
        if not self.ticker:
            raise ValueError("ticker must not be empty")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class PointInTimeUniverseV2(BaseModel):
    """Stable-identity point-in-time membership with explicit symbol history."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[POINT_IN_TIME_UNIVERSE_V2_SCHEMA] = POINT_IN_TIME_UNIVERSE_V2_SCHEMA
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_license: str = Field(min_length=1)
    memberships: list[PointInTimeSecurityMembership]

    @model_validator(mode="after")
    def validate_identity_and_symbol_intervals(self) -> "PointInTimeUniverseV2":
        if not self.memberships:
            raise ValueError("memberships must not be empty")

        by_identity: dict[str, list[PointInTimeSecurityMembership]] = {}
        by_symbol: dict[tuple[str, str, str], list[PointInTimeSecurityMembership]] = {}
        by_provider_symbol: dict[str, list[PointInTimeSecurityMembership]] = {}
        for membership in self.memberships:
            by_identity.setdefault(membership.security_id, []).append(membership)
            symbol_key = (
                membership.ticker,
                membership.market.lower(),
                membership.exchange.lower(),
            )
            by_symbol.setdefault(symbol_key, []).append(membership)
            if membership.provider_symbol:
                by_provider_symbol.setdefault(membership.provider_symbol, []).append(membership)

        for security_id, intervals in by_identity.items():
            _reject_overlapping_intervals(
                intervals,
                f"overlapping identity intervals for security_id {security_id!r}",
            )
        for symbol_key, intervals in by_symbol.items():
            _reject_ambiguous_intervals(
                intervals,
                f"ambiguous ticker mapping for {symbol_key[0]!r}",
            )
        for provider_symbol, intervals in by_provider_symbol.items():
            _reject_ambiguous_intervals(
                intervals,
                f"ambiguous provider_symbol mapping for {provider_symbol!r}",
            )
        return self

    def membership_fingerprint(self) -> str:
        """Fingerprint identity, symbol, effective, and knowability metadata."""

        rows = [
            membership.model_dump(mode="json")
            for membership in sorted(
                self.memberships,
                key=lambda item: (
                    item.security_id,
                    item.valid_from,
                    item.valid_to or date.max,
                    item.ticker,
                ),
            )
        ]
        canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def active_memberships(
        self, as_of: date | str | pd.Timestamp
    ) -> tuple[PointInTimeSecurityMembership, ...]:
        """Return facts effective and knowable on an evaluation date."""

        evaluation_date = _coerce_date(as_of, field_name="as_of")
        return tuple(
            sorted(
                (
                    membership
                    for membership in self.memberships
                    if membership.valid_from <= evaluation_date
                    and (membership.valid_to is None or evaluation_date < membership.valid_to)
                    and membership.known_at <= evaluation_date
                ),
                key=lambda item: (item.security_id, item.ticker),
            )
        )

    def active_tickers(self, as_of: date | str | pd.Timestamp) -> tuple[str, ...]:
        """Return active historical symbols without coercing identifiers."""

        return tuple(sorted({membership.ticker for membership in self.active_memberships(as_of)}))

    def manifest(self) -> dict[str, object]:
        """Return public provenance metadata without raw membership rows."""

        starts = [membership.valid_from for membership in self.memberships]
        ends = [membership.valid_to for membership in self.memberships if membership.valid_to]
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "source": self.source,
            "source_license": self.source_license,
            "interval_semantics": "[valid_from, valid_to); known_at must be <= evaluation date",
            "membership_count": len(self.memberships),
            "security_count": len({membership.security_id for membership in self.memberships}),
            "ticker_count": len({membership.ticker for membership in self.memberships}),
            "provider_symbol_count": len(
                {
                    membership.provider_symbol
                    for membership in self.memberships
                    if membership.provider_symbol
                }
            ),
            "valid_from": min(starts).isoformat() if starts else None,
            "valid_to": max(ends).isoformat() if ends else None,
            "membership_sha256": self.membership_fingerprint(),
        }


def migrate_v1_to_v2(universe: PointInTimeUniverse) -> PointInTimeUniverseV2:
    """Provide a conservative, explicit compatibility path from v1.

    v1 has no stable identifier or knowability date.  The migration therefore
    derives a legacy identity from each ticker and uses ``valid_from`` as the
    conservative knowability date.  It must not be presented as a historical
    identity repair; a licensed archive is still required for that claim.
    """

    return PointInTimeUniverseV2(
        name=universe.name,
        source=universe.source,
        source_license=universe.source_license,
        memberships=[
            PointInTimeSecurityMembership(
                security_id=f"legacy:{membership.ticker}",
                ticker=membership.ticker,
                provider_symbol=membership.ticker,
                valid_from=membership.valid_from,
                valid_to=membership.valid_to,
                known_at=membership.valid_from,
                change_reason="migrated_from_point_in_time_universe.v1",
            )
            for membership in universe.memberships
        ],
    )


def load_point_in_time_universe_v2(
    path: str | bytes | Path,
    *,
    name: str,
    source: str,
    source_license: str,
) -> PointInTimeUniverseV2:
    """Load a v2 identity archive with explicit column and metadata checks."""

    if not name.strip() or not source.strip() or not source_license.strip():
        raise ValueError("name, source, and source_license must not be empty")
    frame = pd.read_csv(path, dtype="string")
    required = {"security_id", "ticker", "valid_from", "known_at"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"v2 membership CSV is missing columns: {', '.join(missing)}")

    memberships: list[PointInTimeSecurityMembership] = []
    for _, row in frame.iterrows():
        memberships.append(
            PointInTimeSecurityMembership(
                security_id=_required_text(row["security_id"], "security_id"),
                ticker=_required_text(row["ticker"], "ticker"),
                provider_symbol=_optional_text(row.get("provider_symbol")),
                market=_optional_text(row.get("market")) or "",
                exchange=_optional_text(row.get("exchange")) or "",
                valid_from=_coerce_date(row["valid_from"], field_name="valid_from"),
                valid_to=(
                    None
                    if _optional_text(row.get("valid_to")) is None
                    else _coerce_date(row["valid_to"], field_name="valid_to")
                ),
                known_at=_coerce_date(row["known_at"], field_name="known_at"),
                change_reason=_optional_text(row.get("change_reason")),
            )
        )
    return PointInTimeUniverseV2(
        name=name.strip(),
        source=source.strip(),
        source_license=source_license.strip(),
        memberships=memberships,
    )


def load_point_in_time_universe_versioned(
    path: str | bytes | Path,
    *,
    schema_version: Literal["v1", "v2"] = "v1",
    name: str,
    source: str,
    source_license: str,
) -> PointInTimeUniverse | PointInTimeUniverseV2:
    """Load an explicitly selected membership schema for compatibility."""

    if schema_version == "v1":
        return load_point_in_time_universe(
            path,
            name=name,
            source=source,
            source_license=source_license,
        )
    return load_point_in_time_universe_v2(
        path,
        name=name,
        source=source,
        source_license=source_license,
    )


def _reject_overlapping_intervals(
    intervals: list[PointInTimeSecurityMembership],
    message: str,
) -> None:
    ordered = sorted(intervals, key=lambda item: item.valid_from)
    for previous, current in zip(ordered, ordered[1:]):
        if previous.valid_to is None or current.valid_from < previous.valid_to:
            raise ValueError(message)


def _reject_ambiguous_intervals(
    intervals: list[PointInTimeSecurityMembership],
    message: str,
) -> None:
    ordered = sorted(intervals, key=lambda item: item.valid_from)
    for previous, current in zip(ordered, ordered[1:]):
        if previous.security_id == current.security_id:
            continue
        if previous.valid_to is None or current.valid_from < previous.valid_to:
            raise ValueError(message)


def _required_text(value: object, field_name: str) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


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
