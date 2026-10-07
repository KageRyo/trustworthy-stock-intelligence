"""Tests for leakage-safe market-relative features."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsi.features.market import MARKET_FEATURE_COLUMNS, build_market_features

DATES = pd.bdate_range("2024-01-01", periods=90)


def _prices(values: np.ndarray, ticker: str, dates: pd.DatetimeIndex = DATES) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "ticker": ticker, "adj_close": values})


def _market(days: int = len(DATES), seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, days)))


def _reference(*, sector_start: int = 0) -> pd.DataFrame:
    market = _market()
    sector = _market(seed=4)
    vix = 15.0 + np.arange(len(DATES)) * 0.1
    return pd.concat(
        [
            _prices(market, "SPY"),
            _prices(sector[sector_start:], "XLK", DATES[sector_start:]),
            _prices(vix, "^VIX"),
        ],
        ignore_index=True,
    )


def _build(stocks: pd.DataFrame, reference: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    return build_market_features(
        stocks,
        reference,
        market_symbol="SPY",
        volatility_symbol="^VIX",
        sector_etf_by_ticker={"AAPL": "XLK"},
        **kwargs,
    )


def test_excess_return_and_beta_match_constructed_series() -> None:
    market = _market()
    market_return = pd.Series(market).pct_change().fillna(0).to_numpy()
    stock = 50.0 * np.cumprod(1 + 2.0 * market_return)

    features = _build(_prices(stock, "AAPL"), _reference())
    row = features.iloc[70]

    expected_stock_5d = stock[70] / stock[65] - 1
    expected_market_5d = market[70] / market[65] - 1
    assert row["excess_return_5d"] == pytest.approx(expected_stock_5d - expected_market_5d)
    assert row["market_return_5d"] == pytest.approx(expected_market_5d)
    assert row["beta_60d"] == pytest.approx(2.0)
    assert row["vix_level"] == pytest.approx(15.0 + 70 * 0.1)
    assert row["vix_change_5d"] == pytest.approx((15.0 + 7.0) / (15.0 + 6.5) - 1)
    assert row["market_drawdown_from_60d_high"] <= 0
    assert features["beta_60d"].iloc[:60].isna().all()


def test_features_at_date_ignore_future_reference_prices() -> None:
    stocks = _prices(_market(seed=9), "AAPL")
    reference = _reference()
    baseline = _build(stocks, reference)

    shocked = reference.copy()
    future = shocked["date"] > DATES[70]
    shocked.loc[future, "adj_close"] *= 3.0
    perturbed = _build(stocks, shocked)

    pd.testing.assert_frame_equal(
        baseline.loc[baseline["date"] <= DATES[70], MARKET_FEATURE_COLUMNS],
        perturbed.loc[perturbed["date"] <= DATES[70], MARKET_FEATURE_COLUMNS],
    )


def test_prior_session_reference_excludes_same_date_close() -> None:
    reference = _reference()
    stocks = _prices(_market(seed=9), "2330")

    features = build_market_features(
        stocks,
        reference,
        market_symbol="SPY",
        volatility_symbol="^VIX",
        sector_etf_by_ticker={},
        same_session_reference=False,
    )

    assert features["ticker"].iloc[0] == "2330"
    assert features["vix_level"].iloc[70] == pytest.approx(15.0 + 69 * 0.1)
    assert np.isnan(features["vix_level"].iloc[0])


def test_sector_excess_falls_back_to_market_before_etf_and_for_unmapped_tickers() -> None:
    reference = _reference(sector_start=40)
    stocks = pd.concat(
        [_prices(_market(seed=9), "AAPL"), _prices(_market(seed=10), "BK")], ignore_index=True
    )

    features = _build(stocks, reference)
    aapl = features[features["ticker"] == "AAPL"].reset_index(drop=True)
    bk = features[features["ticker"] == "BK"].reset_index(drop=True)

    assert aapl["sector_excess_return_20d"].iloc[30] == pytest.approx(
        aapl["excess_return_20d"].iloc[30]
    )
    assert aapl["sector_excess_return_20d"].iloc[80] != pytest.approx(
        aapl["excess_return_20d"].iloc[80]
    )
    pd.testing.assert_series_equal(
        bk["sector_excess_return_5d"], bk["excess_return_5d"], check_names=False
    )


def test_stale_reference_beyond_tolerance_is_missing() -> None:
    reference = _reference()
    gap = (reference["ticker"] == "SPY") & reference["date"].between(DATES[50], DATES[70])
    reference = reference[~gap]

    features = _build(_prices(_market(seed=9), "AAPL"), reference, max_reference_staleness_days=7)

    assert features["market_return_5d"].iloc[52:72].isna().any()
    assert not np.isnan(features["market_return_5d"].iloc[52])
    assert np.isnan(features["market_return_5d"].iloc[65])


def test_missing_market_symbol_is_rejected() -> None:
    stocks = _prices(_market(), "AAPL")
    reference = _reference()

    with pytest.raises(ValueError, match="QQQ"):
        build_market_features(
            stocks,
            reference,
            market_symbol="QQQ",
            volatility_symbol=None,
            sector_etf_by_ticker={},
        )


def test_missing_volatility_symbol_leaves_vix_features_empty() -> None:
    features = build_market_features(
        _prices(_market(seed=9), "AAPL"),
        _reference(),
        market_symbol="SPY",
        volatility_symbol=None,
        sector_etf_by_ticker={},
    )

    assert features["vix_level"].isna().all()
    assert features["excess_return_5d"].notna().iloc[10:].all()
