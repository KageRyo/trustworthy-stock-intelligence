"""Tests for the Temporal Transformer risk model."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
temporal_transformer = pytest.importorskip("tsi.models.temporal_transformer")
TemporalTransformerRiskModel = temporal_transformer.TemporalTransformerRiskModel


def test_temporal_transformer_returns_logits_and_attention_weights() -> None:
    torch.manual_seed(42)
    model = TemporalTransformerRiskModel(
        input_size=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        dropout=0.0,
        max_sequence_length=8,
    )
    model.eval()
    features = torch.randn(4, 6, 5)

    output = model(features, return_attention=True)

    assert output.logits.shape == (4,)
    assert output.attention_weights.shape == (4, 6)
    torch.testing.assert_close(
        output.attention_weights.sum(dim=1),
        torch.ones(4),
    )


def test_temporal_transformer_forward_returns_logits_by_default() -> None:
    model = TemporalTransformerRiskModel(
        input_size=3,
        d_model=12,
        num_heads=3,
        num_layers=1,
        dropout=0.0,
        max_sequence_length=5,
    )
    features = torch.randn(2, 5, 3)

    logits = model(features)

    assert logits.shape == (2,)


def test_temporal_transformer_rejects_invalid_input_shape() -> None:
    model = TemporalTransformerRiskModel(
        input_size=3,
        d_model=12,
        num_heads=3,
        num_layers=1,
        dropout=0.0,
        max_sequence_length=5,
    )

    with pytest.raises(ValueError, match="Expected input shape"):
        model(torch.randn(2, 3))

    with pytest.raises(ValueError, match="Expected feature dimension"):
        model(torch.randn(2, 5, 4))

    with pytest.raises(ValueError, match="exceeds max_sequence_length"):
        model(torch.randn(2, 6, 3))
