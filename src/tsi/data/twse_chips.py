"""TWSE institutional-flow (T86) and margin-balance (MI_MARGN) daily adapters.

Both endpoints return one trading date for every listed security. Raw payloads
are cached per date so a long backfill can resume and so parsing can be rerun
when the schema mapping changes. Payloads pass explicit Pydantic schemas before
business logic reads them.

T86 renamed its foreign-investor columns on 2018-01-02: "外資" became
"外陸資(不含外資自營商)" plus a separate "外資自營商" column. ``foreign_net`` sums
the two newer columns so it keeps the pre-2018 meaning. Shares are reported in
shares for T86 and in lots (1,000 shares) for MI_MARGN.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
import gzip
import json
from pathlib import Path
import time
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi.data.download import fetch_json, parse_taiwan_number

T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
MI_MARGN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
ChipKind = Literal["institutional", "margin"]
CHIP_KINDS: tuple[ChipKind, ...] = ("institutional", "margin")
INSTITUTIONAL_COLUMNS = [
    "date",
    "ticker",
    "foreign_net",
    "investment_trust_net",
    "dealer_net",
    "total_net",
]
MARGIN_COLUMNS = ["date", "ticker", "margin_balance", "short_balance", "margin_short_offset"]
MARGIN_TABLE_FIELDS = [
    "代號",
    "名稱",
    "買進",
    "賣出",
    "現金償還",
    "前日餘額",
    "今日餘額",
    "次一營業日限額",
    "買進",
    "賣出",
    "現券償還",
    "前日餘額",
    "今日餘額",
    "次一營業日限額",
    "資券互抵",
    "註記",
]
_MARGIN_BALANCE_INDEX = 6
_SHORT_BALANCE_INDEX = 12
_OFFSET_INDEX = 14
_FOREIGN_SPLIT_FIELDS = ("外陸資買賣超股數(不含外資自營商)", "外資自營商買賣超股數")
_FOREIGN_LEGACY_FIELD = "外資買賣超股數"
_TRUST_FIELD = "投信買賣超股數"
_DEALER_FIELD = "自營商買賣超股數"
_TOTAL_FIELD = "三大法人買賣超股數"

JsonFetcher = Callable[[str, dict[str, str]], dict[str, object]]


class TWSEChipSchemaError(ValueError):
    """Raised when a TWSE chip payload does not match the expected columns."""


class TWSEInstitutionalResponse(BaseModel):
    """Schema for a TWSE T86 daily institutional trading response."""

    model_config = ConfigDict(extra="ignore")

    stat: str
    date: str | None = None
    fields: list[str] = Field(default_factory=list)
    data: list[list[str]] = Field(default_factory=list)


class TWSEMarginTable(BaseModel):
    """One table inside a TWSE MI_MARGN response."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    fields: list[str] = Field(default_factory=list)
    data: list[list[str]] = Field(default_factory=list)


class TWSEMarginResponse(BaseModel):
    """Schema for a TWSE MI_MARGN daily margin-trading response."""

    model_config = ConfigDict(extra="ignore")

    stat: str
    date: str | None = None
    tables: list[TWSEMarginTable] = Field(default_factory=list)


class InstitutionalFlowRecord(BaseModel):
    """Net shares traded by institutional investors for one ticker and date."""

    model_config = ConfigDict(frozen=True)

    date: str
    ticker: str
    foreign_net: float
    investment_trust_net: float
    dealer_net: float
    total_net: float


class MarginBalanceRecord(BaseModel):
    """End-of-day margin and short balances, in lots, for one ticker and date."""

    model_config = ConfigDict(frozen=True)

    date: str
    ticker: str
    margin_balance: float
    short_balance: float
    margin_short_offset: float


def _iso_date(compact: str) -> str:
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"


def _number(value: str, *, column: str, ticker: str) -> float:
    parsed = parse_taiwan_number(value)
    if parsed is None:
        raise TWSEChipSchemaError(f"Non-numeric {column} for {ticker}: {value!r}")
    return parsed


def parse_institutional_payload(payload: dict[str, object]) -> list[InstitutionalFlowRecord]:
    """Normalize one T86 payload; a non-OK status means no trading data for the date."""

    response = TWSEInstitutionalResponse.model_validate(payload)
    if response.stat != "OK":
        return []
    if not response.date:
        raise TWSEChipSchemaError("T86 response has no date")
    index = {name: position for position, name in enumerate(response.fields)}
    required = ["證券代號", _TRUST_FIELD, _DEALER_FIELD, _TOTAL_FIELD]
    if all(name in index for name in _FOREIGN_SPLIT_FIELDS):
        foreign_fields: Sequence[str] = _FOREIGN_SPLIT_FIELDS
    elif _FOREIGN_LEGACY_FIELD in index:
        foreign_fields = (_FOREIGN_LEGACY_FIELD,)
    else:
        raise TWSEChipSchemaError(f"T86 response has no foreign-investor column: {response.fields}")
    missing = [name for name in required if name not in index]
    if missing:
        raise TWSEChipSchemaError(f"T86 response is missing columns: {', '.join(missing)}")

    trading_date = _iso_date(response.date)
    records: list[InstitutionalFlowRecord] = []
    for row in response.data:
        if len(row) != len(response.fields):
            raise TWSEChipSchemaError(f"T86 row width {len(row)} != {len(response.fields)}")
        ticker = row[index["證券代號"]].strip().upper()

        def value(name: str, ticker: str = ticker, row: list[str] = row) -> float:
            return _number(row[index[name]], column=name, ticker=ticker)

        records.append(
            InstitutionalFlowRecord(
                date=trading_date,
                ticker=ticker,
                foreign_net=sum(value(name) for name in foreign_fields),
                investment_trust_net=value(_TRUST_FIELD),
                dealer_net=value(_DEALER_FIELD),
                total_net=value(_TOTAL_FIELD),
            )
        )
    return records


def parse_margin_payload(payload: dict[str, object]) -> list[MarginBalanceRecord]:
    """Normalize one MI_MARGN payload; a non-OK status means no trading data for the date."""

    response = TWSEMarginResponse.model_validate(payload)
    if response.stat != "OK":
        return []
    if not response.date:
        raise TWSEChipSchemaError("MI_MARGN response has no date")
    tables = [table for table in response.tables if table.fields == MARGIN_TABLE_FIELDS]
    if len(tables) != 1:
        raise TWSEChipSchemaError("MI_MARGN response has no single per-security margin table")

    trading_date = _iso_date(response.date)
    records: list[MarginBalanceRecord] = []
    for row in tables[0].data:
        if len(row) != len(MARGIN_TABLE_FIELDS):
            raise TWSEChipSchemaError(
                f"MI_MARGN row width {len(row)} != {len(MARGIN_TABLE_FIELDS)}"
            )
        ticker = row[0].strip().upper()
        records.append(
            MarginBalanceRecord(
                date=trading_date,
                ticker=ticker,
                margin_balance=_number(row[_MARGIN_BALANCE_INDEX], column="融資今日餘額", ticker=ticker),
                short_balance=_number(row[_SHORT_BALANCE_INDEX], column="融券今日餘額", ticker=ticker),
                margin_short_offset=_number(row[_OFFSET_INDEX], column="資券互抵", ticker=ticker),
            )
        )
    return records


def chip_request(kind: ChipKind, trading_date: str) -> tuple[str, dict[str, str]]:
    """Return the endpoint URL and query parameters for ``YYYY-MM-DD``."""

    compact = pd.Timestamp(trading_date).strftime("%Y%m%d")
    if kind == "institutional":
        return T86_URL, {"date": compact, "selectType": "ALLBUT0999", "response": "json"}
    if kind == "margin":
        return MI_MARGN_URL, {"date": compact, "selectType": "ALL", "response": "json"}
    raise ValueError(f"Unsupported chip kind: {kind}")


def archive_path(archive_dir: Path, kind: ChipKind, trading_date: str) -> Path:
    return archive_dir / kind / f"{pd.Timestamp(trading_date).strftime('%Y%m%d')}.json.gz"


def write_archive_payload(path: Path, payload: dict[str, object]) -> None:
    """Write a gzip JSON payload atomically so an interrupted run leaves no partial file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".tmp")
    partial.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8")))
    partial.replace(path)


def read_archive_payload(path: Path) -> dict[str, object]:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


@dataclass
class BackfillReport:
    """Outcome of :func:`backfill_chip_archive`."""

    fetched: int = 0
    cached: int = 0
    failed: dict[str, str] = field(default_factory=dict)


def backfill_chip_archive(
    trading_dates: Iterable[str],
    *,
    archive_dir: Path,
    kinds: Sequence[ChipKind] = CHIP_KINDS,
    fetcher: JsonFetcher = fetch_json,
    min_interval_seconds: float = 2.5,
    max_attempts: int = 4,
    backoff_seconds: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] | None = None,
) -> BackfillReport:
    """Fetch and cache raw payloads for dates not yet in ``archive_dir``.

    Requests are spaced at least ``min_interval_seconds`` apart. A payload is
    cached only after it validates and has rows, so a blocked, truncated, or
    not-yet-published response is retried with growing backoff and never
    poisons the archive. Pass exchange trading dates only.
    """

    report = BackfillReport()
    last_request = float("-inf")
    for trading_date in trading_dates:
        for kind in kinds:
            path = archive_path(archive_dir, kind, trading_date)
            if path.exists():
                report.cached += 1
                continue
            url, params = chip_request(kind, trading_date)
            error = ""
            for attempt in range(max_attempts):
                wait = min_interval_seconds - (clock() - last_request)
                if wait > 0:
                    sleep(wait)
                last_request = clock()
                try:
                    payload = fetcher(url, params)
                    if not parse_chip_payload(kind, payload):
                        raise TWSEChipSchemaError(f"{kind} has no rows for {trading_date}")
                except Exception as exc:  # noqa: BLE001 - retried, then reported
                    error = f"{type(exc).__name__}: {exc}"
                    if attempt + 1 < max_attempts:
                        sleep(backoff_seconds * (2**attempt))
                    continue
                write_archive_payload(path, payload)
                report.fetched += 1
                error = ""
                break
            if error:
                report.failed[f"{kind}:{trading_date}"] = error
            if log is not None and (report.fetched + len(report.failed)) % 50 == 0:
                log(f"{kind} {trading_date}: fetched={report.fetched} failed={len(report.failed)}")
    return report


def parse_chip_payload(
    kind: ChipKind, payload: dict[str, object]
) -> list[InstitutionalFlowRecord] | list[MarginBalanceRecord]:
    if kind == "institutional":
        return parse_institutional_payload(payload)
    if kind == "margin":
        return parse_margin_payload(payload)
    raise ValueError(f"Unsupported chip kind: {kind}")


@dataclass(frozen=True)
class ChipTables:
    """Normalized chip tables and the trading dates each archive covers."""

    institutional: pd.DataFrame
    margin: pd.DataFrame
    institutional_dates: list[str]
    margin_dates: list[str]


def load_chip_archive(archive_dir: Path) -> ChipTables:
    """Parse every cached payload into normalized institutional and margin tables."""

    frames: dict[ChipKind, pd.DataFrame] = {}
    dates: dict[ChipKind, list[str]] = {}
    for kind in CHIP_KINDS:
        columns = INSTITUTIONAL_COLUMNS if kind == "institutional" else MARGIN_COLUMNS
        rows: list[dict[str, object]] = []
        covered: list[str] = []
        for path in sorted((archive_dir / kind).glob("*.json.gz")):
            records = parse_chip_payload(kind, read_archive_payload(path))
            if records:
                covered.append(records[0].date)
            rows.extend(record.model_dump() for record in records)
        frame = pd.DataFrame(rows, columns=columns)
        frame["ticker"] = frame["ticker"].astype(str)
        frames[kind] = frame.drop_duplicates(["date", "ticker"], keep="last").reset_index(drop=True)
        dates[kind] = covered
    return ChipTables(
        institutional=frames["institutional"],
        margin=frames["margin"],
        institutional_dates=dates["institutional"],
        margin_dates=dates["margin"],
    )
