"""Typed capture of the current Taiwan listed-company universe.

This module deliberately captures a dated *current* catalogue only.  It must
not be converted into historical membership intervals without a source that
also records removals, delistings, and the dates at which each fact was known.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TaiwanMarket = Literal["twse", "tpex", "emerging"]
TWSE_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
TPEX_EMERGING_COMPANY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R"
SOURCE_URLS: dict[TaiwanMarket, str] = {
    "twse": TWSE_COMPANY_URL,
    "tpex": TPEX_COMPANY_URL,
    "emerging": TPEX_EMERGING_COMPANY_URL,
}
HTTP_HEADERS = {
    "User-Agent": (
        "trustworthy-stock-intelligence/0.1 "
        "(research universe capture; https://github.com/KageRyo/trustworthy-stock-intelligence)"
    )
}

JsonFetcher = Callable[[str], list[dict[str, object]]]


class TaiwanUniverseMember(BaseModel):
    """One company present in an official current-universe response."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    market: TaiwanMarket
    company_name: str = Field(min_length=1)
    industry_code: str | None = None
    listing_date: date
    provider_symbol: str = Field(min_length=1)

    @field_validator("ticker", "provider_symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("industry_code")
    @classmethod
    def normalize_industry_code(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class TaiwanUniverseSource(BaseModel):
    """Audit metadata for one official API response, without preserving it."""

    model_config = ConfigDict(extra="forbid")

    url: str
    row_count: int = Field(ge=1)
    response_sha256: str = Field(min_length=64, max_length=64)


class TaiwanUniverseSnapshot(BaseModel):
    """Schema-first manifest and member catalogue for a current Taiwan capture."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["taiwan_current_universe.v1"] = "taiwan_current_universe.v1"
    as_of: date
    sources: dict[TaiwanMarket, TaiwanUniverseSource]
    members: list[TaiwanUniverseMember]

    @model_validator(mode="after")
    def validate_unique_members(self) -> "TaiwanUniverseSnapshot":
        keys = [(member.market, member.ticker) for member in self.members]
        if len(keys) != len(set(keys)):
            raise ValueError("snapshot contains duplicate market/ticker members")
        if not self.members:
            raise ValueError("snapshot must contain at least one member")
        return self

    def members_frame(self) -> pd.DataFrame:
        """Return a stable catalogue suitable for a local, untracked CSV."""

        rows = [member.model_dump(mode="json") for member in self.members]
        return pd.DataFrame(rows).sort_values(["market", "ticker"], kind="mergesort")

    def manifest(self) -> dict[str, object]:
        """Return public-safe metadata without provider response rows."""

        members = self.members_frame()
        counts = {market: int((members["market"] == market).sum()) for market in SOURCE_URLS}
        canonical = members.to_csv(index=False, lineterminator="\n").encode("utf-8")
        return {
            "schema_version": self.schema_version,
            "as_of": self.as_of.isoformat(),
            "member_count": len(self.members),
            "member_count_by_market": counts,
            "member_catalogue_sha256": hashlib.sha256(canonical).hexdigest(),
            "sources": {
                market: source.model_dump(mode="json") for market, source in self.sources.items()
            },
            "limitations": [
                "This is a current-universe capture, not point-in-time historical membership.",
                "It does not establish delisting, removal, suspension, or historical availability dates.",
                "Keep the provider-derived member catalogue outside version control until rights are reviewed.",
            ],
        }


def capture_current_taiwan_universe(*, fetch_json: JsonFetcher | None = None) -> TaiwanUniverseSnapshot:
    """Fetch and normalize the current TWSE, TPEx, and emerging catalogues."""

    fetch = fetch_json or _fetch_json
    raw_by_market = {market: fetch(url) for market, url in SOURCE_URLS.items()}
    sources = {
        market: TaiwanUniverseSource(
            url=SOURCE_URLS[market],
            row_count=len(rows),
            response_sha256=_response_sha256(rows),
        )
        for market, rows in raw_by_market.items()
    }
    as_of_dates = {
        market: _extract_as_of(rows, market=market)
        for market, rows in raw_by_market.items()
    }
    distinct_dates = set(as_of_dates.values())
    if len(distinct_dates) != 1:
        raise ValueError(f"official current-universe sources disagree on as_of date: {as_of_dates}")

    members = [
        _normalize_member(row, market=market)
        for market, rows in raw_by_market.items()
        for row in rows
    ]
    return TaiwanUniverseSnapshot(
        as_of=next(iter(distinct_dates)),
        sources=sources,
        members=members,
    )


def write_snapshot(
    snapshot: TaiwanUniverseSnapshot,
    *,
    members_output: Path,
    manifest_output: Path,
) -> dict[str, object]:
    """Write the untracked local catalogue and its shareable manifest."""

    members_output.parent.mkdir(parents=True, exist_ok=True)
    snapshot.members_frame().to_csv(members_output, index=False)
    manifest = snapshot.manifest()
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _fetch_json(url: str) -> list[dict[str, object]]:
    request = Request(url, headers=HTTP_HEADERS)
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed official HTTPS endpoints
        payload = json.load(response)
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"expected a JSON array of objects from {url}")
    return [dict(row) for row in payload]


def _normalize_member(row: Mapping[str, object], *, market: TaiwanMarket) -> TaiwanUniverseMember:
    if market == "twse":
        ticker = _field(row, "公司代號")
        company_name = _field(row, "公司名稱")
        industry_code = _optional_field(row, "產業別")
        listing_date = _parse_date(_field(row, "上市日期"), field_name="上市日期")
    else:
        ticker = _field(row, "SecuritiesCompanyCode")
        company_name = _field(row, "CompanyName")
        industry_code = _optional_field(row, "SecuritiesIndustryCode")
        listing_date = _parse_date(_field(row, "DateOfListing"), field_name="DateOfListing")
    return TaiwanUniverseMember(
        ticker=ticker,
        market=market,
        company_name=company_name,
        industry_code=industry_code,
        listing_date=listing_date,
        provider_symbol=_provider_symbol(ticker, market=market),
    )


def _extract_as_of(rows: list[dict[str, object]], *, market: TaiwanMarket) -> date:
    if not rows:
        raise ValueError(f"{market} returned an empty current-universe response")
    field_name = "出表日期" if market == "twse" else "Date"
    dates = {_parse_date(_field(row, field_name), field_name=field_name) for row in rows}
    if len(dates) != 1:
        raise ValueError(f"{market} response has inconsistent {field_name} values")
    return next(iter(dates))


def _field(row: Mapping[str, object], name: str) -> str:
    value = row.get(name)
    if value is None or not str(value).strip():
        raise ValueError(f"official response is missing required field {name!r}")
    return str(value).strip()


def _optional_field(row: Mapping[str, object], name: str) -> str | None:
    value = row.get(name)
    return str(value).strip() if value is not None and str(value).strip() else None


def _parse_date(value: str, *, field_name: str) -> date:
    digits = value.strip().replace("/", "").replace("-", "")
    if not digits.isdigit() or len(digits) not in {7, 8}:
        raise ValueError(f"{field_name} must be a YYYYMMDD or ROC YYYMMDD date")
    if len(digits) == 7:
        digits = str(int(digits[:3]) + 1911) + digits[3:]
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid date: {value!r}") from exc


def _provider_symbol(ticker: str, *, market: TaiwanMarket) -> str:
    if market == "twse":
        return f"{ticker}.TW"
    if market == "tpex":
        return f"{ticker}.TWO"
    return f"{ticker}.EMERGING"


def _response_sha256(rows: list[dict[str, object]]) -> str:
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
