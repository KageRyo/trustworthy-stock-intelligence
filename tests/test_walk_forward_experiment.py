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


def _write_chip_archive(directory: Path, tickers: tuple[str, ...]) -> None:
    directory.mkdir()
    dates = pd.bdate_range("2020-01-01", periods=260).strftime("%Y-%m-%d")
    rng = np.random.default_rng(9)
    institutional = pd.DataFrame(
        [
            {
                "date": date,
                "ticker": ticker,
                "foreign_net": rng.normal(0, 500),
                "investment_trust_net": rng.normal(0, 100),
                "dealer_net": rng.normal(0, 50),
                "total_net": 0.0,
            }
            for date in dates
            for ticker in tickers
        ]
    )
    margin = pd.DataFrame(
        [
            {
                "date": date,
                "ticker": ticker,
                "margin_balance": 100.0 + rng.normal(0, 5),
                "short_balance": 10.0,
                "margin_short_offset": 0.0,
            }
            for date in dates
            for ticker in tickers
        ]
    )
    institutional.to_csv(directory / "institutional.csv", index=False)
    margin.to_csv(directory / "margin.csv", index=False)


def test_chip_feature_set_requires_and_records_chip_archive(tmp_path: Path) -> None:
    _write_chip_archive(tmp_path / "chips", ("AAA", "BBB", "2330", "00981A"))
    missing = _args(tmp_path, "--feature-set", "technical_range_chips")
    with pytest.raises(ValueError, match="--chip-archive"):
        load_walk_forward_folds(missing)

    args = _args(
        tmp_path,
        "--feature-set",
        "technical_range_chips",
        "--chip-archive",
        str(tmp_path / "chips"),
        "--chip-lag",
        "2",
    )
    folds = load_walk_forward_folds(args)
    protocol = walk_forward_protocol(args, folds)

    chip_archive = protocol["chip_archive"]
    assert isinstance(chip_archive, dict)
    assert chip_archive["publication_lag"] == 2
    assert len(chip_archive["margin_sha256"]) == 64
    assert {"2330", "00981A"} <= set(folds.folds[0].train["ticker"])
