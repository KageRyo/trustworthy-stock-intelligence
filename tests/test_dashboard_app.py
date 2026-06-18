"""Tests for Streamlit dashboard data helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from dashboard.app import (
    build_metric_comparison_frame,
    build_live_warning_frame,
    fetch_api_json,
    load_live_api_data,
    build_warning_distribution_frame,
    load_run_artifacts,
    normalize_api_base_url,
    select_threshold_tables,
)


def test_load_run_artifacts_reads_required_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"training_config": {"epochs": 1}}))
    (run_dir / "warning_eval.json").write_text(json.dumps({"overall": {"alert_count": 2}}))
    (run_dir / "diagnostics.json").write_text(json.dumps({"row_count": 4}))
    pd.DataFrame({"coverage": [0.5]}).to_csv(run_dir / "threshold_sweep.csv", index=False)

    artifacts = load_run_artifacts(run_dir)

    assert artifacts.run_dir == run_dir
    assert artifacts.summary["training_config"]["epochs"] == 1
    assert artifacts.warning_eval["overall"]["alert_count"] == 2
    assert artifacts.diagnostics["row_count"] == 4
    assert artifacts.threshold_sweep["coverage"].tolist() == [0.5]


def test_build_warning_distribution_frame_uses_counts_and_rates() -> None:
    frame = build_warning_distribution_frame(
        {
            "alert_count": 2,
            "alert_rate": 0.1,
            "watch_count": 3,
            "watch_rate": 0.15,
            "abstain_count": 1,
            "abstain_rate": 0.05,
            "no_alert_count": 14,
            "no_alert_rate": 0.7,
        }
    )

    assert frame["warning_level"].tolist() == ["alert", "watch", "abstain", "no_alert"]
    assert frame["count"].tolist() == [2.0, 3.0, 1.0, 14.0]
    assert frame["rate"].tolist() == [0.1, 0.15, 0.05, 0.7]


def test_build_metric_comparison_frame_extracts_core_metrics() -> None:
    frame = build_metric_comparison_frame(
        {
            "summary": {
                "raw": {"brier_score": 0.2, "ece": 0.3},
                "calibrated": {"brier_score": 0.1, "ece": 0.05},
                "tuned": {"brier_score": 0.1, "ece": 0.05},
            }
        }
    )

    assert frame["metric"].tolist() == ["auc", "f1", "brier_score", "ece", "precision", "recall"]
    assert frame.loc[frame["metric"] == "brier_score", "raw"].iloc[0] == 0.2
    assert frame.loc[frame["metric"] == "ece", "calibrated"].iloc[0] == 0.05


def test_select_threshold_tables_returns_ranked_views() -> None:
    sweep = pd.DataFrame(
        {
            "trust_score_method": ["multiplicative", "multiplicative", "subtractive"],
            "coverage": [0.4, 0.2, 0.5],
            "selective_risk": [0.2, 0.1, 0.05],
            "alert_precision": [0.3, 0.5, 0.0],
            "alert_false_alarm_rate": [0.03, 0.02, 0.0],
            "alert_rate": [0.02, 0.01, 0.0],
        }
    )

    tables = select_threshold_tables(sweep, limit=2)

    assert tables["balanced"].iloc[0]["trust_score_method"] == "multiplicative"
    assert tables["top_by_alert_precision"].iloc[0]["alert_precision"] == 0.5
    assert len(tables["top_by_selective_risk"]) == 2


def test_normalize_api_base_url_removes_trailing_slash() -> None:
    assert normalize_api_base_url("http://localhost:8080/") == "http://localhost:8080"


def test_build_live_warning_frame_extracts_records() -> None:
    frame = build_live_warning_frame(
        {
            "record_count": 1,
            "records": [
                {
                    "date": "2026-06-08",
                    "ticker": "AAPL",
                    "warning_level": "watch",
                    "calibrated_risk_probability": 0.12,
                    "trust_score": 0.09,
                    "uncertainty_score": 0.43,
                    "reason_codes": ["probability_above_watch_threshold"],
                }
            ],
        }
    )

    assert frame["ticker"].tolist() == ["AAPL"]
    assert frame["reason_codes"].tolist() == ["probability_above_watch_threshold"]


def test_build_live_warning_frame_handles_empty_records() -> None:
    frame = build_live_warning_frame({"record_count": 0, "records": []})

    assert frame.empty
    assert frame.columns.tolist() == [
        "date",
        "ticker",
        "warning_level",
        "calibrated_risk_probability",
        "trust_score",
        "uncertainty_score",
        "reason_codes",
    ]


def test_fetch_api_json_propagates_request_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(
        url: str,
        *,
        params: dict[str, object] | None = None,
        timeout: float,
    ) -> object:
        raise requests.Timeout(f"timed out: {url} {params} {timeout}")

    monkeypatch.setattr("dashboard.app.requests.get", fake_get)

    with pytest.raises(requests.Timeout):
        fetch_api_json("http://localhost:8080", "/health", timeout=1.0)


def test_load_live_api_data_fetches_core_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object] | None]] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    def fake_get(
        url: str,
        *,
        params: dict[str, object] | None = None,
        timeout: float,
    ) -> FakeResponse:
        calls.append((url, params))
        if url.endswith("/health"):
            return FakeResponse({"status": "ok", "record_count": 2})
        if url.endswith("/api/v1/status"):
            return FakeResponse({"warnings_loaded": True, "last_loaded_at": "2026-06-10T00:00:00Z"})
        if url.endswith("/api/v1/models/current"):
            return FakeResponse({"model": "temporal_transformer", "record_count": 2})
        if params == {"level": "alert", "sort": "trust_score", "order": "desc", "limit": 5}:
            return FakeResponse({"record_count": 0, "records": []})
        if params == {
            "level": "watch",
            "sort": "calibrated_risk_probability",
            "order": "desc",
            "limit": 5,
        }:
            return FakeResponse({"record_count": 1, "records": [{"ticker": "AAPL"}]})
        raise AssertionError(f"unexpected request: {url} {params}")

    monkeypatch.setattr("dashboard.app.requests.get", fake_get)

    data = load_live_api_data("http://localhost:8080/", limit=5, timeout=1.0)

    assert data.health["status"] == "ok"
    assert data.current_model["model"] == "temporal_transformer"
    assert data.watch_warnings["record_count"] == 1
    assert calls[0][0] == "http://localhost:8080/health"
