from __future__ import annotations

import pandas as pd
import pytest

from tsi.data import download as download_module
from tsi.data.download import (
    TPEXEmergingHistoricalResponse,
    TPEXEmergingHistoricalTable,
    TWSEStockDayResponse,
    _normalize_download_frame,
    configure_yfinance_cache,
    download_ticker_frame,
    resolve_yfinance_ticker,
)


def test_resolve_yfinance_ticker_maps_numeric_auto_to_twse_symbol() -> None:
    resolved = resolve_yfinance_ticker("2330")

    assert resolved.ticker == "2330"
    assert resolved.query_symbol == "2330.TW"


def test_resolve_yfinance_ticker_maps_taiwan_alphanumeric_auto_to_twse_symbol() -> None:
    resolved = resolve_yfinance_ticker("00981a")

    assert resolved.ticker == "00981A"
    assert resolved.query_symbol == "00981A.TW"
    assert resolved.market == "twse"


def test_resolve_yfinance_ticker_maps_explicit_emerging_symbol() -> None:
    resolved = resolve_yfinance_ticker("5240", market="emerging")

    assert resolved.ticker == "5240"
    assert resolved.query_symbol == "5240.EMERGING"
    assert resolved.market == "emerging"


def test_resolve_yfinance_ticker_supports_tpex_numeric_codes() -> None:
    resolved = resolve_yfinance_ticker("6488", market="tpex")

    assert resolved.ticker == "6488"
    assert resolved.query_symbol == "6488.TWO"


def test_resolve_yfinance_ticker_supports_taiwan_alphanumeric_tpex_codes() -> None:
    resolved = resolve_yfinance_ticker("02001L", market="tpex")

    assert resolved.ticker == "02001L"
    assert resolved.query_symbol == "02001L.TWO"
    assert resolved.market == "tpex"


def test_resolve_yfinance_ticker_rejects_non_taiwan_twse_codes() -> None:
    with pytest.raises(ValueError, match="Taiwan stock code"):
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


def test_configure_yfinance_cache_uses_writable_env_path(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "yf-cache"
    calls: list[str] = []

    monkeypatch.setenv("TSI_YFINANCE_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(download_module.yf, "set_tz_cache_location", calls.append)

    configure_yfinance_cache()

    assert cache_dir.is_dir()
    assert calls == [str(cache_dir)]


def test_download_ticker_frame_falls_back_to_twse_daily_for_taiwan_code(monkeypatch) -> None:
    def fake_yfinance_download(**_kwargs):
        return pd.DataFrame()

    def fake_fetch_json(_url, params):
        if params["date"] == "20260601":
            return TWSEStockDayResponse(
                stat="OK",
                date="20260601",
                title="115年06月 00981A 主動統一台股增長 各日成交資訊",
                fields=[
                    "日期",
                    "成交股數",
                    "成交金額",
                    "開盤價",
                    "最高價",
                    "最低價",
                    "收盤價",
                    "漲跌價差",
                    "成交筆數",
                    "註記",
                ],
                data=[
                    [
                        "115/06/01",
                        "254,690,698",
                        "8,109,667,428",
                        "31.69",
                        "32.07",
                        "31.61",
                        "31.70",
                        "+0.16",
                        "73,732",
                        "",
                    ]
                ],
            ).model_dump()
        return TWSEStockDayResponse(stat="很抱歉，沒有符合條件的資料!").model_dump()

    monkeypatch.setattr(download_module.yf, "download", fake_yfinance_download)
    monkeypatch.setattr(download_module, "fetch_json", fake_fetch_json)

    result = download_ticker_frame(
        ["00981A"],
        start="2026-06-01",
        end="2026-06-02",
        interval="1d",
        market="auto",
    )

    assert result.tickers[0].query_symbol == "00981A.TW"
    assert result.tickers[0].market == "twse"
    assert result.failed_batches == []
    assert result.ohlcv["ticker"].tolist() == ["00981A"]
    assert result.ohlcv["date"].tolist() == ["2026-06-01"]
    assert result.ohlcv["close"].tolist() == [31.70]
    assert result.ohlcv["volume"].tolist() == [254690698.0]


def test_download_ticker_frame_falls_back_to_tpex_emerging_daily_for_taiwan_code(
    monkeypatch,
) -> None:
    def fake_yfinance_download(**_kwargs):
        return pd.DataFrame()

    def fake_fetch_json(_url, _params):
        return TWSEStockDayResponse(stat="很抱歉，沒有符合條件的資料!").model_dump()

    def fake_fetch_json_post(_url, params):
        if params["date"] == "20260601":
            return TPEXEmergingHistoricalResponse(
                stat="ok",
                date="20260620",
                tables=[
                    TPEXEmergingHistoricalTable(
                        title="興櫃個股歷史行情",
                        data=[
                            [
                                "115/06/01",
                                "5,054",
                                "124,850",
                                "25.20",
                                "24.50",
                                "24.70",
                                "6",
                                "0",
                                "0",
                                "0.00",
                                "0.00",
                                "0.00",
                                "0",
                            ]
                        ],
                    )
                ],
            ).model_dump()
        return TPEXEmergingHistoricalResponse(stat="查無資料").model_dump()

    monkeypatch.setattr(download_module.yf, "download", fake_yfinance_download)
    monkeypatch.setattr(download_module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(download_module, "fetch_json_post", fake_fetch_json_post)

    result = download_ticker_frame(
        ["5240"],
        start="2026-06-01",
        end="2026-06-02",
        interval="1d",
        market="auto",
    )

    assert result.tickers[0].query_symbol == "5240.EMERGING"
    assert result.tickers[0].market == "emerging"
    assert result.failed_batches == []
    assert result.ohlcv["ticker"].tolist() == ["5240"]
    assert result.ohlcv["date"].tolist() == ["2026-06-01"]
    assert result.ohlcv["high"].tolist() == [25.20]
    assert result.ohlcv["low"].tolist() == [24.50]
    assert result.ohlcv["close"].tolist() == [124850 / 5054]
    assert result.ohlcv["volume"].tolist() == [5054.0]
