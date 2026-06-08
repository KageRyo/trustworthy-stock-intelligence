"""Tests for deep training utilities."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

trainer = pytest.importorskip("tsi.training.trainer")
ArraySequenceDataset = trainer.ArraySequenceDataset
fit_sequence_standardizer = trainer.fit_sequence_standardizer
resolve_training_device = trainer.resolve_training_device
transform_sequence_features = trainer.transform_sequence_features


def test_array_sequence_dataset_returns_float_tensors() -> None:
    features = np.ones((2, 3, 4), dtype=np.float32)
    labels = np.array([0.0, 1.0], dtype=np.float32)

    dataset = ArraySequenceDataset(features, labels)
    x, y = dataset[1]

    assert len(dataset) == 2
    assert x.shape == (3, 4)
    assert x.dtype == torch.float32
    assert y.dtype == torch.float32
    assert float(y) == 1.0


def test_sequence_standardizer_uses_training_statistics() -> None:
    train_features = np.array(
        [
            [[1.0, 10.0], [3.0, 14.0]],
            [[5.0, 18.0], [7.0, 22.0]],
        ],
        dtype=np.float32,
    )
    standardizer = fit_sequence_standardizer(train_features)

    transformed = transform_sequence_features(train_features, standardizer)

    np.testing.assert_allclose(transformed.mean(axis=(0, 1)), np.array([0.0, 0.0]), atol=1e-6)
    np.testing.assert_allclose(transformed.std(axis=(0, 1)), np.array([1.0, 1.0]), atol=1e-6)


def test_resolve_training_device_requires_cuda_unless_cpu_is_explicitly_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="CUDA is required"):
        resolve_training_device("cuda", allow_cpu=False)

    assert resolve_training_device("cuda", allow_cpu=True).type == "cpu"
