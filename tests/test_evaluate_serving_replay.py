"""Tests for the serving-scheme replay experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_serving_replay import as_of_positions, parse_args, run
from tests.test_evaluate_selective_trust import _write_ohlcv


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
