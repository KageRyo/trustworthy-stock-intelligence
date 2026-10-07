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
    split_train_calibration_recent,
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


def test_split_train_calibration_recent_keeps_later_drift_window_out_of_fitting() -> None:
    dates = pd.date_range("2025-01-01", periods=20, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["2330"] * len(dates),
            "risk_label": [0, 1] * 10,
            **{column: np.arange(len(dates), dtype=float) for column in DEFAULT_FEATURE_COLUMNS},
        }
    )

    train, calibration, recent = split_train_calibration_recent(
        frame,
        calibration_size=5,
        drift_size=3,
        train_size=8,
    )

    assert train["date"].min() == pd.Timestamp("2025-01-05")
    assert train["date"].max() == pd.Timestamp("2025-01-12")
    assert calibration["date"].min() == pd.Timestamp("2025-01-13")
    assert calibration["date"].max() == pd.Timestamp("2025-01-17")
    assert recent["date"].min() == pd.Timestamp("2025-01-18")
    assert recent["date"].max() == pd.Timestamp("2025-01-20")


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
            "--drift-size",
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
    assert payload["calibration_drift"]["status"] in {"stable", "degraded"}
    assert payload["calibration_drift"]["calibration_rows"] > 0
    assert payload["calibration_drift"]["recent_rows"] > 0
    assert any(
        code.startswith("calibration_drift_") for code in payload["records"][0]["reason_codes"]
    )
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


def _prediction_args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "--input",
        str(tmp_path / "ohlcv.csv"),
        "--output",
        str(tmp_path / "latest_predictions.csv"),
        "--json-output",
        str(tmp_path / "latest_warnings.json"),
        "--calibration-size",
        "10",
        "--drift-size",
        "0",
        "--train-size",
        "40",
        "--calibration-method",
        "none",
        "--reliability-members",
        "3",
        "--required-history-rows",
        "50",
        *extra,
    ]


def test_run_prediction_defaults_to_reliability_trust(tmp_path: Path) -> None:
    _ohlcv_frame().to_csv(tmp_path / "ohlcv.csv", index=False)
    args = parse_args(_prediction_args(tmp_path))

    predictions = run_prediction(args)
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    assert args.trust_method == "reliability"
    np.testing.assert_allclose(predictions["trust_score"], np.array([1.0, 1.0]))
    assert predictions["uncertainty_score"].between(0.0, 1.0).all()
    for record in payload["records"]:
        assert any(code.startswith("conformal_set_") for code in record["reason_codes"])


def test_run_prediction_lowers_trust_for_stale_ticker(tmp_path: Path) -> None:
    frame = _ohlcv_frame()
    stale_cutoff = frame["date"].max()
    frame = frame[~((frame["ticker"] == "NVDA") & (frame["date"] == stale_cutoff))]
    frame.to_csv(tmp_path / "ohlcv.csv", index=False)

    predictions = run_prediction(parse_args(_prediction_args(tmp_path)))
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    trust = dict(zip(predictions["ticker"], predictions["trust_score"], strict=True))
    assert trust["2330"] == 1.0
    assert trust["NVDA"] == 0.5
    nvda_codes = next(r["reason_codes"] for r in payload["records"] if r["ticker"] == "NVDA")
    assert "stale_ticker_data" in nvda_codes
    assert "limited_data_quality" in nvda_codes


def test_run_prediction_keeps_legacy_trust_method(tmp_path: Path) -> None:
    _ohlcv_frame().to_csv(tmp_path / "ohlcv.csv", index=False)
    args = parse_args(_prediction_args(tmp_path, "--trust-method", "legacy"))

    predictions = run_prediction(args)
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    assert args.trust_threshold is None
    for record in payload["records"]:
        assert not any(code.startswith("conformal_set_") for code in record["reason_codes"])
    assert (predictions["trust_score"] <= predictions["calibrated_risk_probability"] + 1e-9).all()


def test_run_prediction_reliability_trust_reflects_short_history(tmp_path: Path) -> None:
    _ohlcv_frame().to_csv(tmp_path / "ohlcv.csv", index=False)
    args = parse_args(_prediction_args(tmp_path, "--required-history-rows", "300"))

    predictions = run_prediction(args)
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    assert (predictions["trust_score"] < 0.5).all()
    assert (predictions["warning_level"] != "alert").all()
    assert all("limited_data_quality" in record["reason_codes"] for record in payload["records"])


def test_resolve_trust_threshold_depends_on_trust_method() -> None:
    from scripts.predict_latest_baseline import resolve_trust_threshold

    base = ["--input", "x.csv", "--output", "y.csv", "--json-output", "z.json"]

    assert resolve_trust_threshold(parse_args(base)) == 0.4
    assert resolve_trust_threshold(parse_args([*base, "--trust-method", "legacy"])) == 0.1
    assert resolve_trust_threshold(parse_args([*base, "--trust-threshold", "0.7"])) == 0.7


def test_run_prediction_defaults_to_alert_rate_policies(tmp_path: Path) -> None:
    _ohlcv_frame().to_csv(tmp_path / "ohlcv.csv", index=False)
    args = parse_args(_prediction_args(tmp_path))

    predictions = run_prediction(args)
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    assert (args.alert_policy, args.watch_policy) == ("alert_rate:0.05", "alert_rate:0.2")
    policy = payload["alert_policy"]
    assert policy["alert_policy"] == "alert_rate:0.05"
    assert policy["watch_policy"] == "alert_rate:0.2"
    assert policy["calibration_alert_rate"] <= 0.05
    assert (predictions["watch_threshold"] <= predictions["alert_threshold"]).all()


def test_run_prediction_supports_legacy_objective_and_ratio(tmp_path: Path) -> None:
    _ohlcv_frame().to_csv(tmp_path / "ohlcv.csv", index=False)
    args = parse_args(
        _prediction_args(
            tmp_path,
            "--alert-policy",
            "objective",
            "--watch-policy",
            "ratio",
            "--watch-threshold-ratio",
            "0.5",
            "--min-watch-threshold",
            "0.0",
        )
    )

    predictions = run_prediction(args)
    payload = json.loads((tmp_path / "latest_warnings.json").read_text(encoding="utf-8"))

    np.testing.assert_allclose(
        predictions["watch_threshold"], predictions["alert_threshold"] * 0.5
    )
    assert payload["alert_policy"]["alert_policy"] == "objective:f1"
    assert payload["alert_policy"]["watch_policy"] == "ratio:0.5"


def test_select_warning_thresholds_notes_small_calibration_windows() -> None:
    from scripts.predict_latest_baseline import select_warning_thresholds

    base = ["--input", "x.csv", "--output", "y.csv", "--json-output", "z.json"]
    rng = np.random.default_rng(2)
    labels = (rng.random(63) < 0.2).astype(int)
    probabilities = rng.random(63)

    _, _, small = select_warning_thresholds(parse_args(base), labels, probabilities)
    big_labels = np.tile(labels, 20)
    big_probabilities = np.tile(probabilities, 20)
    _, _, big = select_warning_thresholds(parse_args(base), big_labels, big_probabilities)

    assert "small calibration window" in small.note
    assert big.note == ""
