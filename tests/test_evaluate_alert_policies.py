"""Tests for the walk-forward alert policy experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_alert_policies import (
    drawdown_episodes,
    parse_args,
    parse_policies,
    policy_test_metrics,
    run,
)
from tests.test_evaluate_selective_trust import _write_ohlcv


def test_drawdown_episodes_split_runs_by_ticker_and_gaps() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"] * 2),
            "ticker": ["AAA"] * 3 + ["2330"] * 3,
            "risk_label": [1, 1, 0, 1, 0, 1],
        }
    )

    episodes = drawdown_episodes(frame).to_numpy()

    positive = episodes[episodes >= 0]
    assert len(np.unique(positive)) == 3
    assert episodes[0] == episodes[1]
    assert episodes[2] == -1
    assert episodes[3] != episodes[5]


def test_policy_test_metrics_reports_episode_recall_and_volume() -> None:
    labels = np.array([1, 1, 0, 1, 0, 0])
    alerts = np.array([False, True, False, False, True, False])
    episodes = np.array([0, 0, -1, 1, -1, -1])

    metrics = policy_test_metrics(labels, alerts, episodes, tickers=2, dates=3)

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == pytest.approx(1 / 3)
    assert metrics["episode_recall"] == 0.5
    assert metrics["alert_days_per_ticker_month"] == pytest.approx(2 / 6 * 21)


def test_policy_test_metrics_handles_no_alerts() -> None:
    metrics = policy_test_metrics(
        np.array([1, 0]), np.array([False, False]), np.array([0, -1]), tickers=1, dates=2
    )

    assert np.isnan(metrics["precision"])
    assert metrics["recall"] == 0.0
    assert metrics["episode_recall"] == 0.0


def test_parse_policies_reads_kinds_and_targets() -> None:
    policies = parse_policies("f1, target_precision:0.25,alert_rate:0.05", min_alerts=7)

    assert [policy.label for policy in policies] == [
        "f1",
        "target_precision:0.25",
        "alert_rate:0.05",
    ]
    assert all(policy.min_alerts == 7 for policy in policies)


def test_run_writes_summary_for_each_policy(tmp_path: Path) -> None:
    _write_ohlcv(tmp_path / "ohlcv.csv")
    args = parse_args(
        [
            "--input",
            str(tmp_path / "ohlcv.csv"),
            "--output-dir",
            "run",
            "--output-root",
            str(tmp_path),
            "--train-size",
            "120",
            "--calibration-size",
            "40",
            "--test-size",
            "30",
            "--policies",
            "target_precision:0.3,alert_rate:0.1",
            "--min-alerts",
            "3",
        ]
    )

    summary = run(args)

    saved = json.loads((tmp_path / "run" / "summary.json").read_text())
    per_fold = pd.read_csv(tmp_path / "run" / "per_fold.csv")
    assert set(saved["policies"]) == {"f1", "target_precision:0.3", "alert_rate:0.1"}
    assert saved["fold_count"] == summary["fold_count"] >= 1
    assert set(per_fold["policy"]) == set(saved["policies"])
    assert saved["policies"]["alert_rate:0.1"]["alert_rate"] <= 0.3
    for metrics in saved["policies"].values():
        assert metrics["watch_or_alert_rate"] >= metrics["alert_rate"]
        assert metrics["watch_or_alert_recall"] >= metrics["recall"]
