"""Tests for the paired-bootstrap experiment CLI helpers."""

from __future__ import annotations

import pytest

from scripts.paired_bootstrap import build_bootstrap_report, parse_args


def test_build_bootstrap_report_uses_paired_summary_folds() -> None:
    summary = {
        "input": "data.csv",
        "model_type": "logistic",
        "horizon": 5,
        "purge_size": 5,
        "folds": [
            {
                "fold_id": 0,
                "raw_metrics": {"brier_score": 0.2},
                "calibrated_metrics": {"brier_score": 0.1},
            },
            {
                "fold_id": 1,
                "raw_metrics": {"brier_score": 0.3},
                "calibrated_metrics": {"brier_score": 0.2},
            },
        ],
    }

    report = build_bootstrap_report(
        summary,
        baseline="raw",
        comparison="calibrated",
        metrics=["brier_score"],
        resamples=100,
        confidence=0.95,
        seed=7,
    )

    assert report["baseline"] == "raw"
    assert report["comparison"] == "calibrated"
    assert report["statistics"]["fold_count"] == 2
    assert report["statistics"]["metrics"]["brier_score"]["delta"]["estimate"] == pytest.approx(-0.1)


def test_parse_args_requires_explicit_pair_and_output() -> None:
    args = parse_args(
        [
            "--summary",
            "summary.json",
            "--baseline",
            "raw",
            "--comparison",
            "calibrated",
            "--output",
            "intervals.json",
        ]
    )

    assert args.resamples == 4000
    assert args.confidence == 0.95
