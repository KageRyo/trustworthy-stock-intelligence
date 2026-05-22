"""Leakage-aware walk-forward split utilities."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WalkForwardFold:
    """One walk-forward fold defined by date boundaries and row indices."""

    fold_id: int
    train_dates: tuple[pd.Timestamp, ...]
    calibration_dates: tuple[pd.Timestamp, ...]
    test_dates: tuple[pd.Timestamp, ...]
    train_index: tuple[int, ...]
    calibration_index: tuple[int, ...]
    test_index: tuple[int, ...]


def build_walk_forward_splits(
    frame: pd.DataFrame,
    *,
    date_col: str = "date",
    train_size: int = 252,
    calibration_size: int = 63,
    test_size: int = 63,
    step_size: int | None = None,
) -> list[WalkForwardFold]:
    """Create walk-forward splits over unique trading dates.

    Sizes are measured in unique trading dates, not in rows.
    """

    if train_size < 1 or calibration_size < 1 or test_size < 1:
        raise ValueError("train_size, calibration_size, and test_size must all be positive")

    working = frame.copy()
    working[date_col] = pd.to_datetime(working[date_col])
    working = working.sort_values(date_col).reset_index()

    unique_dates = pd.Index(working[date_col].drop_duplicates().sort_values())
    total_window = train_size + calibration_size + test_size
    if len(unique_dates) < total_window:
        raise ValueError(
            "Not enough unique dates for one walk-forward fold: "
            f"required {total_window}, found {len(unique_dates)}"
        )

    step = test_size if step_size is None else step_size
    if step < 1:
        raise ValueError("step_size must be at least 1")

    folds: list[WalkForwardFold] = []
    start = 0
    fold_id = 0

    while start + total_window <= len(unique_dates):
        train_dates = tuple(unique_dates[start : start + train_size])
        calibration_start = start + train_size
        calibration_dates = tuple(unique_dates[calibration_start : calibration_start + calibration_size])
        test_start = calibration_start + calibration_size
        test_dates = tuple(unique_dates[test_start : test_start + test_size])

        train_index = tuple(
            working.loc[working[date_col].isin(train_dates), "index"].astype(int).tolist()
        )
        calibration_index = tuple(
            working.loc[working[date_col].isin(calibration_dates), "index"].astype(int).tolist()
        )
        test_index = tuple(
            working.loc[working[date_col].isin(test_dates), "index"].astype(int).tolist()
        )

        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_dates=train_dates,
                calibration_dates=calibration_dates,
                test_dates=test_dates,
                train_index=train_index,
                calibration_index=calibration_index,
                test_index=test_index,
            )
        )
        start += step
        fold_id += 1

    return folds
