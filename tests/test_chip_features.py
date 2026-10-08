"""Tests for leakage-safe Taiwan chip features."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsi.data.twse_chips import ChipTables
from tsi.features.chips import CHIP_FEATURE_COLUMNS, build_chip_features

DATES = pd.bdate_range("2024-01-01", periods=40)
ISO_DATES = [date.strftime("%Y-%m-%d") for date in DATES]


def _ohlcv(tickers: tuple[str, ...] = ("2330", "00981A")) -> pd.DataFrame:
    return pd.concat(
        [
            pd.DataFrame(
                {"date": DATES, "ticker": ticker, "adj_close": 100.0, "volume": 10_000.0}
            )
            for ticker in tickers
        ],
        ignore_index=True,
    )


def _chips(*, covered: list[str] = ISO_DATES, foreign: float = 1_000.0) -> ChipTables:
    institutional = pd.DataFrame(
        {
            "date": covered,
            "ticker": "2330",
            "foreign_net": foreign,
            "investment_trust_net": -500.0,
            "dealer_net": 0.0,
            "total_net": foreign - 500.0,
        }
    )
    margin = pd.DataFrame(
        {
            "date": covered,
            "ticker": "2330",
            "margin_balance": np.arange(len(covered), dtype=float) + 10.0,
            "short_balance": 2.0,
            "margin_short_offset": 0.0,
        }
    )
    sparse = {"date": covered[0], "ticker": "00981A"}
    institutional = pd.concat(
        [
            institutional,
            pd.DataFrame(
                [
                    {
                        **sparse,
                        "foreign_net": 7.0,
                        "investment_trust_net": 0.0,
                        "dealer_net": 0.0,
                        "total_net": 7.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    margin = pd.concat(
        [
            margin,
            pd.DataFrame(
                [
                    {
                        **sparse,
                        "margin_balance": 0.0,
                        "short_balance": 0.0,
                        "margin_short_offset": 0.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return ChipTables(
        institutional=institutional,
        margin=margin,
        institutional_dates=list(covered),
        margin_dates=list(covered),
    )


def test_flow_and_margin_features_match_constructed_values() -> None:
    features = build_chip_features(_ohlcv(("2330",)), _chips(), publication_lag=0)
    row = features.iloc[30]

    assert row["foreign_flow_5d"] == pytest.approx(5 * 1_000.0 / (5 * 10_000.0))
    assert row["trust_flow_20d"] == pytest.approx(-0.05)
    assert row["dealer_flow_5d"] == 0.0
    assert row["margin_change_5d"] == pytest.approx(5 * 1_000.0 / 50_000.0)
    assert row["margin_days_of_volume"] == pytest.approx(40.0 * 1_000.0 / 10_000.0)
    assert row["short_to_margin"] == pytest.approx(2.0 / 40.0)
    assert features["foreign_flow_20d"].iloc[:19].isna().all()


def test_default_lag_uses_only_previous_trading_date() -> None:
    lagged = build_chip_features(_ohlcv(("2330",)), _chips())
    same_day = build_chip_features(_ohlcv(("2330",)), _chips(), publication_lag=0)

    pd.testing.assert_series_equal(
        lagged["foreign_flow_5d"].iloc[1:].reset_index(drop=True),
        same_day["foreign_flow_5d"].iloc[:-1].reset_index(drop=True),
    )


def test_chip_values_on_or_after_row_date_do_not_change_lagged_features() -> None:
    baseline = _chips()
    shocked = _chips()
    on_or_after = pd.to_datetime(shocked.institutional["date"]) >= DATES[30]
    shocked.institutional.loc[on_or_after, "foreign_net"] = 1e9
    shocked.margin.loc[on_or_after.to_numpy(), "margin_balance"] = 1e9

    before = build_chip_features(_ohlcv(("2330",)), baseline)
    after = build_chip_features(_ohlcv(("2330",)), shocked)

    pd.testing.assert_frame_equal(
        before.loc[before["date"] <= DATES[30], CHIP_FEATURE_COLUMNS],
        after.loc[after["date"] <= DATES[30], CHIP_FEATURE_COLUMNS],
    )


def test_absent_known_ticker_is_zero_and_unknown_or_uncovered_values_are_missing() -> None:
    covered = ISO_DATES[:20] + ISO_DATES[21:]
    features = build_chip_features(
        _ohlcv(("2330", "00981A", "6147")), _chips(covered=covered), publication_lag=0
    )
    listed = features[features["ticker"] == "00981A"].reset_index(drop=True)
    flows = features[features["ticker"] == "2330"].reset_index(drop=True)
    tpex = features[features["ticker"] == "6147"].reset_index(drop=True)

    assert listed["ticker"].iloc[0] == "00981A"
    assert listed["foreign_flow_5d"].iloc[4] == pytest.approx(7.0 / 50_000.0)
    assert listed["foreign_flow_5d"].iloc[10] == 0.0
    assert listed["short_to_margin"].iloc[10] == 0.0
    assert flows["foreign_flow_5d"].iloc[20:25].isna().all()
    assert not np.isnan(flows["foreign_flow_5d"].iloc[25])
    assert tpex[CHIP_FEATURE_COLUMNS].isna().all().all()


def test_zero_volume_uncovered_bar_is_a_no_trade_day() -> None:
    covered = ISO_DATES[:20] + ISO_DATES[21:]
    ohlcv = _ohlcv(("2330",))
    ohlcv.loc[20, "volume"] = 0.0

    features = build_chip_features(ohlcv, _chips(covered=covered), publication_lag=0)

    assert features["foreign_flow_5d"].iloc[20:25].notna().all()
    assert features["foreign_flow_5d"].iloc[22] == pytest.approx(4 * 1_000.0 / 40_000.0)
    assert features["margin_days_of_volume"].iloc[20] == pytest.approx(
        29.0 * 1_000.0 / (19 * 10_000.0 / 20.0)
    )


def test_negative_lag_is_rejected() -> None:
    ohlcv = _ohlcv()
    chips = _chips()

    with pytest.raises(ValueError, match="publication_lag"):
        build_chip_features(ohlcv, chips, publication_lag=-1)
