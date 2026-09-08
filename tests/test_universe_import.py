"""Tests for typed membership archive import and coverage auditing."""

from __future__ import annotations

from datetime import UTC, datetime
import json

import pandas as pd
import pytest

from tsi.data.universe_import import (
    MembershipColumnMapping,
    MembershipCoverageAudit,
    MembershipImportConfig,
    MembershipImportError,
    audit_membership_coverage,
    import_membership_archive,
)


def _config() -> MembershipImportConfig:
    return MembershipImportConfig(
        name="licensed-fixture",
        source="licensed archive fixture",
        source_license="research-only; redistribution prohibited",
        retrieved_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        snapshot_date="2026-07-31",
        mapping=MembershipColumnMapping(
            mapping_version="fixture-mapping-1",
            security_id="entity_id",
            ticker="local_symbol",
            provider_symbol="vendor_code",
            market="market_name",
            valid_from="effective_start",
            valid_to="effective_end",
            known_at="announced_on",
        ),
    )


def test_import_maps_external_columns_and_records_redacted_provenance(tmp_path) -> None:
    path = tmp_path / "licensed-membership.csv"
    path.write_text(
        "entity_id,local_symbol,vendor_code,market_name,effective_start,effective_end,announced_on\n"
        "entity-101,AAA,AAA.US,us,2020-01-01,2021-01-01,2020-01-01\n"
        "entity-101,AAB,AAB.US,us,2021-01-01,2022-01-01,2021-02-01\n"
        "entity-202,AAA,AAA.US,us,2022-01-01,,2022-01-01\n"
        "entity-303,00878,00878.TW,twse,2020-01-01,,2020-01-01\n",
        encoding="utf-8",
    )

    result = import_membership_archive(path, _config())

    assert result.report.status == "valid"
    assert result.report.accepted_row_count == 4
    assert result.universe.active_tickers("2020-06-01") == ("00878", "AAA")
    assert result.universe.active_tickers("2021-01-15") == ("00878",)
    assert result.universe.active_tickers("2021-02-01") == ("00878", "AAB")
    assert result.universe.active_tickers("2022-01-01") == ("00878", "AAA")
    assert result.report.universe_manifest is not None
    assert result.report.universe_manifest["mapping_version"] == "fixture-mapping-1"
    assert (
        result.report.universe_manifest["source_license"]
        == "research-only; redistribution prohibited"
    )
    assert "entity-101" not in json.dumps(result.report.model_dump(mode="json"))


def test_import_fails_closed_for_duplicate_and_invalid_identity_rows(tmp_path) -> None:
    path = tmp_path / "invalid-membership.csv"
    path.write_text(
        "entity_id,local_symbol,vendor_code,market_name,effective_start,effective_end,announced_on\n"
        "entity-1,AAA,AAA.US,us,2020-01-01,2021-01-01,2020-01-01\n"
        "entity-1,AAA,AAA.US,us,2020-01-01,2021-01-01,2020-01-01\n"
        "entity-2,AAA,AAA.US,us,2020-06-01,,2020-06-01\n",
        encoding="utf-8",
    )

    with pytest.raises(MembershipImportError) as error:
        import_membership_archive(path, _config())

    assert error.value.report.status == "invalid"
    assert error.value.report.issue_counts["duplicate_row"] == 1
    assert error.value.report.issue_counts["ambiguous_symbol"] == 1


def test_import_reports_gaps_as_warnings_but_keeps_valid_archive(tmp_path) -> None:
    path = tmp_path / "gapped-membership.csv"
    path.write_text(
        "entity_id,local_symbol,vendor_code,market_name,effective_start,effective_end,announced_on\n"
        "entity-1,AAA,AAA.US,us,2020-01-01,2021-01-01,2020-01-01\n"
        "entity-1,AAA,AAA.US,us,2022-01-01,,2022-01-01\n",
        encoding="utf-8",
    )

    result = import_membership_archive(path, _config())

    assert result.report.status == "valid"
    assert result.report.issue_counts == {"identity_gap": 1}


def test_coverage_audit_separates_unavailable_data_nonmembership_and_unmatched() -> None:
    from tsi.data.universe import PointInTimeUniverseV2

    universe = PointInTimeUniverseV2(
        name="coverage-fixture",
        source="fixture",
        source_license="test-only",
        memberships=[
            {
                "security_id": "active-with-bars",
                "ticker": "AAA",
                "valid_from": "2020-01-01",
                "known_at": "2020-01-01",
            },
            {
                "security_id": "active-no-bars",
                "ticker": "DDD",
                "valid_from": "2020-01-01",
                "known_at": "2020-01-01",
            },
            {
                "security_id": "removed-with-bars",
                "ticker": "BBB",
                "valid_from": "2019-01-01",
                "valid_to": "2020-01-01",
                "known_at": "2019-01-01",
            },
            {
                "security_id": "removed-no-bars",
                "ticker": "CCC",
                "valid_from": "2018-01-01",
                "valid_to": "2019-01-01",
                "known_at": "2018-01-01",
            },
        ],
    )
    ohlcv = pd.DataFrame(
        {
            "date": [
                "2020-06-01",
                "2020-06-02",
                "2019-12-01",
                "2019-01-01",
                "2020-06-01",
            ],
            "ticker": ["AAA", "AAA", "BBB", "AAA", "UNKNOWN"],
            "open": [1, 1, 2, 1, 3],
            "high": [2, 2, 3, 2, 4],
            "low": [0, 0, 1, 0, 2],
            "close": [1.5, None, 2.5, 1.5, 3.5],
            "volume": [100, 100, 200, 100, 300],
        }
    )

    audit = audit_membership_coverage(universe, ohlcv, as_of="2020-06-03")

    assert isinstance(audit, MembershipCoverageAudit)
    assert audit.active_membership_count == 2
    assert audit.active_memberships_missing_bars == 1
    assert audit.unavailable_data_membership_count == 1
    assert audit.removed_or_delisted_membership_count == 2
    assert audit.removed_or_delisted_missing_bars == 1
    assert audit.nonmembership_row_count == 1
    assert audit.unmatched_identifier_count == 1
    assert audit.incomplete_ohlcv_row_count == 1
    assert audit.missing_ohlcv_by_column["close"] == 1
