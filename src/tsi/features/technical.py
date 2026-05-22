"""Leakage-safe technical feature generation for daily OHLCV data."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

DEFAULT_FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "sma_5_gap",
    "sma_10_gap",
    "volatility_5d",
    "volatility_10d",
    "volume_ratio_5d",
]


def _validate_input_columns(frame: pd.DataFrame, required: Sequence[str]) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        missing_joined = ", ".join(missing)
        raise ValueError(f"Missing required columns: {missing_joined}")


def build_technical_features(
    ohlcv: pd.DataFrame,
    *,
    date_col: str = "date",
    ticker_col: str = "ticker",
    price_col: str = "adj_close",
    volume_col: str = "volume",
) -> pd.DataFrame:
    """Build simple leakage-safe technical features.

    All features use only information available on or before date ``t``.
    The function preserves all source columns and appends feature columns.
    """

    _validate_input_columns(ohlcv, [date_col, ticker_col, price_col, volume_col])

    frame = ohlcv.copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    frame = frame.sort_values([ticker_col, date_col]).reset_index(drop=True)

    grouped = frame.groupby(ticker_col, group_keys=False)

    price = grouped[price_col]
    volume = grouped[volume_col]

    frame["return_1d"] = price.pct_change(1)
    frame["return_5d"] = price.pct_change(5)

    sma_5 = price.transform(lambda series: series.rolling(window=5, min_periods=5).mean())
    sma_10 = price.transform(lambda series: series.rolling(window=10, min_periods=10).mean())
    frame["sma_5_gap"] = frame[price_col] / sma_5 - 1.0
    frame["sma_10_gap"] = frame[price_col] / sma_10 - 1.0

    frame["volatility_5d"] = grouped["return_1d"].transform(
        lambda series: series.rolling(window=5, min_periods=5).std()
    )
    frame["volatility_10d"] = grouped["return_1d"].transform(
        lambda series: series.rolling(window=10, min_periods=10).std()
    )

    avg_volume_5 = volume.transform(lambda series: series.rolling(window=5, min_periods=5).mean())
    frame["volume_ratio_5d"] = frame[volume_col] / avg_volume_5

    numeric_features = frame[DEFAULT_FEATURE_COLUMNS].select_dtypes(include=[np.number])
    frame[DEFAULT_FEATURE_COLUMNS] = numeric_features.replace([np.inf, -np.inf], np.nan)
    return frame
