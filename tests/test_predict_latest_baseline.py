from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.predict_latest_baseline import (
    parse_args,
    run_prediction,
    select_latest_feature_rows,
    split_train_calibration,
)
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features


def _ohlcv_frame(days: int = 90) -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    for ticker, offset in [("2330", 0.0), ("NVDA", 8.0)]:
        for index, date in enumerate(dates):
            cycle = np.sin(index / 4.0) * 8.0
            close = 100.0 + offset + cycle + (index * 0.04)
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "ticker": ticker,
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000 + index,
                }
            )
    return pd.DataFrame(rows)


def test_select_latest_feature_rows_keeps_latest_per_ticker() -> None:
    featured = build_technical_features(_ohlcv_frame(days=30))

    latest = select_latest_feature_rows(featured)

    assert latest["ticker"].tolist() == ["2330", "NVDA"]
    assert latest["date"].dt.date.astype(str).tolist() == ["2025-01-30", "2025-01-30"]


def test_split_train_calibration_uses_later_dates_for_calibration() -> None:
    dates = pd.date_range("2025-01-01", periods=20, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["2330"] * len(dates),
            "risk_label": [0, 1] * 10,
            **{column: np.arange(len(dates), dtype=float) for column in DEFAULT_FEATURE_COLUMNS},
        }
    )

    train, calibration = split_train_calibration(frame, calibration_size=5, train_size=10)

    assert train["date"].min() == pd.Timestamp("2025-01-06")
    assert train["date"].max() == pd.Timestamp("2025-01-15")
    assert calibration["date"].min() == pd.Timestamp("2025-01-16")
    assert calibration["date"].max() == pd.Timestamp("2025-01-20")


def test_run_prediction_writes_serving_json_for_numeric_and_us_tickers(tmp_path: Path) -> None:
    input_path = tmp_path / "ohlcv.csv"
    output_path = tmp_path / "latest_predictions.csv"
    json_path = tmp_path / "latest_warnings.json"
    _ohlcv_frame().to_csv(input_path, index=False)
    args = parse_args(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--json-output",
            str(json_path),
            "--calibration-size",
            "10",
            "--train-size",
            "40",
            "--calibration-method",
            "none",
            "--run-id",
            "test_baseline_latest",
        ]
    )

    predictions = run_prediction(args)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert predictions["ticker"].tolist() == ["2330", "NVDA"]
    assert payload["schema_version"] == "v1"
    assert payload["run_id"] == "test_baseline_latest"
    assert payload["record_count"] == 2
    assert [record["ticker"] for record in payload["records"]] == ["2330", "NVDA"]
    assert output_path.exists()


def test_run_prediction_preserves_leading_zero_ticker_symbols(tmp_path: Path) -> None:
    input_path = tmp_path / "ohlcv.csv"
    output_path = tmp_path / "latest_predictions.csv"
    json_path = tmp_path / "latest_warnings.json"
    frame = _ohlcv_frame()
    frame = frame[frame["ticker"] == "2330"].copy()
    frame["ticker"] = "00878"
    frame.to_csv(input_path, index=False)
    args = parse_args(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--json-output",
            str(json_path),
            "--calibration-size",
            "10",
            "--train-size",
            "40",
            "--calibration-method",
            "none",
            "--run-id",
            "test_leading_zero",
        ]
    )

    predictions = run_prediction(args)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert predictions["ticker"].tolist() == ["00878"]
    assert payload["records"][0]["ticker"] == "00878"
