"""Tests for TWSE T86 and MI_MARGN chip adapters and the resumable archive."""

from __future__ import annotations

from pathlib import Path

import pytest

from tsi.data.twse_chips import (
    MARGIN_TABLE_FIELDS,
    T86_URL,
    TWSEChipSchemaError,
    archive_path,
    backfill_chip_archive,
    chip_request,
    load_chip_archive,
    read_archive_payload,
    parse_institutional_payload,
    parse_margin_payload,
    write_archive_payload,
)

LEGACY_T86_FIELDS = [
    "證券代號",
    "證券名稱",
    "外資買進股數",
    "外資賣出股數",
    "外資買賣超股數",
    "投信買進股數",
    "投信賣出股數",
    "投信買賣超股數",
    "自營商買賣超股數",
    "三大法人買賣超股數",
]
SPLIT_T86_FIELDS = [
    "證券代號",
    "證券名稱",
    "外陸資買賣超股數(不含外資自營商)",
    "外資自營商買賣超股數",
    "投信買賣超股數",
    "自營商買賣超股數",
    "三大法人買賣超股數",
]


def _legacy_t86(date: str = "20150105") -> dict[str, object]:
    return {
        "stat": "OK",
        "date": date,
        "fields": LEGACY_T86_FIELDS,
        "data": [
            ["2330  ", "台積電", "1,000", "400", "600", "10", "0", "10", "-5", "605"],
            ["00981A", "主動統一", "0", "0", "0", "0", "0", "0", "2,000", "2,000"],
        ],
    }


def _split_t86(date: str = "20261006") -> dict[str, object]:
    return {
        "stat": "OK",
        "date": date,
        "fields": SPLIT_T86_FIELDS,
        "data": [["2330", "台積電", "-3,000", "200", "50", "-1,000", "-3,750"]],
    }


def _margin(date: str = "20261006") -> dict[str, object]:
    margin = ["5", "3", "0", "100", "102", "9,000"]
    short = ["1", "2", "0", "20", "19", "9,000"]
    row = ["2330", "台積電", *margin, *short, "4", " "]
    return {
        "stat": "OK",
        "date": date,
        "tables": [
            {"title": "信用交易統計", "fields": ["項目", "買進"], "data": [["融資", "1"]]},
            {"title": "融資融券彙總 (全部)", "fields": MARGIN_TABLE_FIELDS, "data": [row]},
        ],
    }


def test_legacy_and_split_foreign_columns_share_one_meaning() -> None:
    legacy = parse_institutional_payload(_legacy_t86())
    split = parse_institutional_payload(_split_t86())

    assert [record.ticker for record in legacy] == ["2330", "00981A"]
    assert legacy[0].date == "2015-01-05"
    assert legacy[0].foreign_net == 600.0
    assert legacy[0].investment_trust_net == 10.0
    assert legacy[1].dealer_net == 2000.0
    assert split[0].foreign_net == -2800.0
    assert split[0].total_net == -3750.0


def test_no_data_status_returns_no_records() -> None:
    payload = {"stat": "很抱歉，沒有符合條件的資料!"}

    assert parse_institutional_payload(payload) == []
    assert parse_margin_payload(payload) == []


def test_institutional_schema_drift_is_rejected() -> None:
    payload = _split_t86()
    payload["fields"] = ["證券代號", "證券名稱", "外資淨買", "投信買賣超股數"]
    payload["data"] = [["2330", "台積電", "1", "2"]]

    with pytest.raises(TWSEChipSchemaError, match="foreign-investor"):
        parse_institutional_payload(payload)


def test_margin_payload_reads_balances_by_validated_position() -> None:
    records = parse_margin_payload(_margin())

    assert len(records) == 1
    assert records[0].date == "2026-10-06"
    assert records[0].margin_balance == 102.0
    assert records[0].short_balance == 19.0
    assert records[0].margin_short_offset == 4.0


def test_margin_payload_without_expected_table_is_rejected() -> None:
    payload = _margin()
    payload["tables"] = payload["tables"][:1]

    with pytest.raises(TWSEChipSchemaError, match="margin table"):
        parse_margin_payload(payload)


def test_chip_request_uses_compact_dates() -> None:
    url, params = chip_request("institutional", "2026-10-06")

    assert url == T86_URL
    assert params == {"date": "20261006", "selectType": "ALLBUT0999", "response": "json"}
    assert chip_request("margin", "2015-01-05")[1]["selectType"] == "ALL"


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def time(self) -> float:
        return self.now


def test_backfill_spaces_requests_retries_invalid_payloads_and_resumes(tmp_path: Path) -> None:
    responses = {
        ("institutional", "20261005"): [{"stat": "OK"}, _split_t86("20261005")],
        ("margin", "20261005"): [_margin("20261005")],
        ("institutional", "20261006"): [{"stat": "很抱歉，沒有符合條件的資料!"}, _split_t86()],
        ("margin", "20261006"): [{"stat": "OK", "date": "20261006", "tables": []}] * 2,
    }
    calls: list[tuple[str, str]] = []

    def fetcher(url: str, params: dict[str, str]) -> dict[str, object]:
        kind = "institutional" if url == T86_URL else "margin"
        calls.append((kind, params["date"]))
        return responses[(kind, params["date"])].pop(0)

    clock = _Clock()
    report = backfill_chip_archive(
        ["2026-10-05", "2026-10-06"],
        archive_dir=tmp_path,
        fetcher=fetcher,
        min_interval_seconds=2.0,
        max_attempts=2,
        backoff_seconds=10.0,
        sleep=clock.sleep,
        clock=clock.time,
    )

    assert report.fetched == 3
    assert list(report.failed) == ["margin:2026-10-06"]
    assert 10.0 in clock.sleeps
    assert all(seconds <= 10.0 for seconds in clock.sleeps)
    assert not archive_path(tmp_path, "margin", "2026-10-06").exists()
    assert not list(tmp_path.rglob("*.tmp"))
    saved = read_archive_payload(archive_path(tmp_path, "institutional", "2026-10-05"))
    assert saved["date"] == "20261005"

    calls.clear()
    responses[("margin", "20261006")] = [_margin()]
    resumed = backfill_chip_archive(
        ["2026-10-05", "2026-10-06"],
        archive_dir=tmp_path,
        fetcher=fetcher,
        sleep=clock.sleep,
        clock=clock.time,
    )

    assert calls == [("margin", "20261006")]
    assert resumed.cached == 3
    assert resumed.fetched == 1


def test_load_chip_archive_builds_tables_and_coverage(tmp_path: Path) -> None:
    for kind, payload, date in (
        ("institutional", _legacy_t86("20150105"), "2015-01-05"),
        ("institutional", {"stat": "很抱歉，沒有符合條件的資料!"}, "2015-01-06"),
        ("margin", _margin("20150105"), "2015-01-05"),
    ):
        write_archive_payload(archive_path(tmp_path, kind, date), payload)

    tables = load_chip_archive(tmp_path)

    assert tables.institutional_dates == ["2015-01-05"]
    assert tables.margin_dates == ["2015-01-05"]
    assert tables.institutional["ticker"].tolist() == ["2330", "00981A"]
    assert tables.margin.loc[0, "margin_balance"] == 102.0
