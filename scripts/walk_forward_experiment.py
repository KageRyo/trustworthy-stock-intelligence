"""Shared CLI and fold plumbing for purged walk-forward experiment scripts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.train import prepare_training_frame
from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.data.market_reference import MarketReference, load_market_reference
from tsi.data.split import WalkForwardFold, build_walk_forward_splits
from tsi.features.sets import (
    DEFAULT_FEATURE_SET,
    FEATURE_SETS,
    feature_set_requires_market_reference,
    resolve_feature_set,
)
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import (
    CalibrationMethod,
    ProbabilityCalibrator,
    fit_probability_calibrator,
)


def resolve_output_dir(output_dir: Path, *, root: Path) -> Path:
    """Resolve ``output_dir`` against ``root`` and reject paths that escape it."""

    base = root.resolve()
    resolved = (base / output_dir).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"--output-dir must stay inside {base}")
    return resolved


def add_walk_forward_arguments(
    parser: argparse.ArgumentParser,
    *,
    feature_set_argument: bool = True,
) -> None:
    """Add input/output, label, split, calibration, and feature-set arguments."""

    parser.add_argument("--input", type=Path, required=True, help="OHLCV CSV input.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory; must resolve inside --output-root.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.cwd(),
        help="Directory that --output-dir must stay inside. Defaults to the working directory.",
    )
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--purge-size", type=int, default=None)
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument(
        "--calibration-method",
        choices=["none", "platt", "isotonic"],
        default="platt",
    )
    parser.add_argument(
        "--market-reference",
        type=Path,
        default=None,
        help="Directory from scripts.download_market_reference; needed for market features.",
    )
    if feature_set_argument:
        parser.add_argument(
            "--feature-set",
            choices=list(FEATURE_SETS),
            default=DEFAULT_FEATURE_SET,
            help="Named feature set used to fit the baseline.",
        )


@dataclass(frozen=True)
class FoldFrames:
    """One walk-forward fold whose train and calibration windows contain both classes."""

    fold: WalkForwardFold
    train: pd.DataFrame
    calibration: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class WalkForwardFolds:
    folds: list[FoldFrames]
    purge_size: int
    skipped: int
    feature_columns: list[str]
    market_reference_dir: Path | None = None


def load_args_market_reference(
    args: argparse.Namespace, feature_columns: Sequence[str]
) -> MarketReference | None:
    """Load ``--market-reference`` when the feature columns need it."""

    if not feature_set_requires_market_reference(feature_columns):
        return None
    if args.market_reference is None:
        raise ValueError("--market-reference is required for market-relative feature sets")
    return load_market_reference(args.market_reference)


def load_walk_forward_folds(
    args: argparse.Namespace,
    *,
    feature_columns: Sequence[str] | None = None,
) -> WalkForwardFolds:
    """Build labeled rows and the purged walk-forward folds usable for fitting.

    Rows with any missing value in ``feature_columns`` (default: ``--feature-set``)
    are dropped before splitting, so callers comparing feature sets should pass
    the union of their columns to keep folds identical.
    """

    columns = list(feature_columns or resolve_feature_set(args.feature_set))
    market_reference = load_args_market_reference(args, columns)
    frame = prepare_training_frame(
        read_ohlcv_csv(args.input),
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
        feature_columns=columns,
        market_reference=market_reference,
    )
    purge_size = args.horizon if args.purge_size is None else args.purge_size
    if purge_size < args.horizon:
        raise ValueError("purge_size must be at least horizon to prevent label-window leakage")
    splits = build_walk_forward_splits(
        frame,
        train_size=args.train_size,
        calibration_size=args.calibration_size,
        test_size=args.test_size,
        purge_size=purge_size,
        label_end_date_col="label_end_date",
    )
    if args.max_folds is not None:
        splits = splits[: args.max_folds]

    usable: list[FoldFrames] = []
    skipped = 0
    for fold in splits:
        train = frame.loc[list(fold.train_index)]
        calibration = frame.loc[list(fold.calibration_index)]
        test = frame.loc[list(fold.test_index)]
        if train["risk_label"].nunique() < 2 or calibration["risk_label"].nunique() < 2 or test.empty:
            skipped += 1
            continue
        usable.append(FoldFrames(fold=fold, train=train, calibration=calibration, test=test))
    if not usable:
        raise ValueError("No walk-forward fold had both classes in train and calibration windows")
    return WalkForwardFolds(
        folds=usable,
        purge_size=purge_size,
        skipped=skipped,
        feature_columns=columns,
        market_reference_dir=args.market_reference if market_reference is not None else None,
    )


@dataclass(frozen=True)
class CalibratedLogisticFit:
    """Logistic baseline fit on train rows and calibrated on calibration rows."""

    model: LogisticRiskModel
    calibrator: ProbabilityCalibrator
    calibration_probabilities: np.ndarray
    test_probabilities: np.ndarray


def fit_calibrated_logistic(
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    test: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    calibration_method: CalibrationMethod,
) -> CalibratedLogisticFit:
    """Fit the baseline and calibrator; probabilities are calibrated for both windows."""

    columns = list(feature_columns)
    model = LogisticRiskModel().fit(train[columns].to_numpy(), train["risk_label"].to_numpy())
    raw_calibration = model.predict_proba(calibration[columns].to_numpy())
    calibrator = fit_probability_calibrator(
        raw_calibration, calibration["risk_label"].to_numpy(), method=calibration_method
    )
    return CalibratedLogisticFit(
        model=model,
        calibrator=calibrator,
        calibration_probabilities=calibrator.predict(raw_calibration),
        test_probabilities=calibrator.predict(model.predict_proba(test[columns].to_numpy())),
    )


def walk_forward_protocol(
    args: argparse.Namespace,
    folds: WalkForwardFolds,
    **extra: object,
) -> dict[str, object]:
    """Protocol fields recorded in every experiment summary; ``extra`` precedes skipped_folds."""

    reference: dict[str, object] = {}
    if folds.market_reference_dir is not None:
        reference["market_reference"] = {
            "path": str(folds.market_reference_dir),
            "ohlcv_sha256": file_sha256(folds.market_reference_dir / "ohlcv.csv"),
            "sector_map_sha256": file_sha256(folds.market_reference_dir / "sector_map.csv"),
        }
    return {
        "feature_interval": "1d",
        "feature_columns": list(folds.feature_columns),
        **reference,
        "horizon": args.horizon,
        "drawdown_threshold": args.drawdown_threshold,
        "train_size": args.train_size,
        "calibration_size": args.calibration_size,
        "test_size": args.test_size,
        "purge_size": folds.purge_size,
        "calibration_method": args.calibration_method,
        **extra,
        "skipped_folds": folds.skipped,
    }
