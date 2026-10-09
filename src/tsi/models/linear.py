"""Parameter-only logistic scoring for stored serving models.

A fitted ``LogisticRiskModel`` is a median imputer, a standardizer, and a logistic regression.
``LinearLogitParams`` stores those fitted values as plain numbers so a serving model can be saved as
schema-validated JSON and scored later without pickling scikit-learn objects.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from tsi.models.logistic import LogisticRiskModel


class LinearLogitParams(BaseModel):
    """Fitted imputer medians, standardizer moments, and logistic coefficients."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    medians: list[float]
    means: list[float]
    scales: list[float]
    coefficients: list[float]
    intercept: float

    @model_validator(mode="after")
    def _same_length(self) -> LinearLogitParams:
        lengths = {len(self.medians), len(self.means), len(self.scales), len(self.coefficients)}
        if len(lengths) != 1 or 0 in lengths:
            raise ValueError("medians, means, scales, and coefficients must have the same length")
        return self


@dataclass(frozen=True)
class LinearLogitModel:
    """Score rows from ``LinearLogitParams`` exactly as the fitted pipeline does."""

    params: LinearLogitParams

    @property
    def coefficients(self) -> np.ndarray:
        return np.asarray(self.params.coefficients, dtype=float)

    def standardize(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=float)
        width = len(self.params.coefficients)
        if values.ndim != 2 or values.shape[1] != width:
            raise ValueError(f"features must be a 2D array with {width} feature columns")
        medians = np.asarray(self.params.medians, dtype=float)
        imputed = np.where(np.isnan(values), medians, values)
        return (imputed - np.asarray(self.params.means)) / np.asarray(self.params.scales)

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        log_odds = self.standardize(features) @ self.coefficients + self.params.intercept
        return 1.0 / (1.0 + np.exp(-log_odds))


def linear_logit_params(model: LogisticRiskModel) -> LinearLogitParams:
    """Export the fitted values of a ``LogisticRiskModel``."""

    imputer = model.pipeline.named_steps["imputer"]
    scaler = model.pipeline.named_steps["scaler"]
    classifier = model.pipeline.named_steps["classifier"]
    return LinearLogitParams(
        medians=[float(value) for value in imputer.statistics_],
        means=[float(value) for value in scaler.mean_],
        scales=[float(value) for value in scaler.scale_],
        coefficients=[float(value) for value in classifier.coef_[0]],
        intercept=float(classifier.intercept_[0]),
    )
