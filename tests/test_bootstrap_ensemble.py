"""Tests for the date-block bootstrap ensemble."""

from __future__ import annotations

import numpy as np
import pytest

from tsi.models.ensemble import DateBootstrapEnsemble
from tsi.models.logistic import LogisticRiskModel


def _toy_data(rows_per_date: int = 20, dates: int = 60) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(3)
    features = rng.normal(size=(rows_per_date * dates, 2))
    labels = (features[:, 0] + rng.normal(0, 1, len(features)) > 1.0).astype(int)
    groups = np.repeat(np.arange(dates), rows_per_date)
    return features, labels, groups


def test_ensemble_returns_one_probability_row_per_member() -> None:
    features, labels, groups = _toy_data()
    ensemble = DateBootstrapEnsemble(LogisticRiskModel, n_members=5, random_state=0)

    ensemble.fit(features, labels, groups=groups)
    members = ensemble.predict_member_proba(features[:7])

    assert members.shape == (5, 7)
    assert np.all((members >= 0.0) & (members <= 1.0))


def test_ensemble_members_differ_and_are_reproducible() -> None:
    features, labels, groups = _toy_data()

    first = DateBootstrapEnsemble(LogisticRiskModel, n_members=4, random_state=7)
    second = DateBootstrapEnsemble(LogisticRiskModel, n_members=4, random_state=7)
    first_members = first.fit(features, labels, groups=groups).predict_member_proba(features[:5])
    second_members = second.fit(features, labels, groups=groups).predict_member_proba(features[:5])

    np.testing.assert_allclose(first_members, second_members)
    assert first_members.std(axis=0).max() > 0.0


def test_ensemble_disagreement_grows_far_from_training_data() -> None:
    features, labels, groups = _toy_data()
    ensemble = DateBootstrapEnsemble(LogisticRiskModel, n_members=10, random_state=0)
    ensemble.fit(features, labels, groups=groups)

    near = ensemble.predict_member_proba(np.array([[0.0, 0.0]])).std()
    far = ensemble.predict_member_proba(np.array([[0.0, 25.0]])).std()

    assert far > near


def test_ensemble_rejects_single_class_training_data() -> None:
    features, _, groups = _toy_data()

    with pytest.raises(ValueError, match="both classes"):
        DateBootstrapEnsemble(LogisticRiskModel, n_members=2).fit(
            features, np.zeros(len(features), dtype=int), groups=groups
        )


def test_ensemble_requires_at_least_two_members() -> None:
    with pytest.raises(ValueError, match="at least two"):
        DateBootstrapEnsemble(LogisticRiskModel, n_members=1)
