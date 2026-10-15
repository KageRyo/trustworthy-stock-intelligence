"""Residual TPEx close errors require corroborating official OHLC evidence."""
import pandas as pd
import pytest

from tsi.data import price_reconciliation as daily
from tsi.data.download import DownloadFrameResult, DownloadTicker


def _snapshot():
    result = DownloadFrameResult(
        dataset_name="test", tickers=[DownloadTicker("3260", "3260.TWO", "tpex")],
        ohlcv=pd.DataFrame([{
            "date": "2017-07-03", "ticker": "3260", "open": 73.509483,
            "high": 73.802742, "low": 73.020729, "close": 69.208397,
            "adj_close": 45.059568, "volume": 7326943.0,
        }]), start="2015-01-01", end="2026-10-15", interval="1d", failed_batches=[],
    )

    before = result.ohlcv.iloc[0].copy()
    before["date"] = "2017-06-30"
    before["close"] = 73.1
    before["adj_close"] = 73.1 * (45.059568 / 69.208397)
    result.ohlcv.loc[1] = before
    return result


def test_official_ohl_agreement_corrects_close_on_same_split_scale(tmp_path, monkeypatch):
    result = _snapshot()
    official = pd.DataFrame([{
        "date": "2017-07-03", "ticker": "3260", "open": 75.2,
        "high": 75.5, "low": 74.7, "close": 74.8,
        "adj_close": 74.8, "volume": 7162,
    }])
    monkeypatch.setattr(daily, "download_tpex_daily_frame", lambda *a, **kw: official)
    frame, changes = daily.reconcile_tpex_closes(result)
    row = frame.iloc[0]
    assert row.low <= row.close <= row.high
    assert row.open == result.ohlcv.iloc[0].open
    assert row.volume == result.ohlcv.iloc[0].volume
    assert row.adj_close / row.close == pytest.approx(45.059568 / 69.208397)
    assert changes[0].official_close == 74.8
    assert changes[0].ticker == "3260"
    assert result.ohlcv.iloc[0].close == 69.208397  # Original provider evidence is immutable.


def test_official_disagreement_blocks_any_correction(monkeypatch):
    official = pd.DataFrame([{
        "date": "2017-07-03", "ticker": "3260", "open": 75.2,
        "high": 80.0, "low": 74.7, "close": 74.8,
    }])
    monkeypatch.setattr(daily, "download_tpex_daily_frame", lambda *a, **kw: official)
    with pytest.raises(ValueError, match="agreement"):
        daily.reconcile_tpex_closes(_snapshot())


def test_bad_close_with_correct_adjusted_close_is_not_rescaled(monkeypatch):
    result = _snapshot()
    result.ohlcv.loc[0, "adj_close"] = 47.6  # Correct adjusted price, only raw close is bad.
    official = pd.DataFrame([{
        "date": "2017-07-03", "ticker": "3260", "open": 75.2,
        "high": 75.5, "low": 74.7, "close": 74.8,
    }])
    monkeypatch.setattr(daily, "download_tpex_daily_frame", lambda *a, **kw: official)
    with pytest.raises(ValueError, match="adjustment factor"):
        daily.reconcile_tpex_closes(result)
