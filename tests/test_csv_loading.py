from __future__ import annotations

from pathlib import Path

import pytest

from tsi.data.csv import portable_path_label, read_ohlcv_csv


def test_read_ohlcv_csv_preserves_leading_zero_tickers(tmp_path: Path) -> None:
    path = tmp_path / "ohlcv.csv"
    path.write_text(
        "date,ticker,open,high,low,close,adj_close,volume\n"
        "2026-06-01,00878,20,21,19,20.5,20.5,1000\n",
        encoding="utf-8",
    )

    frame = read_ohlcv_csv(path)

    assert frame["ticker"].tolist() == ["00878"]


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("data/raw/sp100/ohlcv.csv", "data/raw/sp100/ohlcv.csv"),
        ("work/data/raw/ohlcv.csv", "data/raw/ohlcv.csv"),
        ("elsewhere/ohlcv.csv", "ohlcv.csv"),
    ],
)
def test_portable_path_label_never_includes_host_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, label: str
) -> None:
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    given = Path(path) if path.startswith("data/") else tmp_path / path

    assert portable_path_label(given) == label
