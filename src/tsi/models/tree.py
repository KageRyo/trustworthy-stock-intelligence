"""Tree-based sklearn baselines for stock risk warning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


TreeModelType = Literal["random_forest", "hist_gradient_boosting"]


@dataclass
class TreeRiskModel:
    """Thin wrapper around sklearn tree-based classifiers."""

    model_type: TreeModelType = "random_forest"
    random_state: int = 42
    n_estimators: int = 200
    max_depth: int | None = None
    learning_rate: float = 0.05
    max_iter: int = 200
    class_weight: str | dict[int, float] | None = "balanced"

    def __post_init__(self) -> None:
        self.pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("classifier", self._build_classifier()),
            ]
        )

    @property
    def model_name(self) -> str:
        return self.model_type

    def fit(self, features: np.ndarray, labels: np.ndarray) -> "TreeRiskModel":
        self.pipeline.fit(features, labels)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return self.pipeline.predict_proba(features)[:, 1]

    def predict(self, features: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(features) >= threshold).astype(int)

    def _build_classifier(self) -> RandomForestClassifier | HistGradientBoostingClassifier:
        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                random_state=self.random_state,
                class_weight=self.class_weight,
                n_jobs=-1,
            )
        if self.model_type == "hist_gradient_boosting":
            return HistGradientBoostingClassifier(
                learning_rate=self.learning_rate,
                max_iter=self.max_iter,
                max_depth=self.max_depth,
                random_state=self.random_state,
            )
        raise ValueError(f"Unsupported tree model type: {self.model_type}")
