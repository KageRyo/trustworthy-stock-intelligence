"""Leakage-safe range-based volatility features from daily OHLC bars.

Open, high, and low are rescaled by ``adj_close / close`` so splits and dividends do
not create artificial ranges. Every rolling window ends at date ``t``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RANGE_FEATURE_COLUMNS = [
    "parkinson_vol_10d",
    "garman_klass_vol_10d",
    "atr_14_pct",
    "volatility_20d",
    "drawdown_from_20d_high",
]

_REQUIRED_COLUMNS = ("date", "ticker", "open", "high", "low", "close", "adj_close")


def _rolling_mean(grouped: pd.core.groupby.SeriesGroupBy, window: int) -> pd.Series:
    return grouped.transform(
        lambda series: series.rolling(window=window, min_periods=window).mean()
    )


def build_range_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Append range-based volatility and drawdown features per ticker."""

    missing = [column for column in _REQUIRED_COLUMNS if column not in ohlcv.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    frame = ohlcv.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["ticker", "date"]).reset_index(drop=True)

    factor = frame["adj_close"] / frame["close"]
    adj_open = frame["open"] * factor
    adj_high = frame["high"] * factor
    adj_low = frame["low"] * factor
    adj_close = frame["adj_close"]
    previous_close = adj_close.groupby(frame["ticker"]).shift(1)

    with np.errstate(divide="ignore", invalid="ignore"):
        log_high_low = np.log(adj_high / adj_low)
        log_close_open = np.log(adj_close / adj_open)
        daily_return = adj_close.groupby(frame["ticker"]).pct_change()

    by_ticker = frame["ticker"]
    parkinson_term = pd.Series(log_high_low**2, index=frame.index)
    garman_klass_term = pd.Series(
        0.5 * log_high_low**2 - (2.0 * np.log(2.0) - 1.0) * log_close_open**2, index=frame.index
    )
    true_range = pd.concat(
        [adj_high - adj_low, (adj_high - previous_close).abs(), (adj_low - previous_close).abs()],
        axis=1,
    ).max(axis=1, skipna=False)

    frame["parkinson_vol_10d"] = np.sqrt(
        _rolling_mean(parkinson_term.groupby(by_ticker), 10) / (4.0 * np.log(2.0))
    )
    frame["garman_klass_vol_10d"] = np.sqrt(
        _rolling_mean(garman_klass_term.groupby(by_ticker), 10).clip(lower=0.0)
    )
    frame["atr_14_pct"] = _rolling_mean(true_range.groupby(by_ticker), 14) / adj_close
    frame["volatility_20d"] = daily_return.groupby(by_ticker).transform(
        lambda series: series.rolling(window=20, min_periods=20).std()
    )
    rolling_high = adj_close.groupby(by_ticker).transform(
        lambda series: series.rolling(window=20, min_periods=20).max()
    )
    frame["drawdown_from_20d_high"] = adj_close / rolling_high - 1.0

    frame[RANGE_FEATURE_COLUMNS] = frame[RANGE_FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return frame
