"""Logistic regression baseline for stock risk warning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class LogisticRiskModel:
    """Thin wrapper around an sklearn logistic regression pipeline."""

    random_state: int = 42
    max_iter: int = 1000
    class_weight: str | dict[int, float] | None = "balanced"

    def __post_init__(self) -> None:
        self.pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        random_state=self.random_state,
                        max_iter=self.max_iter,
                        class_weight=self.class_weight,
                    ),
                ),
            ]
        )

    def fit(self, features: np.ndarray, labels: np.ndarray) -> "LogisticRiskModel":
        self.pipeline.fit(features, labels)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return self.pipeline.predict_proba(features)[:, 1]

    def predict(self, features: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(features) >= threshold).astype(int)
