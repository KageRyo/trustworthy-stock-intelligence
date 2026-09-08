"""Tests for point-in-time universe membership handling."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from tsi.data.universe import (
    PointInTimeMembership,
    PointInTimeSecurityMembership,
    PointInTimeUniverse,
    PointInTimeUniverseV2,
    filter_frame_by_point_in_time_universe,
    load_point_in_time_universe,
    load_point_in_time_universe_v2,
    migrate_v1_to_v2,
)


def _universe() -> PointInTimeUniverse:
    return PointInTimeUniverse(
        name="fixture",
        source="fixture-source",
        source_license="fixture-only",
        memberships=[
            {"ticker": "AAA", "valid_from": "2020-01-01", "valid_to": "2021-01-01"},
            {"ticker": "AAA", "valid_from": "2021-01-01", "valid_to": None},
            {"ticker": "00878", "valid_from": "2020-06-01", "valid_to": None},
        ],
    )


def test_active_tickers_use_half_open_intervals_and_preserve_symbols() -> None:
    universe = _universe()

    assert universe.active_tickers(date(2019, 12, 31)) == ()
    assert universe.active_tickers("2020-06-01") == ("00878", "AAA")
    assert universe.active_tickers("2021-01-01") == ("00878", "AAA")
    assert universe.manifest()["ticker_count"] == 2
    assert len(universe.membership_fingerprint()) == 64


def test_overlapping_intervals_are_rejected() -> None:
    with pytest.raises(ValueError, match="overlapping"):
        PointInTimeUniverse(
            name="fixture",
            source="fixture-source",
            source_license="fixture-only",
            memberships=[
                {"ticker": "AAA", "valid_from": "2020-01-01", "valid_to": "2021-01-01"},
                {"ticker": "AAA", "valid_from": "2020-12-01", "valid_to": None},
            ],
        )


def test_filter_frame_uses_row_date_membership() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2019-12-31", "2020-06-01", "2021-01-01", "2020-06-01"],
            "ticker": ["AAA", "AAA", "AAA", "00878"],
            "close": [1.0, 2.0, 3.0, 4.0],
        }
    )

    filtered = filter_frame_by_point_in_time_universe(frame, _universe())

    assert filtered["close"].tolist() == [2.0, 3.0, 4.0]


def test_loader_requires_source_metadata_and_keeps_leading_zeroes(tmp_path) -> None:
    path = tmp_path / "membership.csv"
    path.write_text(
        "ticker,valid_from,valid_to\n00878,2020-01-01,\n",
        encoding="utf-8",
    )

    universe = load_point_in_time_universe(
        path,
        name="taiwan_fixture",
        source="official-archive",
        source_license="research-only",
    )

    assert universe.memberships[0].ticker == "00878"
    assert universe.manifest()["source_license"] == "research-only"


def test_membership_interval_requires_later_end_date() -> None:
    with pytest.raises(ValueError, match="valid_to"):
        PointInTimeMembership(
            ticker="AAA",
            valid_from="2021-01-02",
            valid_to="2021-01-01",
        )


def _universe_v2() -> PointInTimeUniverseV2:
    return PointInTimeUniverseV2(
        name="fixture-v2",
        source="licensed-fixture",
        source_license="research-only",
        memberships=[
            {
                "security_id": "security-a",
                "ticker": "AAA",
                "provider_symbol": "AAA",
                "market": "us",
                "valid_from": "2020-01-01",
                "valid_to": "2021-01-01",
                "known_at": "2020-01-01",
                "change_reason": "initial_listing",
            },
            {
                "security_id": "security-a",
                "ticker": "AAB",
                "provider_symbol": "AAB",
                "market": "us",
                "valid_from": "2021-01-01",
                "valid_to": "2022-01-01",
                "known_at": "2021-02-01",
                "change_reason": "rename",
            },
            {
                "security_id": "security-b",
                "ticker": "AAA",
                "provider_symbol": "AAA",
                "market": "us",
                "valid_from": "2022-01-01",
                "valid_to": None,
                "known_at": "2022-01-01",
                "change_reason": "ticker_reuse",
            },
            {
                "security_id": "security-tw",
                "ticker": "00878",
                "provider_symbol": "00878.TW",
                "market": "twse",
                "valid_from": "2020-01-01",
                "valid_to": None,
                "known_at": "2020-01-01",
                "change_reason": "initial_listing",
            },
        ],
    )


def test_v2_tracks_identity_rename_reuse_and_known_at_without_leakage() -> None:
    universe = _universe_v2()

    assert universe.active_tickers("2020-06-01") == ("00878", "AAA")
    assert universe.active_tickers("2021-01-15") == ("00878",)
    assert universe.active_tickers("2021-02-01") == ("00878", "AAB")
    assert universe.active_tickers("2022-01-01") == ("00878", "AAA")
    assert universe.manifest()["security_count"] == 3
    assert universe.manifest()["schema_version"] == "point_in_time_universe.v2"

    frame = pd.DataFrame(
        {
            "date": ["2021-01-15", "2021-02-01", "2022-01-01"],
            "ticker": ["AAB", "AAB", "AAA"],
            "close": [1.0, 2.0, 3.0],
        }
    )
    filtered = filter_frame_by_point_in_time_universe(frame, universe)

    assert filtered["close"].tolist() == [2.0, 3.0]


def test_v2_rejects_overlapping_identity_and_ambiguous_symbol_intervals() -> None:
    with pytest.raises(ValueError, match="overlapping identity"):
        PointInTimeUniverseV2(
            name="fixture",
            source="source",
            source_license="license",
            memberships=[
                {
                    "security_id": "security-a",
                    "ticker": "AAA",
                    "valid_from": "2020-01-01",
                    "valid_to": "2021-02-01",
                    "known_at": "2020-01-01",
                },
                {
                    "security_id": "security-a",
                    "ticker": "AAB",
                    "valid_from": "2021-01-01",
                    "valid_to": None,
                    "known_at": "2021-01-01",
                },
            ],
        )

    with pytest.raises(ValueError, match="ambiguous ticker"):
        PointInTimeUniverseV2(
            name="fixture",
            source="source",
            source_license="license",
            memberships=[
                {
                    "security_id": "security-a",
                    "ticker": "AAA",
                    "valid_from": "2020-01-01",
                    "valid_to": "2022-01-01",
                    "known_at": "2020-01-01",
                },
                {
                    "security_id": "security-b",
                    "ticker": "AAA",
                    "valid_from": "2021-01-01",
                    "valid_to": None,
                    "known_at": "2021-01-01",
                },
            ],
        )


def test_v2_loader_preserves_leading_zero_and_open_intervals(tmp_path) -> None:
    path = tmp_path / "membership-v2.csv"
    path.write_text(
        "security_id,ticker,provider_symbol,market,valid_from,valid_to,known_at\n"
        "security-tw,00878,00878.TW,twse,2020-01-01,,2020-01-01\n",
        encoding="utf-8",
    )

    universe = load_point_in_time_universe_v2(
        path,
        name="taiwan_fixture",
        source="official-archive",
        source_license="research-only",
    )

    assert universe.memberships[0].ticker == "00878"
    assert universe.memberships[0].valid_to is None
    assert universe.memberships[0].provider_symbol == "00878.TW"


def test_v1_migration_is_explicit_and_marks_legacy_identity() -> None:
    migrated = migrate_v1_to_v2(_universe())

    migrated_taiwan = next(
        membership for membership in migrated.memberships if membership.ticker == "00878"
    )
    assert migrated_taiwan.security_id == "legacy:00878"
    assert migrated_taiwan.known_at == migrated_taiwan.valid_from
    assert migrated_taiwan.change_reason == "migrated_from_point_in_time_universe.v1"


def test_v2_membership_requires_typed_identifiers() -> None:
    with pytest.raises(ValueError, match="security_id"):
        PointInTimeSecurityMembership(
            security_id=" ",
            ticker="AAA",
            valid_from="2020-01-01",
            known_at="2020-01-01",
        )
