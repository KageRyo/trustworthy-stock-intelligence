"""Temporal Transformer model for drawdown risk prediction."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class TemporalTransformerOutput:
    """Model logits with optional attention-pooling weights."""

    logits: torch.Tensor
    attention_weights: torch.Tensor


class TemporalTransformerRiskModel(nn.Module):
    """Transformer encoder over fixed-length market feature windows.

    Input shape is ``[batch, sequence_length, input_size]``. The model returns
    one logit per sample for use with ``BCEWithLogitsLoss``.
    """

    def __init__(
        self,
        *,
        input_size: int,
        d_model: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        max_sequence_length: int = 128,
    ) -> None:
        super().__init__()
        if input_size < 1:
            raise ValueError("input_size must be at least 1")
        if d_model < 1:
            raise ValueError("d_model must be at least 1")
        if num_heads < 1:
            raise ValueError("num_heads must be at least 1")
        if d_model % num_heads != 0:
            raise ValueError("d_model must be divisible by num_heads")
        if num_layers < 1:
            raise ValueError("num_layers must be at least 1")
        if max_sequence_length < 1:
            raise ValueError("max_sequence_length must be at least 1")

        self.input_size = input_size
        self.d_model = d_model
        self.max_sequence_length = max_sequence_length

        self.input_projection = nn.Linear(input_size, d_model)
        self.position_embedding = nn.Parameter(torch.zeros(max_sequence_length, d_model))

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.attention_pool = nn.Linear(d_model, 1)
        self.head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Dropout(dropout),
            nn.Linear(d_model, 1),
        )
        self._reset_parameters()

    def _reset_parameters(self) -> None:
        nn.init.normal_(self.position_embedding, mean=0.0, std=0.02)
        nn.init.xavier_uniform_(self.input_projection.weight)
        nn.init.zeros_(self.input_projection.bias)
        nn.init.xavier_uniform_(self.attention_pool.weight)
        nn.init.zeros_(self.attention_pool.bias)

    def _validate_input(self, features: torch.Tensor) -> None:
        if features.dim() != 3:
            raise ValueError(
                "Expected input shape [batch, sequence_length, input_size], "
                f"got {tuple(features.shape)}"
            )
        if features.shape[-1] != self.input_size:
            raise ValueError(
                f"Expected feature dimension {self.input_size}, got {features.shape[-1]}"
            )
        if features.shape[1] > self.max_sequence_length:
            raise ValueError(
                f"sequence_length {features.shape[1]} exceeds "
                f"max_sequence_length {self.max_sequence_length}"
            )

    def encode(self, features: torch.Tensor) -> torch.Tensor:
        """Encode a batch of fixed-length feature windows."""

        self._validate_input(features)
        sequence_length = features.shape[1]
        projected = self.input_projection(features)
        positioned = projected + self.position_embedding[:sequence_length].unsqueeze(0)
        return self.encoder(positioned)

    def forward(
        self,
        features: torch.Tensor,
        *,
        return_attention: bool = False,
    ) -> torch.Tensor | TemporalTransformerOutput:
        encoded = self.encode(features)
        attention_logits = self.attention_pool(encoded).squeeze(-1)
        attention_weights = torch.softmax(attention_logits, dim=1)
        pooled = torch.sum(encoded * attention_weights.unsqueeze(-1), dim=1)
        logits = self.head(pooled).squeeze(-1)
        if return_attention:
            return TemporalTransformerOutput(logits=logits, attention_weights=attention_weights)
        return logits
