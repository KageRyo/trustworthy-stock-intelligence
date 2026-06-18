"""Serving-ready prediction output schemas."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


WarningLevel = Literal["alert", "watch", "abstain", "no_alert"]
DEFAULT_SCHEMA_VERSION = "v1"


class PredictionRecord(BaseModel):
    """Single warning prediction record for dashboard/API serving."""

    model_config = ConfigDict(extra="forbid")

    date: str
    ticker: str
    model: str
    model_bundle: str
    risk_probability: float = Field(ge=0.0, le=1.0)
    calibrated_risk_probability: float = Field(ge=0.0, le=1.0)
    calibration_method: str
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    alert_threshold: float = Field(ge=0.0, le=1.0)
    watch_threshold: float = Field(ge=0.0, le=1.0)
    warning_level: WarningLevel
    reason_codes: list[str]


class PredictionBatch(BaseModel):
    """Batch of prediction records with generation metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = DEFAULT_SCHEMA_VERSION
    run_id: str = "unknown"
    data_as_of: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    record_count: int | None = None
    records: list[PredictionRecord]

    def model_post_init(self, __context: object) -> None:
        if self.record_count is None:
            self.record_count = len(self.records)
        if self.record_count != len(self.records):
            raise ValueError("record_count must match records length")


def _date_to_iso_date(value: object) -> str:
    timestamp = pd.Timestamp(value)
    return timestamp.date().isoformat()


def build_prediction_batch(
    frame: pd.DataFrame,
    *,
    generated_at: str | None = None,
    run_id: str | None = None,
    data_as_of: str | None = None,
) -> PredictionBatch:
    """Build a serving JSON batch from prediction rows."""

    required_columns = [
        "date",
        "ticker",
        "model",
        "model_bundle",
        "risk_probability",
        "calibrated_risk_probability",
        "calibration_method",
        "uncertainty_score",
        "trust_score",
        "alert_threshold",
        "watch_threshold",
        "warning_level",
        "reason_codes",
    ]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    records = [
        PredictionRecord(
            date=_date_to_iso_date(row["date"]),
            ticker=str(row["ticker"]),
            model=str(row["model"]),
            model_bundle=str(row["model_bundle"]),
            risk_probability=float(row["risk_probability"]),
            calibrated_risk_probability=float(row["calibrated_risk_probability"]),
            calibration_method=str(row["calibration_method"]),
            uncertainty_score=float(row["uncertainty_score"]),
            trust_score=float(row["trust_score"]),
            alert_threshold=float(row["alert_threshold"]),
            watch_threshold=float(row["watch_threshold"]),
            warning_level=row["warning_level"],
            reason_codes=list(row["reason_codes"]),
        )
        for _, row in frame.iterrows()
    ]
    return PredictionBatch(
        run_id=run_id or _infer_run_id(frame),
        data_as_of=data_as_of or _infer_data_as_of(frame),
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        records=records,
    )


def _infer_run_id(frame: pd.DataFrame) -> str:
    if "run_id" in frame.columns and not frame.empty:
        value = frame["run_id"].dropna()
        if not value.empty:
            return str(value.iloc[0])
    if "model_bundle" in frame.columns and not frame.empty:
        value = frame["model_bundle"].dropna()
        if not value.empty:
            return Path(str(value.iloc[0])).name or "unknown"
    return "unknown"


def _infer_data_as_of(frame: pd.DataFrame) -> str:
    if "date" not in frame.columns or frame.empty:
        return ""
    return _date_to_iso_date(pd.to_datetime(frame["date"]).max())


def write_prediction_batch_json(batch: PredictionBatch, path: Path) -> None:
    """Write a prediction batch JSON file atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(batch.model_dump(mode="json"), indent=2) + "\n"
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync for atomic rename durability."""

    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
