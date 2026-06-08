"""PyTorch training helpers for deep stock risk models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


class BinarySequenceModel(Protocol):
    """Protocol for models that return one binary logit per sequence."""

    def __call__(self, features: torch.Tensor) -> torch.Tensor:
        ...


@dataclass(frozen=True)
class SequenceStandardizer:
    """Feature scaling statistics fit only on training sequences."""

    mean: np.ndarray
    scale: np.ndarray


@dataclass(frozen=True)
class DeepTrainingConfig:
    """Training hyperparameters for a binary sequence model."""

    epochs: int = 20
    batch_size: int = 256
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    num_workers: int = 0


@dataclass(frozen=True)
class DeepTrainingResult:
    """Training history and hardware metadata."""

    train_loss: list[float]
    validation_loss: list[float]
    device: str
    gpu_count: int
    used_data_parallel: bool


class ArraySequenceDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """Torch dataset backed by in-memory numpy sequence arrays."""

    def __init__(self, features: np.ndarray, labels: np.ndarray) -> None:
        if features.ndim != 3:
            raise ValueError("features must have shape [samples, lookback, feature_count]")
        if labels.ndim != 1:
            raise ValueError("labels must have shape [samples]")
        if len(features) != len(labels):
            raise ValueError("features and labels must have matching sample counts")
        self.features = torch.as_tensor(features, dtype=torch.float32)
        self.labels = torch.as_tensor(labels, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.features[index], self.labels[index]


def fit_sequence_standardizer(features: np.ndarray) -> SequenceStandardizer:
    """Fit per-feature normalization statistics over samples and timesteps."""

    if features.ndim != 3:
        raise ValueError("features must have shape [samples, lookback, feature_count]")
    mean = features.mean(axis=(0, 1), keepdims=True)
    scale = features.std(axis=(0, 1), keepdims=True)
    scale = np.where(scale < 1e-8, 1.0, scale)
    return SequenceStandardizer(mean=mean.astype(np.float32), scale=scale.astype(np.float32))


def transform_sequence_features(
    features: np.ndarray,
    standardizer: SequenceStandardizer,
) -> np.ndarray:
    """Apply training-set standardization statistics to sequence features."""

    return ((features - standardizer.mean) / standardizer.scale).astype(np.float32)


def resolve_training_device(device_name: str, *, allow_cpu: bool = False) -> torch.device:
    """Resolve the training device, requiring CUDA by default."""

    requested = device_name.lower()
    if requested not in {"cuda", "cpu", "auto"}:
        raise ValueError("device must be one of: cuda, cpu, auto")

    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if allow_cpu:
            return torch.device("cpu")
        raise RuntimeError("CUDA is required for deep training; pass --allow-cpu only for tests")

    if requested == "cuda":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if allow_cpu:
            return torch.device("cpu")
        raise RuntimeError("CUDA is required for deep training; pass --allow-cpu only for tests")

    if not allow_cpu:
        raise RuntimeError("CPU training is disabled by default; pass --allow-cpu only for tests")
    return torch.device("cpu")


def maybe_wrap_multi_gpu(
    model: nn.Module,
    device: torch.device,
    *,
    use_multi_gpu: bool = True,
) -> tuple[nn.Module, int, bool]:
    """Move the model to device and use DataParallel when multiple GPUs exist."""

    model = model.to(device)
    gpu_count = torch.cuda.device_count() if device.type == "cuda" else 0
    if use_multi_gpu and gpu_count > 1:
        return nn.DataParallel(model), gpu_count, True
    return model, gpu_count, False


def _positive_class_weight(labels: np.ndarray, device: torch.device) -> torch.Tensor:
    positives = float(np.sum(labels == 1.0))
    negatives = float(np.sum(labels == 0.0))
    value = negatives / positives if positives > 0.0 and negatives > 0.0 else 1.0
    return torch.tensor(value, dtype=torch.float32, device=device)


def _run_epoch(
    model: nn.Module,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> float:
    is_training = optimizer is not None
    model.train(is_training)
    total_loss = 0.0
    total_samples = 0

    for features, labels in loader:
        features = features.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(is_training):
            logits = model(features)
            loss = criterion(logits, labels)
            if optimizer is not None:
                loss.backward()
                optimizer.step()

        batch_size = int(labels.shape[0])
        total_loss += float(loss.detach().cpu()) * batch_size
        total_samples += batch_size

    return total_loss / max(total_samples, 1)


def train_binary_sequence_model(
    model: nn.Module,
    train_features: np.ndarray,
    train_labels: np.ndarray,
    validation_features: np.ndarray,
    validation_labels: np.ndarray,
    *,
    config: DeepTrainingConfig,
    device: torch.device,
    use_multi_gpu: bool = True,
) -> tuple[nn.Module, DeepTrainingResult]:
    """Train a binary sequence classifier and return the trained model."""

    model, gpu_count, used_data_parallel = maybe_wrap_multi_gpu(
        model,
        device,
        use_multi_gpu=use_multi_gpu,
    )
    train_loader = DataLoader(
        ArraySequenceDataset(train_features, train_labels),
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        ArraySequenceDataset(validation_features, validation_labels),
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=device.type == "cuda",
    )

    criterion = nn.BCEWithLogitsLoss(pos_weight=_positive_class_weight(train_labels, device))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    train_loss: list[float] = []
    validation_loss: list[float] = []
    for _ in range(config.epochs):
        train_loss.append(_run_epoch(model, train_loader, criterion, device, optimizer))
        with torch.no_grad():
            validation_loss.append(_run_epoch(model, validation_loader, criterion, device))

    return model, DeepTrainingResult(
        train_loss=train_loss,
        validation_loss=validation_loss,
        device=str(device),
        gpu_count=gpu_count,
        used_data_parallel=used_data_parallel,
    )


def predict_probabilities(
    model: nn.Module,
    features: np.ndarray,
    *,
    batch_size: int,
    device: torch.device,
    num_workers: int = 0,
) -> np.ndarray:
    """Predict sigmoid probabilities for sequence features."""

    loader = DataLoader(
        ArraySequenceDataset(features, np.zeros(len(features), dtype=np.float32)),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
    )
    model.eval()
    probabilities: list[np.ndarray] = []
    with torch.no_grad():
        for batch_features, _ in loader:
            batch_features = batch_features.to(device, non_blocking=True)
            logits = model(batch_features)
            probabilities.append(torch.sigmoid(logits).detach().cpu().numpy())
    return np.concatenate(probabilities).astype(float)
