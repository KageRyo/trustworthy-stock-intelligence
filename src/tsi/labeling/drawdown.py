"""Future drawdown risk labels for early-warning experiments."""

from __future__ import annotations

import pandas as pd


def add_future_drawdown_label(
    frame: pd.DataFrame,
    *,
    horizon: int = 5,
    threshold: float = -0.05,
    date_col: str = "date",
    ticker_col: str = "ticker",
    price_col: str = "adj_close",
    label_col: str = "risk_label",
) -> pd.DataFrame:
    """Append future max drawdown statistics and binary risk labels.

    The label at date ``t`` uses prices from ``t+1`` through ``t+horizon`` only.
    Rows without a full future horizon receive missing labels.
    """

    required = [date_col, ticker_col, price_col]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if horizon < 1:
        raise ValueError("horizon must be at least 1")

    labeled = frame.copy()
    labeled[date_col] = pd.to_datetime(labeled[date_col])
    labeled = labeled.sort_values([ticker_col, date_col]).reset_index(drop=True)

    future_window = horizon

    def _per_ticker(group: pd.DataFrame) -> pd.DataFrame:
        prices = group[price_col]
        future_min = prices.shift(-1).rolling(window=future_window, min_periods=future_window).min()
        future_min = future_min.shift(-(future_window - 1))
        future_drawdown = future_min / prices - 1.0

        result = group.copy()
        result[ticker_col] = group.name
        result["future_min_price"] = future_min
        result["future_max_drawdown"] = future_drawdown
        result["label_available"] = future_drawdown.notna()
        result[label_col] = pd.Series(pd.NA, index=result.index, dtype="Int64")
        available_mask = result["label_available"]
        result.loc[available_mask, label_col] = (
            result.loc[available_mask, "future_max_drawdown"] <= threshold
        ).astype("Int64")
        return result

    return labeled.groupby(ticker_col, group_keys=False).apply(_per_ticker).reset_index(drop=True)
