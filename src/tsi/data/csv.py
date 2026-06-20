"""CSV loading helpers for market data artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_ohlcv_csv(path: Path | str) -> pd.DataFrame:
    """Read OHLCV CSV while preserving ticker symbols exactly as strings."""

    frame = pd.read_csv(path, dtype={"ticker": "string"})
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper()
    return frame
