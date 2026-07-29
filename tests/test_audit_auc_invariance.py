"""Tests for raw-versus-Platt AUC invariance auditing."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.audit_auc_invariance import (
    assert_auc_audit_invariants,
    build_auc_audit,
)


def _calibrate(raw: list[float], *, coefficient: float, intercept: float) -> np.ndarray:
    values = np.asarray(raw, dtype=float)
    return 1.0 / (1.0 + np.exp(-(coefficient * values + intercept)))


def _predictions(
    *,
    labels: list[int],
    raw: list[float],
    calibrated: np.ndarray,
    fold_id: int = 0,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fold_id": [fold_id] * len(labels),
            "ticker": ["AAPL"] * len(labels),
            "date": pd.date_range("2024-01-02", periods=len(labels), freq="D"),
            "risk_label": labels,
            "risk_probability": raw,
            "calibrated_risk_probability": calibrated,
        }
    )


def test_positive_platt_coefficient_preserves_fold_auc() -> None:
    raw = [0.1, 0.3, 0.7, 0.9]
    predictions = _predictions(
        labels=[0, 0, 1, 1],
        raw=raw,
        calibrated=_calibrate(raw, coefficient=2.0, intercept=-1.0),
    )

    overview, diagnostics = build_auc_audit(predictions)
    fold = diagnostics["folds"][0]

    assert fold["coefficient_sign"] == "positive"
    assert fold["raw_sample_key_hash"].startswith("sha256:")
    assert fold["raw_sample_key_hash"] == fold["calibrated_sample_key_hash"]
    assert fold["raw_auc"] == fold["calibrated_auc"]
    assert fold["ranking_inversion_count"] == 0
    assert fold["strict_raw_order_pair_count"] == 6
    assert fold["spearman_rank_correlation"] == pytest.approx(1.0)
    assert overview["invariants"]["positive_coefficient_auc_invariance"]["passed"]
    assert_auc_audit_invariants(overview)


def test_negative_platt_coefficient_reverses_fold_ranking() -> None:
    raw = [0.1, 0.3, 0.7, 0.9]
    predictions = _predictions(
        labels=[0, 0, 1, 1],
        raw=raw,
        calibrated=_calibrate(raw, coefficient=-1.5, intercept=0.2),
    )

    overview, diagnostics = build_auc_audit(predictions)
    fold = diagnostics["folds"][0]

    assert fold["coefficient_sign"] == "negative"
    assert fold["calibrated_auc"] == pytest.approx(1.0 - fold["raw_auc"])
    assert fold["ranking_inversion_count"] == 6
    assert fold["strict_raw_order_pair_count"] == 6
    assert fold["spearman_rank_correlation"] == pytest.approx(-1.0)
    assert overview["invariants"]["negative_coefficient_rank_reversal"]["passed"]
    assert_auc_audit_invariants(overview)


def test_auc_audit_requires_identical_variant_samples() -> None:
    raw = [0.1, 0.3, 0.7, 0.9]
    calibrated = _calibrate(raw, coefficient=2.0, intercept=-1.0)
    calibrated[0] = np.nan
    predictions = _predictions(
        labels=[0, 0, 1, 1],
        raw=raw,
        calibrated=calibrated,
    )

    overview, _ = build_auc_audit(predictions)

    assert not overview["invariants"]["identical_sample_keys"]["passed"]
    with pytest.raises(ValueError, match="identical_sample_keys"):
        assert_auc_audit_invariants(overview)


def test_single_class_fold_marks_both_auc_values_unavailable() -> None:
    raw = [0.1, 0.3, 0.7]
    predictions = _predictions(
        labels=[0, 0, 0],
        raw=raw,
        calibrated=_calibrate(raw, coefficient=2.0, intercept=-1.0),
    )

    overview, diagnostics = build_auc_audit(predictions)
    fold = diagnostics["folds"][0]

    assert fold["raw_single_class"]
    assert fold["calibrated_single_class"]
    assert not fold["raw_valid_auc"]
    assert not fold["calibrated_valid_auc"]
    assert fold["raw_auc"] is None
    assert fold["calibrated_auc"] is None
    assert overview["invariants"]["single_class_auc_consistency"]["passed"]
    assert_auc_audit_invariants(overview)
