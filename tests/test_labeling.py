"""Tests for leakage-free risk labeling."""

from __future__ import annotations

import pandas as pd

from tsi.labeling.drawdown import add_future_drawdown_label


def test_drawdown_label_uses_future_window_only() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=7, freq="D"),
            "ticker": ["AAA"] * 7,
            "adj_close": [100, 96, 97, 94, 98, 102, 101],
        }
    )

    labeled = add_future_drawdown_label(frame, horizon=3, threshold=-0.05)

    assert round(float(labeled.loc[0, "future_max_drawdown"]), 4) == -0.06
    assert labeled.loc[0, "label_end_date"] == pd.Timestamp("2024-01-04")
    assert int(labeled.loc[0, "risk_label"]) == 1
    assert int(labeled.loc[1, "risk_label"]) == 0
    assert bool(labeled.loc[4, "label_available"]) is False
    assert pd.isna(labeled.loc[4, "label_end_date"])
    assert pd.isna(labeled.loc[4, "risk_label"])


def test_drawdown_label_resets_per_ticker() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4, freq="D").tolist() * 2,
            "ticker": ["AAA"] * 4 + ["BBB"] * 4,
            "adj_close": [100, 95, 94, 93, 200, 210, 220, 230],
        }
    )

    labeled = add_future_drawdown_label(frame, horizon=2, threshold=-0.05)

    aaa_first = labeled[labeled["ticker"] == "AAA"].iloc[0]
    bbb_first = labeled[labeled["ticker"] == "BBB"].iloc[0]
    assert int(aaa_first["risk_label"]) == 1
    assert int(bbb_first["risk_label"]) == 0
