"""Tests for shared walk-forward experiment plumbing with feature sets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.walk_forward_experiment import (
    add_walk_forward_arguments,
    load_walk_forward_folds,
    walk_forward_protocol,
)
from tests.test_evaluate_selective_trust import _write_ohlcv
from tsi.features.sets import resolve_feature_set


def _write_reference(directory: Path) -> None:
    directory.mkdir()
    dates = pd.bdate_range("2019-12-01", periods=300)
    rng = np.random.default_rng(8)
    pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates.strftime("%Y-%m-%d"),
                    "ticker": symbol,
                    "close": level,
                    "adj_close": level,
                }
            )
            for symbol, level in (
                ("SPY", 300.0 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))),
                ("^VIX", 15.0 + rng.uniform(0, 5, len(dates))),
            )
        ],
        ignore_index=True,
    ).to_csv(directory / "ohlcv.csv", index=False)
    pd.DataFrame(
        {"ticker": ["AAA"], "sector": [""], "sector_key": [""], "sector_etf": [""]}
    ).to_csv(directory / "sector_map.csv", index=False)
    (directory / "metadata.json").write_text(
        json.dumps({"market_symbol": "SPY", "volatility_symbol": "^VIX"})
    )


def _args(tmp_path: Path, *extra: str, feature_set_argument: bool = True) -> argparse.Namespace:
    _write_ohlcv(tmp_path / "ohlcv.csv")
    parser = argparse.ArgumentParser()
    add_walk_forward_arguments(parser, feature_set_argument=feature_set_argument)
    return parser.parse_args(
        [
            "--input",
            str(tmp_path / "ohlcv.csv"),
            "--output-dir",
            "run",
            "--train-size",
            "80",
            "--calibration-size",
            "30",
            "--test-size",
            "30",
            *extra,
        ]
    )


def test_market_feature_set_requires_reference(tmp_path: Path) -> None:
    args = _args(tmp_path, "--feature-set", "technical_market")

    with pytest.raises(ValueError, match="--market-reference"):
        load_walk_forward_folds(args)


def test_market_feature_set_records_reference_fingerprints(tmp_path: Path) -> None:
    _write_reference(tmp_path / "market")
    args = _args(
        tmp_path,
        "--feature-set",
        "technical_market",
        "--market-reference",
        str(tmp_path / "market"),
    )

    folds = load_walk_forward_folds(args)
    protocol = walk_forward_protocol(args, folds)

    assert folds.feature_columns == resolve_feature_set("technical_market")
    assert protocol["feature_columns"] == folds.feature_columns
    reference = protocol["market_reference"]
    assert isinstance(reference, dict)
    assert len(reference["ohlcv_sha256"]) == 64
    first = folds.folds[0]
    assert first.train[folds.feature_columns].notna().all().all()
    assert {"2330", "00981A"} <= set(first.train["ticker"])


def test_explicit_columns_override_feature_set_and_skip_unused_reference(tmp_path: Path) -> None:
    columns = resolve_feature_set("technical_range")
    args = _args(tmp_path, feature_set_argument=False)

    folds = load_walk_forward_folds(args, feature_columns=columns)
    protocol = walk_forward_protocol(args, folds)

    assert folds.feature_columns == columns
    assert "market_reference" not in protocol
