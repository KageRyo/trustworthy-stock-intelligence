from __future__ import annotations

from pathlib import Path

from tsi.data.csv import read_ohlcv_csv


def test_read_ohlcv_csv_preserves_leading_zero_tickers(tmp_path: Path) -> None:
    path = tmp_path / "ohlcv.csv"
    path.write_text(
        "date,ticker,open,high,low,close,adj_close,volume\n"
        "2026-06-01,00878,20,21,19,20.5,20.5,1000\n",
        encoding="utf-8",
    )

    frame = read_ohlcv_csv(path)

    assert frame["ticker"].tolist() == ["00878"]
