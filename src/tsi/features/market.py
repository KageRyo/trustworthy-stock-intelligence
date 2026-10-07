"""Leakage-safe market-relative features from reference index and sector series.

Reference prices are aligned to each stock row with a backward as-of join, so a
row at date ``t`` only sees reference closes on or before ``t``. When the
reference market closes after the stock's market on the same calendar date
(for example SPY versus a Taiwan stock), pass ``same_session_reference=False``
to use only reference closes strictly before ``t``. Returns are then computed on
the stock's own trading calendar.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

RELATIVE_FEATURE_COLUMNS = [
    "excess_return_5d",
    "excess_return_20d",
    "sector_excess_return_5d",
    "sector_excess_return_20d",
    "beta_60d",
]
REGIME_FEATURE_COLUMNS = [
    "market_return_5d",
    "market_drawdown_from_60d_high",
    "vix_level",
    "vix_change_5d",
]
MARKET_FEATURE_COLUMNS = [*RELATIVE_FEATURE_COLUMNS, *REGIME_FEATURE_COLUMNS]

_STOCK_COLUMNS = ("date", "ticker", "adj_close")
_REFERENCE_COLUMNS = ("date", "ticker", "adj_close")
BETA_WINDOW = 60


def _require(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")


def _align_reference(
    dates: pd.Series,
    reference: pd.DataFrame,
    symbol: str,
    *,
    same_session: bool,
    tolerance: pd.Timedelta,
) -> pd.Series:
    """Return the latest reference close available at each date, indexed like ``dates``."""

    series = (
        reference.loc[reference["ticker"] == symbol, ["date", "adj_close"]]
        .dropna()
        .drop_duplicates("date", keep="last")
        .sort_values("date")
        .rename(columns={"adj_close": "reference_close"})
    )
    if series.empty:
        return pd.Series(np.nan, index=dates.index)
    left = pd.DataFrame({"date": dates, "row": np.arange(len(dates))}).sort_values("date")
    aligned = pd.merge_asof(
        left,
        series,
        on="date",
        direction="backward",
        allow_exact_matches=same_session,
        tolerance=tolerance,
    )
    values = aligned.sort_values("row")["reference_close"].to_numpy()
    return pd.Series(values, index=dates.index, dtype=float)


def _period_return(price: pd.Series, tickers: pd.Series, periods: int) -> pd.Series:
    return price / price.groupby(tickers).shift(periods) - 1.0


def _rolling_mean(values: pd.Series, tickers: pd.Series, window: int) -> pd.Series:
    return values.groupby(tickers).transform(
        lambda series: series.rolling(window=window, min_periods=window).mean()
    )


def build_market_features(
    ohlcv: pd.DataFrame,
    reference_ohlcv: pd.DataFrame,
    *,
    market_symbol: str,
    volatility_symbol: str | None,
    sector_etf_by_ticker: Mapping[str, str],
    same_session_reference: bool = True,
    max_reference_staleness_days: int = 7,
) -> pd.DataFrame:
    """Append market-relative return, beta, market regime, and volatility-index features.

    Sector-relative returns fall back to the market series when a ticker has no
    sector ETF or the ETF has no price for that window. Volatility-index
    features stay missing when ``volatility_symbol`` is ``None``.
    """

    _require(ohlcv, _STOCK_COLUMNS, "ohlcv")
    _require(reference_ohlcv, _REFERENCE_COLUMNS, "reference_ohlcv")
    reference = reference_ohlcv.copy()
    reference["date"] = pd.to_datetime(reference["date"])
    reference["ticker"] = reference["ticker"].astype(str)
    if not (reference["ticker"] == market_symbol).any():
        raise ValueError(f"Reference data has no rows for market symbol {market_symbol}")

    frame = ohlcv.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    tickers = frame["ticker"]
    tolerance = pd.Timedelta(days=max_reference_staleness_days)

    def align(symbol: str) -> pd.Series:
        return _align_reference(
            frame["date"],
            reference,
            symbol,
            same_session=same_session_reference,
            tolerance=tolerance,
        )

    stock_price = frame["adj_close"]
    market_price = align(market_symbol)
    sector_price = pd.Series(np.nan, index=frame.index)
    for etf in sorted(set(sector_etf_by_ticker.values())):
        rows = tickers.map(sector_etf_by_ticker).eq(etf)
        if rows.any():
            sector_price[rows] = align(etf)[rows]

    for periods in (5, 20):
        stock_return = _period_return(stock_price, tickers, periods)
        market_return = _period_return(market_price, tickers, periods)
        sector_return = _period_return(sector_price, tickers, periods).fillna(market_return)
        frame[f"excess_return_{periods}d"] = stock_return - market_return
        frame[f"sector_excess_return_{periods}d"] = stock_return - sector_return
        if periods == 5:
            frame["market_return_5d"] = market_return

    stock_daily = _period_return(stock_price, tickers, 1)
    market_daily = _period_return(market_price, tickers, 1)
    covariance = _rolling_mean(stock_daily * market_daily, tickers, BETA_WINDOW) - _rolling_mean(
        stock_daily, tickers, BETA_WINDOW
    ) * _rolling_mean(market_daily, tickers, BETA_WINDOW)
    variance = (
        _rolling_mean(market_daily**2, tickers, BETA_WINDOW)
        - _rolling_mean(market_daily, tickers, BETA_WINDOW) ** 2
    )
    frame["beta_60d"] = covariance / variance.where(variance > 0)

    market_high = market_price.groupby(tickers).transform(
        lambda series: series.rolling(window=60, min_periods=60).max()
    )
    frame["market_drawdown_from_60d_high"] = market_price / market_high - 1.0

    if volatility_symbol is None:
        frame["vix_level"] = np.nan
        frame["vix_change_5d"] = np.nan
    else:
        vix = align(volatility_symbol)
        frame["vix_level"] = vix
        frame["vix_change_5d"] = _period_return(vix, tickers, 5)

    frame[MARKET_FEATURE_COLUMNS] = (
        frame[MARKET_FEATURE_COLUMNS].astype(float).replace([np.inf, -np.inf], np.nan)
    )
    return frame
