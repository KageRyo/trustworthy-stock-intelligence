"""Tests for point-in-time universe membership handling."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from tsi.data.universe import (
    PointInTimeMembership,
    PointInTimeUniverse,
    filter_frame_by_point_in_time_universe,
    load_point_in_time_universe,
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
