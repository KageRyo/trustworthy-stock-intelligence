"""Reconcile residual TPEx close errors only when official OHLC corroborates the scale."""
from __future__ import annotations

from math import isclose

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from tsi.data.download import DownloadFrameResult, download_tpex_daily_frame


class OfficialCloseCorrection(BaseModel):
    """Auditable official evidence, with provider adjustment scale preserved."""

    model_config = ConfigDict(extra="forbid")
    ticker: str
    date: str
    source: str = "tpex_tradingStock"
    original_close: float
    corrected_close: float
    original_adj_close: float
    corrected_adj_close: float
    official_open: float
    official_high: float
    official_low: float
    official_close: float
    price_scale: float
    adjustment_reference_date: str | None = None
    adjustment_reference_factor: float | None = None


def reconcile_tpex_closes(
    result: DownloadFrameResult,
) -> tuple[pd.DataFrame, list[OfficialCloseCorrection]]:
    """Fix only closes outside valid OHL bounds, corroborated by official OHL ratios.

    Yahoo OHL can be split-adjusted while official exchange prices are raw. All three
    independent OHL ratios must agree, and the official close must fit those bounds.
    Keep the repaired provider's adj_close/close ratio and volume units. Never clamp,
    discard a row, or infer a close from nearby prices. Other invalid data stays blocked.
    """
    frame = result.ohlcv.copy()
    corrections: list[OfficialCloseCorrection] = []
    markets = {t.ticker: t.market for t in result.tickers}
    low, high, close = frame.low, frame.high, frame.close
    bad_close = (close < low) | (close > high)
    for index in frame.index[bad_close]:
        row = frame.loc[index]
        if markets.get(str(row.ticker)) != "tpex":
            continue
        day = str(row.date)[:10]
        reference, scale, new_close = _official_close(row, day)
        previous, previous_ratio = _adjustment_reference(result.ohlcv, row, day)
        adjusted = float(row.adj_close) * new_close / float(row.close)
        corrections.append(OfficialCloseCorrection(
            ticker=str(row.ticker), date=day, original_close=float(row.close),
            corrected_close=new_close, original_adj_close=float(row.adj_close),
            corrected_adj_close=adjusted, official_open=float(reference.open),
            official_high=float(reference.high), official_low=float(reference.low),
            official_close=float(reference.close), price_scale=scale,
            adjustment_reference_date=str(previous.date)[:10],
            adjustment_reference_factor=previous_ratio,
        ))
        frame.loc[index, ["close", "adj_close"]] = [new_close, adjusted]
    return frame, corrections


def _official_close(row: pd.Series, day: str) -> tuple[pd.Series, float, float]:
    """Require official OHL corroboration on the provider's split-adjusted scale."""
    official = download_tpex_daily_frame(str(row.ticker), start=day, end=day)
    official = official[official.date.astype(str).str.startswith(day)]
    if len(official) != 1:
        raise ValueError("No unique official TPEx row for close reconciliation")
    reference = official.iloc[0]
    original_ohl = np.array([row.open, row.high, row.low], dtype=float)
    reference_ohl = np.array([reference.open, reference.high, reference.low], dtype=float)
    if not np.isfinite(reference_ohl).all() or (reference_ohl <= 0).any():
        raise ValueError("Invalid official TPEx price evidence")
    ratios = original_ohl / reference_ohl
    scale = float(np.median(ratios))
    if not all(isclose(float(r), scale, rel_tol=1e-6) for r in ratios):
        raise ValueError("Official TPEx OHL scale agreement failed")
    new_close = float(reference.close) * scale
    if not (float(row.low) <= new_close <= float(row.high)):
        raise ValueError("Official TPEx close does not satisfy provider OHL bounds")
    return reference, scale, new_close


def _adjustment_reference(
    frame: pd.DataFrame, row: pd.Series, day: str,
) -> tuple[pd.Series, float]:
    """Require a nearby prior trading row to corroborate the adjustment ratio."""
    if not np.isfinite([row.close, row.adj_close]).all() or float(row.close) <= 0:
        raise ValueError("Provider adjustment ratio is unavailable")
    history = frame[
        (frame.ticker == row.ticker) & (frame.date.astype(str).str[:10] < day)
    ].sort_values("date")
    if history.empty:
        raise ValueError("No preceding adjustment factor evidence")
    previous = history.iloc[-1]
    gap = (pd.Timestamp(day) - pd.Timestamp(previous.date)).days
    ratio = float(row.adj_close) / float(row.close)
    previous_ratio = float(previous.adj_close) / float(previous.close)
    if not (0 < gap <= 7 and np.isfinite(previous_ratio) and previous_ratio > 0
            and isclose(ratio, previous_ratio, rel_tol=1e-5)):
        raise ValueError("Preceding adjustment factor agreement failed")
    return previous, previous_ratio
