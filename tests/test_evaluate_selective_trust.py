"""Tests for the walk-forward selective trust experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.evaluate_selective_trust import CONFIDENCE_SIGNALS, parse_args, run


def _write_ohlcv(path: Path) -> None:
    rng = np.random.default_rng(4)
    dates = pd.bdate_range("2020-01-01", periods=260)
    rows = []
    for ticker in ("AAA", "BBB", "2330", "00981A"):
        volatility = rng.uniform(0.01, 0.04)
        close = 100.0 * np.exp(np.cumsum(rng.normal(0, volatility, len(dates))))
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


def test_run_writes_summary_and_curves(tmp_path: Path) -> None:
    input_path = tmp_path / "ohlcv.csv"
    _write_ohlcv(input_path)
    output_dir = tmp_path / "run"
    args = parse_args(
        [
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--train-size",
            "120",
            "--calibration-size",
            "40",
            "--test-size",
            "30",
            "--n-members",
            "3",
        ]
    )

    summary = run(args)

    saved = json.loads((output_dir / "summary.json").read_text())
    curves = pd.read_csv(output_dir / "risk_coverage.csv")
    assert saved["fold_count"] == summary["fold_count"] >= 1
    assert set(saved["pooled"]) == set(CONFIDENCE_SIGNALS)
    assert set(curves["signal"]) == set(CONFIDENCE_SIGNALS)
    assert saved["protocol"]["purge_size"] == 5
    assert len(saved["epistemic_alert_gate"]) == 4
    assert len(saved["uncertainty_abstain"]) == 2
    assert abs(saved["correlation_with_risk_probability"]["legacy_trust"]) > 0.5
