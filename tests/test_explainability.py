from __future__ import annotations

import numpy as np

from tsi.models.logistic import LogisticRiskModel
from tsi.trust.explainability import (
    LOGISTIC_ATTRIBUTION_METHOD,
    build_logistic_feature_attributions,
)


def test_logistic_attributions_are_deterministic_and_directional() -> None:
    features = np.array(
        [
            [-2.0, 0.2, 1.0],
            [-1.0, 0.4, 0.8],
            [1.0, 0.8, -0.5],
            [2.0, 1.0, -0.8],
        ]
    )
    labels = np.array([0, 0, 1, 1])
    model = LogisticRiskModel(class_weight=None).fit(features, labels)

    first = build_logistic_feature_attributions(
        model,
        features[-1:],
        ("return_1d", "return_5d", "volatility_5d"),
        top_k=2,
    )
    second = build_logistic_feature_attributions(
        model,
        features[-1:],
        ("return_1d", "return_5d", "volatility_5d"),
        top_k=2,
    )

    assert first == second
    assert len(first) == 1
    assert len(first[0]) == 2
    assert all(item.method == LOGISTIC_ATTRIBUTION_METHOD for item in first[0])
    assert {item.direction for item in first[0]} <= {"positive", "negative", "neutral"}
    assert all(item.value is not None for item in first[0])


def test_constant_prior_fallback_has_no_false_attribution() -> None:
    features = np.ones((2, 3))

    attributions = build_logistic_feature_attributions(
        object(), features, ("a", "b", "c")
    )

    assert attributions == [[], []]
