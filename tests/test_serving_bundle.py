"""Tests for storing a fitted serving model and scoring new tickers with it."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.predict_latest_baseline import parse_args, run_prediction
from tests.test_evaluate_selective_trust import _write_ohlcv
from tsi.serving.bundle import SERVING_BUNDLE_SCHEMA_VERSION, load_serving_bundle

COMPARED = [
    "date",
    "ticker",
    "risk_probability",
    "calibrated_risk_probability",
    "calibration_method",
    "uncertainty_score",
    "trust_score",
    "alert_threshold",
    "watch_threshold",
    "warning_level",
]


def _args(tmp_path: Path, input_path: Path, name: str, *extra: str):
    return parse_args(
        [
            "--model-bundle-root",
            str(tmp_path / "bundles"),
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / f"{name}.csv"),
            "--json-output",
            str(tmp_path / f"{name}.json"),
            "--calibration-size",
            "30",
            "--drift-size",
            "10",
            "--reliability-members",
            "4",
            "--required-history-rows",
            "60",
            "--run-id",
            name,
            *extra,
        ]
    )


def _batch_with_bundle(tmp_path: Path) -> tuple[pd.DataFrame, Path]:
    universe = tmp_path / "universe.csv"
    _write_ohlcv(universe)
    bundle_path = tmp_path / "bundles" / "us.json"
    batch = run_prediction(_args(tmp_path, universe, "batch", "--model-bundle-output", "us.json"))
    return batch, bundle_path


def _records(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(record["ticker"]): record for record in payload["records"]}


def _assert_same_scores(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    actual = actual.sort_values("ticker").reset_index(drop=True)[COMPARED]
    expected = expected.sort_values("ticker").reset_index(drop=True)[COMPARED]
    for column in COMPARED:
        if actual[column].dtype.kind == "f":
            np.testing.assert_allclose(actual[column], expected[column], rtol=0, atol=1e-12)
        else:
            assert actual[column].tolist() == expected[column].tolist(), column


def test_batch_writes_a_schema_validated_bundle(tmp_path: Path) -> None:
    _, bundle_path = _batch_with_bundle(tmp_path)

    bundle = load_serving_bundle(bundle_path, root=bundle_path.parent)

    assert bundle.schema_version == SERVING_BUNDLE_SCHEMA_VERSION
    assert bundle.run_id == "batch"
    assert bundle.feature_set == "technical_range"
    assert bundle.tickers == 4
    assert len(bundle.model.coefficients) == len(bundle.feature_columns)
    assert len(bundle.reliability.members) == 4


def test_bundle_scores_the_universe_like_the_batch(tmp_path: Path) -> None:
    batch, bundle_path = _batch_with_bundle(tmp_path)

    scored = run_prediction(
        _args(tmp_path, tmp_path / "universe.csv", "scored", "--model-bundle", str(bundle_path))
    )

    _assert_same_scores(scored, batch)
    batch_records = _records(tmp_path / "batch.json")
    for ticker, record in _records(tmp_path / "scored.json").items():
        assert record["reason_codes"] == batch_records[ticker]["reason_codes"]
    assert (scored["model"] == "logistic_regression_pooled").all()
    assert scored["model_bundle"].str.startswith("pooled:technical_range:").all()


def test_bundle_scores_a_single_ticker_like_its_batch_row(tmp_path: Path) -> None:
    batch, bundle_path = _batch_with_bundle(tmp_path)
    universe = pd.read_csv(tmp_path / "universe.csv", dtype={"ticker": str})
    single = tmp_path / "single.csv"
    universe[universe["ticker"] == "00981A"].to_csv(single, index=False)

    scored = run_prediction(_args(tmp_path, single, "single", "--model-bundle", str(bundle_path)))

    _assert_same_scores(scored, batch[batch["ticker"] == "00981A"])
    assert _records(tmp_path / "single.json")["00981A"]["reason_codes"] == (
        _records(tmp_path / "batch.json")["00981A"]["reason_codes"]
    )


def test_bundle_options_are_mutually_exclusive(tmp_path: Path) -> None:
    _, bundle_path = _batch_with_bundle(tmp_path)
    args = _args(
        tmp_path,
        tmp_path / "universe.csv",
        "both",
        "--model-bundle",
        str(bundle_path),
        "--model-bundle-output",
        "other.json",
    )

    with pytest.raises(ValueError, match="either"):
        run_prediction(args)


def test_legacy_trust_cannot_be_stored(tmp_path: Path) -> None:
    universe = tmp_path / "universe.csv"
    _write_ohlcv(universe)
    args = _args(
        tmp_path, universe, "legacy", "--trust-method", "legacy", "--model-bundle-output", "x.json"
    )

    with pytest.raises(ValueError, match="reliability"):
        run_prediction(args)


def test_single_ticker_fits_are_flagged(tmp_path: Path) -> None:
    universe = tmp_path / "universe.csv"
    _write_ohlcv(universe)
    frame = pd.read_csv(universe, dtype={"ticker": str})
    single = tmp_path / "single.csv"
    frame[frame["ticker"] == "AAA"].to_csv(single, index=False)

    run_prediction(_args(tmp_path, single, "alone"))
    run_prediction(_args(tmp_path, universe, "pooled"))

    assert "single_ticker_model" in _records(tmp_path / "alone.json")["AAA"]["reason_codes"]
    for record in _records(tmp_path / "pooled.json").values():
        assert "single_ticker_model" not in record["reason_codes"]


def test_single_ticker_fits_cannot_be_stored(tmp_path: Path) -> None:
    universe = tmp_path / "universe.csv"
    _write_ohlcv(universe)
    frame = pd.read_csv(universe, dtype={"ticker": str})
    single = tmp_path / "single.csv"
    frame[frame["ticker"] == "AAA"].to_csv(single, index=False)

    args = _args(tmp_path, single, "alone", "--model-bundle-output", "x.json")

    with pytest.raises(ValueError, match="more than one ticker"):
        run_prediction(args)


def test_an_old_bundle_is_flagged_as_stale(tmp_path: Path) -> None:
    _, bundle_path = _batch_with_bundle(tmp_path)
    universe = pd.read_csv(tmp_path / "universe.csv", dtype={"ticker": str})
    later = universe.copy()
    later["date"] = (pd.to_datetime(later["date"]) + pd.Timedelta(days=45)).dt.strftime("%Y-%m-%d")
    later_path = tmp_path / "later.csv"
    later[later["ticker"] == "BBB"].to_csv(later_path, index=False)

    run_prediction(_args(tmp_path, later_path, "later", "--model-bundle", str(bundle_path)))
    run_prediction(
        _args(tmp_path, tmp_path / "universe.csv", "same", "--model-bundle", str(bundle_path))
    )

    assert "model_bundle_stale" in _records(tmp_path / "later.json")["BBB"]["reason_codes"]
    for record in _records(tmp_path / "same.json").values():
        assert "model_bundle_stale" not in record["reason_codes"]


@pytest.mark.parametrize("option", ["--model-bundle", "--model-bundle-output"])
def test_bundle_paths_must_stay_inside_the_bundle_root(tmp_path: Path, option: str) -> None:
    universe = tmp_path / "universe.csv"
    _write_ohlcv(universe)
    args = _args(tmp_path, universe, "escape", option, "../outside.json")

    with pytest.raises(ValueError, match="must stay inside"):
        run_prediction(args)
