from __future__ import annotations

import pandas as pd
import pytest

from tsi.data.download import _normalize_download_frame, download_ticker_frame, resolve_yfinance_ticker


def test_resolve_yfinance_ticker_maps_numeric_auto_to_twse_symbol() -> None:
    resolved = resolve_yfinance_ticker("2330")

    assert resolved.ticker == "2330"
    assert resolved.query_symbol == "2330.TW"


def test_resolve_yfinance_ticker_supports_tpex_numeric_codes() -> None:
    resolved = resolve_yfinance_ticker("6488", market="tpex")

    assert resolved.ticker == "6488"
    assert resolved.query_symbol == "6488.TWO"


def test_resolve_yfinance_ticker_rejects_non_numeric_twse_codes() -> None:
    with pytest.raises(ValueError, match="numeric Taiwan stock code"):
        resolve_yfinance_ticker("NVDA", market="twse")


def test_normalize_download_frame_keeps_display_ticker_alias() -> None:
    index = pd.DatetimeIndex(["2026-06-18", "2026-06-19"], name="Date")
    raw = pd.DataFrame(
        {
            ("2330.TW", "Open"): [100.0, 101.0],
            ("2330.TW", "High"): [103.0, 104.0],
            ("2330.TW", "Low"): [99.0, 100.0],
            ("2330.TW", "Close"): [102.0, 103.0],
            ("2330.TW", "Adj Close"): [102.0, 103.0],
            ("2330.TW", "Volume"): [1000, 1200],
        },
        index=index,
    )

    normalized = _normalize_download_frame(raw, ["2330.TW"], {"2330.TW": "2330"})

    assert normalized["ticker"].tolist() == ["2330", "2330"]
    assert normalized["date"].tolist() == ["2026-06-18", "2026-06-19"]


def test_normalize_download_frame_preserves_intraday_timestamp() -> None:
    index = pd.DatetimeIndex(["2026-06-18 01:00:00+00:00"], name="Datetime")
    raw = pd.DataFrame(
        {
            ("NVDA", "Open"): [100.0],
            ("NVDA", "High"): [103.0],
            ("NVDA", "Low"): [99.0],
            ("NVDA", "Close"): [102.0],
            ("NVDA", "Volume"): [1000],
        },
        index=index,
    )

    normalized = _normalize_download_frame(raw, ["NVDA"], preserve_timestamp=True)

    assert normalized["date"].tolist() == ["2026-06-18T01:00:00Z"]
    assert normalized["adj_close"].tolist() == [102.0]


def test_download_ticker_frame_rejects_unsupported_interval() -> None:
    with pytest.raises(ValueError, match="interval must be one of"):
        download_ticker_frame(["NVDA"], start="2026-01-01", interval="15m")
