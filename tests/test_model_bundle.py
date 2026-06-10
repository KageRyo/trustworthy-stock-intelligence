"""Tests for deep model bundle persistence."""

from __future__ import annotations

import numpy as np
import torch

from tsi.artifacts.model_bundle import (
    ModelBundleMetadata,
    load_model_bundle,
    save_model_bundle,
    state_dict_without_parallel_prefix,
)
from tsi.models.temporal_transformer import TemporalTransformerRiskModel
from tsi.training.trainer import SequenceStandardizer
from tsi.trust.calibration import IdentityCalibrator


def test_state_dict_without_parallel_prefix_removes_module_prefix() -> None:
    state = {
        "module.head.weight": torch.ones(1),
        "module.head.bias": torch.zeros(1),
    }

    cleaned = state_dict_without_parallel_prefix(state)

    assert sorted(cleaned) == ["head.bias", "head.weight"]


def test_model_bundle_save_and_load_round_trips_components(tmp_path) -> None:
    model = TemporalTransformerRiskModel(
        input_size=2,
        d_model=8,
        num_heads=2,
        num_layers=1,
        dim_feedforward=16,
        dropout=0.0,
        max_sequence_length=4,
    )
    metadata = ModelBundleMetadata(
        model_type="temporal_transformer",
        model_config={
            "input_size": 2,
            "d_model": 8,
            "num_heads": 2,
            "num_layers": 1,
            "dim_feedforward": 16,
            "dropout": 0.0,
            "max_sequence_length": 4,
        },
        feature_columns=("feature_a", "feature_b"),
        lookback=4,
        calibration_method="none",
        trust_config={"trust_score_method": "multiplicative"},
        training_config={"epochs": 1},
        alert_threshold=0.3,
        watch_threshold=0.2,
        fold_id=7,
    )
    standardizer = SequenceStandardizer(
        mean=np.asarray([[[1.0, 2.0]]], dtype=np.float32),
        scale=np.asarray([[[0.5, 0.25]]], dtype=np.float32),
    )

    save_model_bundle(
        tmp_path,
        model_state_dict=model.state_dict(),
        metadata=metadata,
        standardizer=standardizer,
        calibrator=IdentityCalibrator(),
    )
    bundle = load_model_bundle(tmp_path)

    assert bundle.metadata.fold_id == 7
    assert bundle.metadata.feature_columns == ("feature_a", "feature_b")
    np.testing.assert_allclose(bundle.standardizer.mean, standardizer.mean)
    np.testing.assert_allclose(bundle.standardizer.scale, standardizer.scale)
    np.testing.assert_allclose(bundle.calibrator.predict(np.array([0.2, 1.2])), np.array([0.2, 1.0]))
    assert set(bundle.model_state_dict) == set(model.state_dict())
