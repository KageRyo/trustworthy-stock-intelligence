"""Date-block bootstrap ensembles for epistemic uncertainty."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np


class ProbabilityModel(Protocol):
    def fit(self, features: np.ndarray, labels: np.ndarray) -> object: ...

    def predict_proba(self, features: np.ndarray) -> np.ndarray: ...


class DateBootstrapEnsemble:
    """Refit a model on bootstrap resamples of whole dates.

    Resampling dates instead of rows keeps same-day cross-sectional rows together,
    so member disagreement reflects how sensitive the fit is to which market days
    were observed. The ensemble is only used for uncertainty; serving probabilities
    still come from the single model fitted on all training rows.
    """

    def __init__(
        self,
        model_factory: Callable[[], ProbabilityModel],
        *,
        n_members: int = 10,
        random_state: int = 42,
        max_resample_attempts: int = 20,
    ) -> None:
        if n_members < 2:
            raise ValueError("n_members must be at least two")
        self.model_factory = model_factory
        self.n_members = n_members
        self.random_state = random_state
        self.max_resample_attempts = max_resample_attempts
        self.members_: list[ProbabilityModel] = []

    def fit(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        *,
        groups: np.ndarray,
    ) -> "DateBootstrapEnsemble":
        values = np.asarray(features, dtype=float)
        targets = np.asarray(labels).astype(int)
        group_values = np.asarray(groups)
        if not (len(values) == len(targets) == len(group_values)):
            raise ValueError("features, labels, and groups must have the same length")
        if np.unique(targets).size < 2:
            raise ValueError("bootstrap ensemble training requires both classes")

        unique_groups, inverse = np.unique(group_values, return_inverse=True)
        rows_by_group = [np.flatnonzero(inverse == index) for index in range(unique_groups.size)]
        rng = np.random.default_rng(self.random_state)
        members: list[ProbabilityModel] = []
        for _ in range(self.n_members):
            for _attempt in range(self.max_resample_attempts):
                sampled = rng.integers(0, unique_groups.size, size=unique_groups.size)
                rows = np.concatenate([rows_by_group[index] for index in sampled])
                if np.unique(targets[rows]).size == 2:
                    break
            else:
                raise ValueError("could not draw a bootstrap sample containing both classes")
            model = self.model_factory()
            model.fit(values[rows], targets[rows])
            members.append(model)
        self.members_ = members
        return self

    def predict_member_proba(self, features: np.ndarray) -> np.ndarray:
        """Return member probabilities with shape ``(n_members, n_samples)``."""

        if not self.members_:
            raise ValueError("DateBootstrapEnsemble must be fit before predicting")
        values = np.asarray(features, dtype=float)
        return np.vstack([member.predict_proba(values) for member in self.members_])
