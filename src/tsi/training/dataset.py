"""Leakage-aware sequence dataset construction for temporal DL models."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SequenceDataset:
    """Windowed model inputs, labels, and target-row metadata."""

    x: np.ndarray
    y: np.ndarray
    metadata: pd.DataFrame
    feature_columns: tuple[str, ...]
    lookback: int


def _validate_columns(frame: pd.DataFrame, required: Sequence[str]) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def build_sequence_dataset(
    frame: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    lookback: int = 60,
    label_col: str = "risk_label",
    date_col: str = "date",
    ticker_col: str = "ticker",
) -> SequenceDataset:
    """Build fixed-length per-ticker windows ending at each labeled target row.

    The label for a sample is read from the row at the end of the window. For
    future-drawdown labels, that row represents information available at day
    ``t`` while the label was generated from ``t+1`` onward.
    """

    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if not feature_columns:
        raise ValueError("feature_columns must not be empty")

    feature_columns_tuple = tuple(feature_columns)
    _validate_columns(frame, [date_col, ticker_col, label_col, *feature_columns_tuple])

    source_index_col = "__tsi_source_index"
    working = frame.copy()
    working[date_col] = pd.to_datetime(working[date_col])
    working[source_index_col] = frame.index
    working = working.sort_values([ticker_col, date_col, source_index_col]).reset_index(drop=True)

    windows: list[np.ndarray] = []
    labels: list[float] = []
    metadata_rows: list[dict[str, object]] = []

    for ticker, group in working.groupby(ticker_col, sort=False):
        group = group.reset_index(drop=True)
        feature_values = group.loc[:, feature_columns_tuple].to_numpy(dtype=float)
        label_values = pd.to_numeric(group[label_col], errors="coerce").to_numpy(dtype=float)

        for end_pos in range(lookback - 1, len(group)):
            start_pos = end_pos - lookback + 1
            window = feature_values[start_pos : end_pos + 1]
            label = label_values[end_pos]

            if np.isnan(label) or not np.isfinite(window).all():
                continue

            target_row = group.iloc[end_pos]
            start_row = group.iloc[start_pos]
            windows.append(window)
            labels.append(float(label))
            metadata_rows.append(
                {
                    "ticker": ticker,
                    "date": target_row[date_col],
                    "source_index": int(target_row[source_index_col]),
                    "window_start_date": start_row[date_col],
                    "window_end_date": target_row[date_col],
                }
            )

    if windows:
        x = np.stack(windows).astype(np.float32)
        y = np.asarray(labels, dtype=np.float32)
    else:
        x = np.empty((0, lookback, len(feature_columns_tuple)), dtype=np.float32)
        y = np.empty((0,), dtype=np.float32)

    metadata = pd.DataFrame(
        metadata_rows,
        columns=["ticker", "date", "source_index", "window_start_date", "window_end_date"],
    )
    return SequenceDataset(
        x=x,
        y=y,
        metadata=metadata,
        feature_columns=feature_columns_tuple,
        lookback=lookback,
    )
