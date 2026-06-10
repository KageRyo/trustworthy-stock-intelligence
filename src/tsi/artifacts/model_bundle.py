"""Save and load deep model bundles for repeatable inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch

from tsi.training.trainer import SequenceStandardizer
from tsi.trust.calibration import ProbabilityCalibrator

MODEL_STATE_FILENAME = "model.pt"
METADATA_FILENAME = "metadata.json"
STANDARDIZER_FILENAME = "standardizer.npz"
CALIBRATOR_FILENAME = "calibrator.joblib"


@dataclass(frozen=True)
class ModelBundleMetadata:
    """Metadata required to reconstruct a trained deep risk model."""

    model_type: str
    model_config: dict[str, Any]
    feature_columns: tuple[str, ...]
    lookback: int
    calibration_method: str
    trust_config: dict[str, Any]
    training_config: dict[str, Any]
    alert_threshold: float
    watch_threshold: float
    fold_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["feature_columns"] = list(self.feature_columns)
        return data

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "ModelBundleMetadata":
        return cls(
            model_type=str(data["model_type"]),
            model_config=dict(data["model_config"]),
            feature_columns=tuple(data["feature_columns"]),
            lookback=int(data["lookback"]),
            calibration_method=str(data["calibration_method"]),
            trust_config=dict(data["trust_config"]),
            training_config=dict(data["training_config"]),
            alert_threshold=float(data["alert_threshold"]),
            watch_threshold=float(data["watch_threshold"]),
            fold_id=None if data.get("fold_id") is None else int(data["fold_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True)
class ModelBundle:
    """Loaded model bundle components."""

    path: Path
    metadata: ModelBundleMetadata
    model_state_dict: dict[str, torch.Tensor]
    standardizer: SequenceStandardizer
    calibrator: ProbabilityCalibrator


def state_dict_without_parallel_prefix(
    state_dict: dict[str, torch.Tensor],
) -> dict[str, torch.Tensor]:
    """Return a CPU state dict without DataParallel ``module.`` prefixes."""

    cleaned = {}
    for key, value in state_dict.items():
        cleaned_key = key.removeprefix("module.")
        cleaned[cleaned_key] = value.detach().cpu() if isinstance(value, torch.Tensor) else value
    return cleaned


def save_model_bundle(
    path: Path,
    *,
    model_state_dict: dict[str, torch.Tensor],
    metadata: ModelBundleMetadata,
    standardizer: SequenceStandardizer,
    calibrator: ProbabilityCalibrator,
) -> None:
    """Save a deep model bundle directory."""

    path.mkdir(parents=True, exist_ok=True)
    torch.save(
        state_dict_without_parallel_prefix(model_state_dict),
        path / MODEL_STATE_FILENAME,
    )
    (path / METADATA_FILENAME).write_text(
        json.dumps(metadata.to_json_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez(
        path / STANDARDIZER_FILENAME,
        mean=np.asarray(standardizer.mean, dtype=np.float32),
        scale=np.asarray(standardizer.scale, dtype=np.float32),
    )
    joblib.dump(calibrator, path / CALIBRATOR_FILENAME)


def load_model_bundle(path: Path, *, map_location: str | torch.device = "cpu") -> ModelBundle:
    """Load a model bundle from disk."""

    metadata_path = path / METADATA_FILENAME
    state_path = path / MODEL_STATE_FILENAME
    standardizer_path = path / STANDARDIZER_FILENAME
    calibrator_path = path / CALIBRATOR_FILENAME
    missing = [
        str(candidate)
        for candidate in (metadata_path, state_path, standardizer_path, calibrator_path)
        if not candidate.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing model bundle artifact(s): {', '.join(missing)}")

    metadata = ModelBundleMetadata.from_json_dict(json.loads(metadata_path.read_text(encoding="utf-8")))
    standardizer_values = np.load(standardizer_path)
    state_dict = torch.load(state_path, map_location=map_location, weights_only=True)
    calibrator = joblib.load(calibrator_path)
    return ModelBundle(
        path=path,
        metadata=metadata,
        model_state_dict=state_dict,
        standardizer=SequenceStandardizer(
            mean=standardizer_values["mean"].astype(np.float32),
            scale=standardizer_values["scale"].astype(np.float32),
        ),
        calibrator=calibrator,
    )
