"""Tests for baseline training CLI helpers."""

from __future__ import annotations

from scripts.train import build_baseline_model, parse_args
from tsi.models.logistic import LogisticRiskModel
from tsi.models.tree import TreeRiskModel


def test_parse_args_defaults_to_logistic_model() -> None:
    args = parse_args(["--input", "data.csv"])

    assert args.model_type == "logistic"


def test_build_baseline_model_supports_tree_models() -> None:
    args = parse_args(
        [
            "--input",
            "data.csv",
            "--model-type",
            "random_forest",
            "--tree-n-estimators",
            "10",
        ]
    )

    model, model_name = build_baseline_model(args)

    assert isinstance(model, TreeRiskModel)
    assert model_name == "random_forest"
    assert model.n_estimators == 10


def test_build_baseline_model_keeps_logistic_name() -> None:
    args = parse_args(["--input", "data.csv"])

    model, model_name = build_baseline_model(args)

    assert isinstance(model, LogisticRiskModel)
    assert model_name == "logistic_regression"
