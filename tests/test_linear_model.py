"""Tests for parameter-only logistic scoring."""

from __future__ import annotations

import numpy as np
import pytest

from tsi.models.linear import LinearLogitModel, LinearLogitParams, linear_logit_params
from tsi.models.logistic import LogisticRiskModel


def _fitted_logistic() -> tuple[LogisticRiskModel, np.ndarray]:
    rng = np.random.default_rng(11)
    features = rng.normal(size=(500, 4)) * np.array([1.0, 3.0, 0.2, 10.0]) + 5.0
    features[::17, 2] = np.nan
    labels = (features[:, 0] + rng.normal(scale=1.0, size=500) > 5.3).astype(int)
    return LogisticRiskModel().fit(features, labels), features


def test_linear_logit_model_reproduces_the_fitted_logistic_model() -> None:
    model, features = _fitted_logistic()
    loaded = LinearLogitModel(linear_logit_params(model))

    np.testing.assert_allclose(
        loaded.predict_proba(features), model.predict_proba(features), rtol=0, atol=1e-12
    )


def test_linear_logit_standardization_matches_the_pipeline() -> None:
    model, features = _fitted_logistic()
    loaded = LinearLogitModel(linear_logit_params(model))
    pipeline = model.pipeline

    expected = pipeline.named_steps["scaler"].transform(
        pipeline.named_steps["imputer"].transform(features)
    )

    np.testing.assert_allclose(loaded.standardize(features), expected, rtol=0, atol=1e-12)


def test_linear_logit_params_round_trip_through_json() -> None:
    model, features = _fitted_logistic()
    params = linear_logit_params(model)

    restored = LinearLogitParams.model_validate_json(params.model_dump_json())

    assert restored == params
    np.testing.assert_array_equal(
        LinearLogitModel(restored).predict_proba(features),
        LinearLogitModel(params).predict_proba(features),
    )


def test_linear_logit_params_reject_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        LinearLogitParams(
            medians=[0.0, 0.0],
            means=[0.0],
            scales=[1.0, 1.0],
            coefficients=[1.0, 1.0],
            intercept=0.0,
        )


def test_linear_logit_model_rejects_the_wrong_feature_count() -> None:
    model, features = _fitted_logistic()
    loaded = LinearLogitModel(linear_logit_params(model))

    with pytest.raises(ValueError, match="4 feature columns"):
        loaded.predict_proba(features[:, :3])
