"""Tests for serving prediction JSON schema."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from tsi.serving.schema import PredictionBatch, build_prediction_batch, write_prediction_batch_json


def test_prediction_batch_builds_records_from_frame() -> None:
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-06-08")],
            "ticker": ["AAPL"],
            "model": ["temporal_transformer"],
            "model_bundle": ["model_bundle"],
            "risk_probability": [0.18],
            "calibrated_risk_probability": [0.12],
            "calibration_method": ["platt"],
            "uncertainty_score": [0.43],
            "trust_score": [0.09],
            "alert_threshold": [0.2],
            "watch_threshold": [0.16],
            "warning_level": ["watch"],
            "reason_codes": [["probability_above_watch_threshold"]],
        }
    )

    batch = build_prediction_batch(frame, generated_at="2026-06-10T00:00:00+00:00")

    assert batch.record_count == 1
    assert batch.schema_version == "v1"
    assert batch.run_id == "model_bundle"
    assert batch.data_as_of == "2026-06-08"
    assert batch.generated_at == "2026-06-10T00:00:00+00:00"
    assert batch.records[0].ticker == "AAPL"
    assert batch.records[0].date == "2026-06-08"
    assert batch.records[0].reason_codes == ["probability_above_watch_threshold"]


def test_prediction_batch_json_round_trips(tmp_path: Path) -> None:
    batch = PredictionBatch(
        generated_at="2026-06-10T00:00:00+00:00",
        records=[
            {
                "date": "2026-06-08",
                "ticker": "AAPL",
                "model": "temporal_transformer",
                "model_bundle": "model_bundle",
                "risk_probability": 0.18,
                "calibrated_risk_probability": 0.12,
                "calibration_method": "platt",
                "uncertainty_score": 0.43,
                "trust_score": 0.09,
                "alert_threshold": 0.2,
                "watch_threshold": 0.16,
                "warning_level": "watch",
                "reason_codes": ["probability_above_watch_threshold"],
            }
        ],
    )

    output = tmp_path / "warnings.json"
    write_prediction_batch_json(batch, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "v1"
    assert payload["run_id"] == "unknown"
    assert payload["record_count"] == 1
    assert payload["records"][0]["ticker"] == "AAPL"


def test_prediction_batch_json_replaces_existing_file_atomically(tmp_path: Path) -> None:
    output = tmp_path / "warnings.json"
    output.write_text('{"record_count": 999, "records": []}\n', encoding="utf-8")
    batch = PredictionBatch(generated_at="2026-06-10T00:00:00+00:00", records=[])

    write_prediction_batch_json(batch, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["record_count"] == 0
    assert not list(tmp_path.glob("*.tmp"))


def test_prediction_batch_json_does_not_replace_existing_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "warnings.json"
    output.write_text('{"status": "old"}\n', encoding="utf-8")
    batch = PredictionBatch(generated_at="2026-06-10T00:00:00+00:00", records=[])

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError(f"replace failed: {source} -> {destination}")

    monkeypatch.setattr(os, "replace", fail_replace)

    try:
        write_prediction_batch_json(batch, output)
    except OSError as error:
        assert "replace failed" in str(error)
    else:
        raise AssertionError("Expected OSError from failed atomic replace")

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "old"}
    assert not list(tmp_path.glob("*.tmp"))
