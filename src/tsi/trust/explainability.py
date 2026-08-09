"""Deterministic, model-specific explanations for serving predictions."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from tsi.serving.schema import FeatureAttribution


LOGISTIC_ATTRIBUTION_METHOD = "standardized_logit_v1"


def build_logistic_feature_attributions(
    model: object,
    features: np.ndarray,
    feature_names: Sequence[str],
    *,
    top_k: int = 5,
) -> list[list[FeatureAttribution]]:
    """Return deterministic coefficient contributions for a fitted logistic model.

    Contributions are calculated as the fitted positive-class coefficient times
    the feature value after the model's imputer and standardizer. A positive
    contribution raises the model's raw drawdown-risk log-odds; it is not a
    causal explanation. Models without the expected fitted pipeline, such as
    the constant-prior fallback, return an empty attribution list per row.
    """

    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    values = np.asarray(features, dtype=float)
    if values.ndim != 2:
        raise ValueError("features must be a two-dimensional array")
    names = tuple(str(name) for name in feature_names)
    if values.shape[1] != len(names):
        raise ValueError("feature_names must match the number of feature columns")

    pipeline = getattr(model, "pipeline", None)
    if pipeline is None:
        return [[] for _ in range(values.shape[0])]
    try:
        imputer = pipeline.named_steps["imputer"]
        scaler = pipeline.named_steps["scaler"]
        classifier = pipeline.named_steps["classifier"]
        coefficients = np.asarray(classifier.coef_, dtype=float)
    except (AttributeError, KeyError):
        return [[] for _ in range(values.shape[0])]
    if coefficients.ndim != 2 or coefficients.shape[0] != 1:
        return [[] for _ in range(values.shape[0])]
    if coefficients.shape[1] != values.shape[1]:
        raise ValueError("fitted classifier coefficients do not match features")

    standardized = scaler.transform(imputer.transform(values))
    contributions = standardized * coefficients[0]
    attributions: list[list[FeatureAttribution]] = []
    for raw_row, contribution_row in zip(values, contributions, strict=True):
        order = np.argsort(-np.abs(contribution_row), kind="stable")[:top_k]
        row_attributions = []
        for index in order:
            contribution = float(contribution_row[index])
            if contribution > 0.0:
                direction = "positive"
            elif contribution < 0.0:
                direction = "negative"
            else:
                direction = "neutral"
            raw_value = raw_row[index]
            row_attributions.append(
                FeatureAttribution(
                    feature=names[index],
                    value=float(raw_value) if np.isfinite(raw_value) else None,
                    contribution=contribution,
                    direction=direction,
                    method=LOGISTIC_ATTRIBUTION_METHOD,
                )
            )
        attributions.append(row_attributions)
    return attributions
