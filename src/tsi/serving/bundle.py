"""Schema-validated serving model bundles.

A batch run fits the pooled serving model on a reference universe. The bundle stores that fitted
model as plain numbers: logistic parameters, the calibrator, the alert and watch thresholds, the
calibration-drift result, and the reliability references. On-demand analysis loads it to score a
new ticker with the pooled model instead of fitting that ticker alone (Experiment 020).
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tsi.models.linear import LinearLogitParams
from tsi.serving.schema import AlertPolicyMetadata, CalibrationDriftMetadata
from tsi.trust.calibration import CalibratorParams
from tsi.trust.reliability import ReliabilityParams

SERVING_BUNDLE_SCHEMA_VERSION = "serving_model_bundle.v1"


class ServingModelBundle(BaseModel):
    """A fitted pooled serving model and the provenance needed to audit it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["serving_model_bundle.v1"] = SERVING_BUNDLE_SCHEMA_VERSION
    run_id: str
    created_at: datetime
    source_input: str
    source_input_sha256: str
    tickers: int = Field(ge=1)
    training_rows: int = Field(ge=1)
    data_as_of: str
    feature_interval: str
    feature_set: str
    feature_columns: list[str]
    horizon: int = Field(ge=1)
    drawdown_threshold: float
    model: LinearLogitParams
    calibration_method: str
    calibrator: CalibratorParams
    calibration_drift: CalibrationDriftMetadata
    drift_reason_codes: list[str]
    drift_trust_multiplier: float | None = Field(default=None, ge=0.0, le=1.0)
    drift_abstain: bool
    alert_threshold: float
    watch_threshold: float
    alert_policy: AlertPolicyMetadata
    trust_threshold: float
    uncertainty_threshold: float
    reliability: ReliabilityParams


def write_serving_bundle(bundle: ServingModelBundle, path: Path) -> None:
    """Write ``bundle`` atomically so a concurrent reader never sees a partial file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(bundle.model_dump_json())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_serving_bundle(path: Path) -> ServingModelBundle:
    """Read and validate a bundle written by ``write_serving_bundle``."""

    return ServingModelBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))
