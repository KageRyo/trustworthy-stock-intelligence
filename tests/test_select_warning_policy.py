"""Tests for warning-policy candidate selection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.select_warning_policy import parse_args, run_selection, select_policy_candidates


def test_select_policy_candidates_ranks_recall_with_filters() -> None:
    sweep = pd.DataFrame(
        {
            "alert_rate": [0.001, 0.02, 0.03],
            "alert_recall": [0.9, 0.2, 0.4],
            "alert_precision": [0.1, 0.3, 0.2],
            "alert_false_alarm_rate": [0.01, 0.02, 0.03],
            "coverage": [0.4, 0.4, 0.4],
            "selective_risk": [0.2, 0.1, 0.15],
        }
    )

    candidates = select_policy_candidates(sweep, objective="recall", limit=1)

    assert candidates.iloc[0]["alert_recall"] == 0.4


def test_select_policy_candidates_falls_back_when_filters_empty() -> None:
    sweep = pd.DataFrame(
        {
            "alert_rate": [0.9],
            "alert_recall": [0.8],
            "alert_precision": [0.1],
            "alert_false_alarm_rate": [0.8],
            "coverage": [0.9],
            "selective_risk": [0.4],
        }
    )

    candidates = select_policy_candidates(sweep, objective="recall", limit=1)

    assert candidates.iloc[0]["alert_rate"] == 0.9


def test_run_selection_writes_markdown(tmp_path: Path) -> None:
    sweep_path = tmp_path / "threshold_sweep.csv"
    output_path = tmp_path / "policy.md"
    pd.DataFrame(
        {
            "trust_score_method": ["multiplicative"],
            "alert_rate": [0.02],
            "alert_recall": [0.3],
            "alert_precision": [0.2],
            "alert_false_alarm_rate": [0.02],
            "coverage": [0.5],
            "selective_risk": [0.1],
        }
    ).to_csv(sweep_path, index=False)

    args = parse_args(["--sweep", str(sweep_path), "--output", str(output_path)])
    report = run_selection(args)

    assert output_path.exists()
    assert "Recall-Oriented Trust Policy Candidates" in report
