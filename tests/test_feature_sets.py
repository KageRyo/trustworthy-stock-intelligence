"""Tests for named feature sets and the shared feature-frame builder."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsi.data.market_reference import MarketReference
from tsi.features.market import MARKET_FEATURE_COLUMNS
from tsi.features.sets import (
    FEATURE_SETS,
    build_feature_frame,
    feature_set_requires_market_reference,
    resolve_feature_set,
)
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.features.volatility import RANGE_FEATURE_COLUMNS


def _ohlcv(tickers: tuple[str, ...] = ("AAPL", "2330"), days: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    frames = []
    for ticker in tickers:
        close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, days)))
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.bdate_range("2024-01-01", periods=days).astype(str),
                    "ticker": ticker,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000.0,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _reference(days: int = 80) -> MarketReference:
    dates = pd.bdate_range("2024-01-01", periods=days)
    rng = np.random.default_rng(6)
    ohlcv = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": symbol,
                    "adj_close": 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, days))),
                }
            )
            for symbol in ("SPY", "^VIX", "XLK")
        ],
        ignore_index=True,
    )
    return MarketReference(
        ohlcv=ohlcv,
        market_symbol="SPY",
        volatility_symbol="^VIX",
        sector_etf_by_ticker={"AAPL": "XLK"},
    )


def test_feature_sets_extend_the_technical_baseline_without_duplicates() -> None:
    assert resolve_feature_set("technical") == DEFAULT_FEATURE_COLUMNS
    assert resolve_feature_set("technical_range_market") == [
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *MARKET_FEATURE_COLUMNS,
    ]
    for columns in FEATURE_SETS.values():
        assert len(columns) == len(set(columns))
    assert not feature_set_requires_market_reference(resolve_feature_set("technical_range"))
    assert feature_set_requires_market_reference(resolve_feature_set("technical_market"))


def test_unknown_feature_set_lists_choices() -> None:
    with pytest.raises(ValueError, match="technical_range"):
        resolve_feature_set("magic")


def test_technical_frame_matches_existing_builder() -> None:
    ohlcv = _ohlcv()

    pd.testing.assert_frame_equal(
        build_feature_frame(ohlcv, DEFAULT_FEATURE_COLUMNS),
        build_technical_features(ohlcv),
    )


def test_full_feature_frame_builds_all_columns_and_keeps_ticker_strings() -> None:
    columns = resolve_feature_set("technical_range_market")

    frame = build_feature_frame(_ohlcv(), columns, market_reference=_reference())

    assert set(columns) <= set(frame.columns)
    assert set(frame["ticker"]) == {"AAPL", "2330"}
    assert frame.loc[frame.index[-1], columns].notna().all()


def test_market_columns_require_reference() -> None:
    with pytest.raises(ValueError, match="market reference"):
        build_feature_frame(_ohlcv(), resolve_feature_set("technical_market"))


def test_unknown_columns_are_rejected() -> None:
    with pytest.raises(ValueError, match="not_a_feature"):
        build_feature_frame(_ohlcv(), [*DEFAULT_FEATURE_COLUMNS, "not_a_feature"])
