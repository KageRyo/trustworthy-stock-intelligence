"""Tests for range-based volatility features."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsi.features.volatility import RANGE_FEATURE_COLUMNS, build_range_features


def _ohlcv(days: int = 40, ticker: str = "2330") -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, days)))
    open_ = close * (1 + rng.normal(0, 0.005, days))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.02, days))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.02, days))
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=days),
            "ticker": ticker,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "adj_close": close,
            "volume": 1000.0,
        }
    )


def test_range_features_are_positive_and_warm_up_with_nan() -> None:
    features = build_range_features(_ohlcv())

    assert set(RANGE_FEATURE_COLUMNS) <= set(features.columns)
    assert features["atr_14_pct"].iloc[:13].isna().all()
    late = features.iloc[25:]
    for column in ("parkinson_vol_10d", "garman_klass_vol_10d", "atr_14_pct", "volatility_20d"):
        assert (late[column] > 0).all()
    assert (late["drawdown_from_20d_high"] <= 0).all()


def test_range_features_do_not_use_future_rows() -> None:
    base = _ohlcv()
    changed = base.copy()
    changed.loc[30:, ["open", "high", "low", "close", "adj_close"]] *= 3.0

    left = build_range_features(base).iloc[:30]
    right = build_range_features(changed).iloc[:30]

    pd.testing.assert_frame_equal(left[RANGE_FEATURE_COLUMNS], right[RANGE_FEATURE_COLUMNS])


def test_range_features_use_split_adjusted_prices() -> None:
    frame = _ohlcv()
    split = frame.copy()
    # A 2:1 split halves raw prices from row 20 on; adj_close stays continuous.
    split.loc[20:, ["open", "high", "low", "close"]] /= 2.0

    original = build_range_features(frame)
    adjusted = build_range_features(split)

    np.testing.assert_allclose(
        original["atr_14_pct"].iloc[30:], adjusted["atr_14_pct"].iloc[30:], rtol=1e-9
    )
    assert adjusted["atr_14_pct"].iloc[20:34].max() < 0.2


def test_range_features_are_computed_per_ticker() -> None:
    frame = pd.concat([_ohlcv(ticker="AAPL"), _ohlcv(ticker="00981A")], ignore_index=True)

    features = build_range_features(frame)

    first_rows = features.groupby("ticker").head(5)
    assert first_rows["parkinson_vol_10d"].isna().all()


def test_constant_prices_have_zero_range_volatility() -> None:
    frame = _ohlcv()
    frame[["open", "high", "low", "close", "adj_close"]] = 50.0

    features = build_range_features(frame).iloc[25:]

    for column in ("parkinson_vol_10d", "garman_klass_vol_10d", "atr_14_pct"):
        assert features[column].abs().max() == pytest.approx(0.0)
