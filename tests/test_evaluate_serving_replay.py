"""Tests for the serving-scheme replay experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_serving_replay import (
    _fit,
    _labeled_frame,
    _replay_single_tickers,
    as_of_positions,
    parse_args,
    run,
)
from tests.test_evaluate_selective_trust import _write_ohlcv
from tsi.features.sets import resolve_feature_set


def _args(tmp_path: Path, *extra: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_ohlcv(tmp_path / "ohlcv.csv")
    return parse_args(
        [
            "--input",
            str(tmp_path / "ohlcv.csv"),
            "--output-dir",
            "run",
            "--output-root",
            str(tmp_path),
            "--calibration-size",
            "30",
            "--drift-size",
            "10",
            "--test-size",
            "20",
            "--step-size",
            "20",
            "--min-history-dates",
            "120",
            *extra,
        ]
    )


def test_as_of_positions_leave_room_for_history_and_test() -> None:
    assert as_of_positions(200, min_history=120, test_size=20, step=20) == [120, 140, 160]
    with pytest.raises(ValueError, match="positive"):
        as_of_positions(200, min_history=120, test_size=20, step=0)


def test_run_replays_pooled_and_single_ticker_models(tmp_path: Path) -> None:
    summary = run(_args(tmp_path))

    pooled = pd.read_csv(tmp_path / "run" / "pooled_as_of.csv")
    single = pd.read_csv(tmp_path / "run" / "single_as_of.csv", dtype={"ticker": str})
    saved = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert saved == summary
    assert len(pooled) == summary["pooled"]["as_of_dates"] >= 3
    assert set(single["ticker"]) <= {"AAA", "BBB", "2330", "00981A"}
    for frame in (pooled, single):
        increasing = frame[frame["platt_slope"] > 0]
        np.testing.assert_allclose(increasing["auc_platt"], increasing["auc_raw"], atol=1e-9)
        np.testing.assert_allclose(frame["auc_platt_monotone"], frame["auc_raw"], atol=1e-9)
    assert summary["pooled"]["nonpositive_slope"] == int((pooled["platt_slope"] <= 0).sum())
    assert summary["single_ticker"]["tickers"] == single["ticker"].nunique()
    assert {"pooled", "single"} <= set(summary["per_ticker_history_auc"])
    assert summary["protocol"]["feature_set"] == "technical_range"


def test_run_is_deterministic(tmp_path: Path) -> None:
    first = run(_args(tmp_path / "a"))
    second = run(_args(tmp_path / "b"))

    first.pop("input")
    second.pop("input")
    assert first == second


def _write_unseen_ohlcv(path: Path) -> None:
    rng = np.random.default_rng(9)
    dates = pd.bdate_range("2020-01-01", periods=260)
    rows = []
    for ticker in ("CCC", "5240", "02001L"):
        close = 50.0 * np.exp(np.cumsum(rng.normal(0, rng.uniform(0.01, 0.04), len(dates))))
        for date, price in zip(dates, close, strict=True):
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "adj_close": price,
                    "volume": float(rng.integers(1_000, 10_000)),
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_score_input_applies_the_pooled_model_to_unseen_tickers(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_unseen_ohlcv(tmp_path / "unseen.csv")

    summary = run(_args(tmp_path, "--score-input", str(tmp_path / "unseen.csv")))

    single = pd.read_csv(tmp_path / "run" / "single_as_of.csv", dtype={"ticker": str})
    history = pd.read_csv(tmp_path / "run" / "per_ticker_history_auc.csv", dtype={"ticker": str})
    assert set(single["ticker"]) <= {"CCC", "5240", "02001L"}
    assert set(history["ticker"]) <= {"CCC", "5240", "02001L"}
    assert summary["score_input"] == str(tmp_path / "unseen.csv")
    assert summary["score_input_sha256"]
    assert summary["pooled"]["as_of_dates"] >= 3


def test_single_ticker_replay_skips_tickers_without_rows_in_the_next_step(tmp_path: Path) -> None:
    args = _args(tmp_path)
    columns = resolve_feature_set(args.feature_set)
    frame = _labeled_frame(args.input, args, columns)
    dates = pd.Index(sorted(frame["date"].unique()))
    position = 150
    known = frame[frame["date"] <= dates[position - args.horizon]]
    test = frame[(frame["date"] > dates[position]) & (frame["date"] <= dates[position + 40])]
    next_step = test[(test["date"] <= dates[position + 20]) & (test["ticker"] != "AAA")]
    pooled = _fit(known, args, columns)
    assert pooled is not None

    rows, history = _replay_single_tickers(pooled[0], known, test, next_step, args, columns)

    scored = set(pd.concat(history)["ticker"])
    assert "AAA" not in scored
    assert scored
    assert rows
