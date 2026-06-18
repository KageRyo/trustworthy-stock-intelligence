"""Tests for tree-based baseline models."""

from __future__ import annotations

import numpy as np

from tsi.models.tree import TreeRiskModel


def test_random_forest_risk_model_predicts_probabilities() -> None:
    features = np.array(
        [
            [0.0, 0.0],
            [0.1, 0.2],
            [1.0, 1.0],
            [1.2, 0.9],
        ]
    )
    labels = np.array([0, 0, 1, 1])
    model = TreeRiskModel(model_type="random_forest", n_estimators=20, random_state=7)

    model.fit(features, labels)
    probabilities = model.predict_proba(features)

    assert probabilities.shape == (4,)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))
    assert model.predict(features).shape == (4,)


def test_hist_gradient_boosting_risk_model_predicts_probabilities() -> None:
    features = np.array(
        [
            [0.0, 0.0],
            [0.1, 0.2],
            [1.0, 1.0],
            [1.2, 0.9],
            [1.3, 1.1],
            [0.2, 0.1],
        ]
    )
    labels = np.array([0, 0, 1, 1, 1, 0])
    model = TreeRiskModel(model_type="hist_gradient_boosting", max_iter=5, random_state=7)

    model.fit(features, labels)
    probabilities = model.predict_proba(features)

    assert probabilities.shape == (6,)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))
