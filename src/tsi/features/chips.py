"""Leakage-safe Taiwan institutional-flow and margin features.

Institutional flows and margin balances for date ``t`` are published after the
close of ``t``. Features are computed on each ticker's own trading calendar and
then shifted by ``publication_lag`` rows, so with the default lag of 1 a row at
date ``t`` only uses chip data through the previous trading date.

On a date the archive covers, a ticker absent from T86 had no institutional
trades (net flow 0), and a ticker absent from MI_MARGN has no margin balance
(0 lots). On a date the archive does not cover, chip values are missing.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from tsi.data.twse_chips import ChipTables

FLOW_FEATURE_COLUMNS = [
    "foreign_flow_5d",
    "foreign_flow_20d",
    "trust_flow_5d",
    "trust_flow_20d",
    "dealer_flow_5d",
]
MARGIN_FEATURE_COLUMNS = [
    "margin_change_5d",
    "short_change_5d",
    "margin_days_of_volume",
    "short_to_margin",
]
CHIP_FEATURE_COLUMNS = [*FLOW_FEATURE_COLUMNS, *MARGIN_FEATURE_COLUMNS]
SHARES_PER_LOT = 1_000.0
_REQUIRED_COLUMNS = ("date", "ticker", "volume")


def _aligned(
    frame: pd.DataFrame,
    table: pd.DataFrame,
    covered_dates: Sequence[str],
    columns: Sequence[str],
) -> pd.DataFrame:
    """Chip values per stock row: table value, 0 on covered dates, NaN otherwise."""

    chips = table.loc[:, ["date", "ticker", *columns]].copy()
    chips["date"] = pd.to_datetime(chips["date"])
    chips["ticker"] = chips["ticker"].astype(str)
    merged = frame.loc[:, ["date", "ticker"]].merge(chips, on=["date", "ticker"], how="left")
    covered = frame["date"].isin(pd.to_datetime(pd.Index(covered_dates))).to_numpy()
    for column in columns:
        values = merged[column].to_numpy(dtype=float)
        values = np.where(np.isnan(values) & covered, 0.0, values)
        merged[column] = values
    return merged.set_index(frame.index)[list(columns)]


def build_chip_features(
    ohlcv: pd.DataFrame,
    chips: ChipTables,
    *,
    publication_lag: int = 1,
) -> pd.DataFrame:
    """Append institutional-flow and margin features; see the module docstring for timing."""

    missing = [column for column in _REQUIRED_COLUMNS if column not in ohlcv.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if publication_lag < 0:
        raise ValueError("publication_lag must be non-negative")

    frame = ohlcv.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["ticker"] = frame["ticker"].astype(str)
    frame = frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    tickers = frame["ticker"]

    flows = _aligned(
        frame,
        chips.institutional,
        chips.institutional_dates,
        ["foreign_net", "investment_trust_net", "dealer_net"],
    )
    margin = _aligned(
        frame, chips.margin, chips.margin_dates, ["margin_balance", "short_balance"]
    ) * SHARES_PER_LOT
    volume = frame["volume"].astype(float)

    def rolling_sum(values: pd.Series, window: int) -> pd.Series:
        return values.groupby(tickers).transform(
            lambda series: series.rolling(window=window, min_periods=window).sum()
        )

    volume_5d = rolling_sum(volume, 5)
    volume_20d = rolling_sum(volume, 20)
    features = pd.DataFrame(index=frame.index)
    features["foreign_flow_5d"] = rolling_sum(flows["foreign_net"], 5) / volume_5d
    features["foreign_flow_20d"] = rolling_sum(flows["foreign_net"], 20) / volume_20d
    features["trust_flow_5d"] = rolling_sum(flows["investment_trust_net"], 5) / volume_5d
    features["trust_flow_20d"] = rolling_sum(flows["investment_trust_net"], 20) / volume_20d
    features["dealer_flow_5d"] = rolling_sum(flows["dealer_net"], 5) / volume_5d
    for name, column in (
        ("margin_change_5d", "margin_balance"),
        ("short_change_5d", "short_balance"),
    ):
        change = margin[column] - margin[column].groupby(tickers).shift(5)
        features[name] = change / volume_5d
    features["margin_days_of_volume"] = margin["margin_balance"] / (volume_20d / 20.0)
    features["short_to_margin"] = np.where(
        margin["margin_balance"] > 0,
        margin["short_balance"] / margin["margin_balance"].where(margin["margin_balance"] > 0),
        np.where(margin["margin_balance"].isna(), np.nan, 0.0),
    )

    features = features.replace([np.inf, -np.inf], np.nan)
    if publication_lag:
        features = features.groupby(tickers).shift(publication_lag)
    frame[CHIP_FEATURE_COLUMNS] = features[CHIP_FEATURE_COLUMNS].astype(float)
    return frame
