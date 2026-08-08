"""Tests for the leakage-aware cross-market transfer helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.evaluate_cross_market_transfer import (
    _json_safe,
    _mean_metric_dict,
    target_rows_for_dates,
)


def test_target_rows_use_source_test_dates_and_preserve_string_tickers() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
            "ticker": ["0050", "2330", "2330"],
            "risk_label": [0, 1, 0],
        }
    )

    selected = target_rows_for_dates(frame, pd.to_datetime(["2026-01-05", "2026-01-06"]))

    assert selected["ticker"].tolist() == ["2330", "2330"]


def test_mean_metric_dict_ignores_undefined_auc() -> None:
    result = _mean_metric_dict(
        [
            {"auc": float("nan"), "brier_score": 0.2},
            {"auc": 0.6, "brier_score": 0.4},
        ]
    )

    assert result["auc"] == 0.6
    assert result["brier_score"] == 0.30000000000000004


def test_mean_metric_dict_supports_transfer_degradation_fields() -> None:
    result = _mean_metric_dict(
        [{"event_rate_delta": 0.1, "brier_delta": 0.2, "ece_delta": 0.3}],
        metric_names=("event_rate_delta", "brier_delta", "ece_delta"),
    )

    assert result == {"event_rate_delta": 0.1, "brier_delta": 0.2, "ece_delta": 0.3}


def test_json_safe_converts_numpy_scalars_and_nan() -> None:
    value = _json_safe({"count": np.int64(2), "undefined": np.float64("nan")})

    assert value == {"count": 2, "undefined": None}
