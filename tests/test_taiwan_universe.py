"""Tests for current Taiwan universe capture schemas and boundaries."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from tsi.data.taiwan_universe import (
    TPEX_COMPANY_URL,
    TPEX_EMERGING_COMPANY_URL,
    TWSE_COMPANY_URL,
    capture_current_taiwan_universe,
    write_snapshot,
)


def _responses() -> dict[str, list[dict[str, object]]]:
    return {
        TWSE_COMPANY_URL: [
            {
                "出表日期": "1150808",
                "公司代號": "0050",
                "公司名稱": "測試上市公司",
                "產業別": "01",
                "上市日期": "20030630",
            }
        ],
        TPEX_COMPANY_URL: [
            {
                "Date": "1150808",
                "SecuritiesCompanyCode": "6488",
                "CompanyName": "測試上櫃公司",
                "SecuritiesIndustryCode": "22",
                "DateOfListing": "20160101",
            }
        ],
        TPEX_EMERGING_COMPANY_URL: [
            {
                "Date": "1150808",
                "SecuritiesCompanyCode": "5240",
                "CompanyName": "測試興櫃公司",
                "SecuritiesIndustryCode": "33",
                "DateOfListing": "20180101",
            }
        ],
    }


def test_current_capture_keeps_market_qualified_provider_symbols() -> None:
    responses = _responses()

    snapshot = capture_current_taiwan_universe(fetch_json=responses.__getitem__)

    assert snapshot.as_of.isoformat() == "2026-08-08"
    assert snapshot.members_frame()["provider_symbol"].tolist() == [
        "5240.EMERGING",
        "6488.TWO",
        "0050.TW",
    ]
    manifest = snapshot.manifest()
    assert manifest["member_count_by_market"] == {"twse": 1, "tpex": 1, "emerging": 1}
    assert len(manifest["member_catalogue_sha256"]) == 64
    assert "not point-in-time" in manifest["limitations"][0]


def test_current_capture_rejects_mixed_as_of_dates() -> None:
    responses = _responses()
    responses[TPEX_COMPANY_URL][0]["Date"] = "1150807"

    with pytest.raises(ValueError, match="disagree on as_of date"):
        capture_current_taiwan_universe(fetch_json=responses.__getitem__)


def test_write_snapshot_keeps_member_rows_and_manifest_separate(tmp_path) -> None:
    snapshot = capture_current_taiwan_universe(fetch_json=_responses().__getitem__)
    members_path = tmp_path / "current_taiwan_members.csv"
    manifest_path = tmp_path / "current_taiwan_manifest.json"

    manifest = write_snapshot(
        snapshot,
        members_output=members_path,
        manifest_output=manifest_path,
    )

    members = pd.read_csv(members_path, dtype={"ticker": "string"})
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert members["ticker"].tolist() == ["5240", "6488", "0050"]
    assert saved_manifest == manifest
    assert "company_name" not in json.dumps(saved_manifest, ensure_ascii=False)
