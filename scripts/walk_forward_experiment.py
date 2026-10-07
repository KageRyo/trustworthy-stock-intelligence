"""Shared CLI and fold plumbing for purged walk-forward experiment scripts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.train import prepare_training_frame
from tsi.data.csv import read_ohlcv_csv
from tsi.data.split import WalkForwardFold, build_walk_forward_splits
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS


def resolve_output_dir(output_dir: Path, *, root: Path) -> Path:
    """Resolve ``output_dir`` against ``root`` and reject paths that escape it."""

    base = root.resolve()
    resolved = (base / output_dir).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"--output-dir must stay inside {base}")
    return resolved


def add_walk_forward_arguments(parser: argparse.ArgumentParser) -> None:
    """Add input/output, label, split, and calibration arguments shared by experiments."""

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


def load_walk_forward_folds(args: argparse.Namespace) -> WalkForwardFolds:
    """Build labeled rows and the purged walk-forward folds usable for fitting."""

    frame = prepare_training_frame(
        read_ohlcv_csv(args.input),
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
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
    return WalkForwardFolds(folds=usable, purge_size=purge_size, skipped=skipped)


def walk_forward_protocol(
    args: argparse.Namespace,
    folds: WalkForwardFolds,
    **extra: object,
) -> dict[str, object]:
    """Protocol fields recorded in every experiment summary; ``extra`` precedes skipped_folds."""

    return {
        "feature_interval": "1d",
        "feature_columns": list(DEFAULT_FEATURE_COLUMNS),
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
