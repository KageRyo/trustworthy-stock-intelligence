"""Evaluate within-market and cross-market transfer under one temporal protocol."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsi.data.csv import read_ohlcv_csv
from tsi.data.split import build_walk_forward_splits
from tsi.evaluation.metrics import classification_metrics
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.labeling.drawdown import add_future_drawdown_label
from tsi.labeling.warning_level import select_alert_threshold
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator
from tsi.trust.decision import compute_watch_threshold


METRIC_NAMES = (
    "auc",
    "pr_auc",
    "brier_score",
    "ece",
    "precision",
    "recall",
    "f1",
    "false_alarm_rate",
    "false_discovery_rate",
    "miss_rate",
    "positive_rate",
    "prediction_rate",
    "support",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the transfer evaluator CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-input", type=Path, required=True)
    parser.add_argument("--target-input", type=Path, required=True)
    parser.add_argument("--source-market", required=True, help="Label for the training market.")
    parser.add_argument("--target-market", required=True, help="Label for the evaluation market.")
    parser.add_argument("--source-name", default="source")
    parser.add_argument("--target-name", default="target")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--step-size", type=int, default=None)
    parser.add_argument("--purge-size", type=int, default=None)
    parser.add_argument(
        "--calibration-method",
        choices=["none", "platt", "isotonic"],
        default="platt",
    )
    parser.add_argument(
        "--threshold-objective",
        choices=["f1", "precision", "recall"],
        default="f1",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--predictions-output", type=Path, default=None)
    return parser.parse_args(argv)


def prepare_transfer_frame(
    path: Path,
    *,
    horizon: int,
    drawdown_threshold: float,
) -> pd.DataFrame:
    """Build the same feature and label frame for either market."""

    featured = build_technical_features(read_ohlcv_csv(path))
    labeled = add_future_drawdown_label(
        featured,
        horizon=horizon,
        threshold=drawdown_threshold,
    )
    frame = labeled[labeled["label_available"]].copy()
    frame = frame.dropna(subset=DEFAULT_FEATURE_COLUMNS)
    frame["risk_label"] = frame["risk_label"].astype(int)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values(["date", "ticker"]).reset_index(drop=True)


def target_rows_for_dates(frame: pd.DataFrame, dates: Sequence[pd.Timestamp]) -> pd.DataFrame:
    """Select target rows by the source fold's test-date boundaries."""

    if len(dates) == 0:
        return frame.iloc[0:0].copy()
    return frame[frame["date"].isin(pd.Index(dates))].copy()


def constant_prior_probabilities(train_labels: np.ndarray, *, output_size: int) -> np.ndarray:
    """Return a training-window event-rate prior for a one-class fold."""

    if len(train_labels) == 0:
        raise ValueError("train_labels must not be empty")
    return np.full(output_size, float(np.asarray(train_labels, dtype=float).mean()))


def run_transfer(args: argparse.Namespace) -> dict[str, object]:
    """Run source-trained evaluation on target test windows."""

    source = prepare_transfer_frame(
        args.source_input,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )
    target = prepare_transfer_frame(
        args.target_input,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )
    purge_size = args.horizon if args.purge_size is None else args.purge_size
    if purge_size < args.horizon:
        raise ValueError("purge_size must be at least horizon to prevent label-window leakage")

    folds = build_walk_forward_splits(
        source,
        train_size=args.train_size,
        calibration_size=args.calibration_size,
        test_size=args.test_size,
        step_size=args.step_size,
        purge_size=purge_size,
        label_end_date_col="label_end_date",
    )
    fold_results: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    skipped_folds: list[dict[str, object]] = []

    calibration_method: CalibrationMethod = args.calibration_method
    for fold in folds:
        train_frame = source.loc[list(fold.train_index)]
        calibration_frame = source.loc[list(fold.calibration_index)]
        target_test = target_rows_for_dates(target, fold.test_dates)
        if target_test.empty:
            skipped_folds.append(
                {
                    "fold_id": fold.fold_id,
                    "test_start": str(fold.test_dates[0].date()),
                    "test_end": str(fold.test_dates[-1].date()),
                    "reason": "target has no labeled rows in source test-date window",
                }
            )
            continue

        train_labels = train_frame["risk_label"].to_numpy()
        calibration_labels = calibration_frame["risk_label"].to_numpy()
        if pd.Series(train_labels).nunique() < 2:
            prior = constant_prior_probabilities(train_labels, output_size=len(calibration_frame))
            target_probabilities = constant_prior_probabilities(
                train_labels,
                output_size=len(target_test),
            )
            model_name = "constant_prior"
        else:
            model = LogisticRiskModel()
            model.fit(train_frame[DEFAULT_FEATURE_COLUMNS].to_numpy(), train_labels)
            prior = np.full(len(calibration_frame), float(train_labels.mean()), dtype=float)
            target_probabilities = model.predict_proba(
                target_test[DEFAULT_FEATURE_COLUMNS].to_numpy()
            )
            calibration_probabilities = model.predict_proba(
                calibration_frame[DEFAULT_FEATURE_COLUMNS].to_numpy()
            )
            model_name = "logistic_regression"

        if pd.Series(train_labels).nunique() < 2:
            calibration_probabilities = prior
        calibrator = fit_probability_calibrator(
            calibration_probabilities,
            calibration_labels,
            method=calibration_method,
        )
        calibrated_calibration = calibrator.predict(calibration_probabilities)
        calibrated_target = calibrator.predict(target_probabilities)
        threshold_selection = select_alert_threshold(
            calibration_labels,
            calibrated_calibration,
            objective=args.threshold_objective,
        )
        tuned_threshold = threshold_selection.threshold
        target_labels = target_test["risk_label"].to_numpy()
        source_metrics = {
            "raw": classification_metrics(calibration_labels, calibration_probabilities),
            "calibrated": classification_metrics(calibration_labels, calibrated_calibration),
            "tuned": classification_metrics(
                calibration_labels,
                calibrated_calibration,
                threshold=tuned_threshold,
            ),
        }
        target_metrics = {
            "raw": classification_metrics(target_labels, target_probabilities),
            "calibrated": classification_metrics(target_labels, calibrated_target),
            "tuned": classification_metrics(
                target_labels,
                calibrated_target,
                threshold=tuned_threshold,
            ),
        }
        source_calibrated = source_metrics["calibrated"]
        target_calibrated = target_metrics["calibrated"]
        degradation = {
            "event_rate_delta": target_calibrated["positive_rate"]
            - source_calibrated["positive_rate"],
            "brier_delta": target_calibrated["brier_score"] - source_calibrated["brier_score"],
            "ece_delta": target_calibrated["ece"] - source_calibrated["ece"],
        }
        fold_results.append(
            {
                "fold_id": fold.fold_id,
                "model": model_name,
                "source_train_start": str(fold.train_dates[0].date()),
                "source_train_end": str(fold.train_dates[-1].date()),
                "source_calibration_start": str(fold.calibration_dates[0].date()),
                "source_calibration_end": str(fold.calibration_dates[-1].date()),
                "target_test_start": str(fold.test_dates[0].date()),
                "target_test_end": str(fold.test_dates[-1].date()),
                "source_train_rows": len(train_frame),
                "source_calibration_rows": len(calibration_frame),
                "target_test_rows": len(target_test),
                "purge_size": purge_size,
                "alert_threshold": tuned_threshold,
                "watch_threshold": compute_watch_threshold(
                    tuned_threshold,
                    watch_threshold_ratio=0.5,
                    min_watch_threshold=0.01,
                ),
                "source_calibration_metrics": source_metrics,
                "target_test_metrics": target_metrics,
                "calibration_degradation": degradation,
            }
        )
        prediction_frames.append(
            target_test.loc[:, ["date", "ticker", "risk_label"]]
            .assign(
                fold_id=fold.fold_id,
                source_market=args.source_market,
                target_market=args.target_market,
                raw_risk_probability=target_probabilities,
                calibrated_risk_probability=calibrated_target,
                alert_threshold=tuned_threshold,
            )
        )

    if not fold_results:
        raise ValueError("no target test windows were available for evaluation")

    report = {
        "experiment_id": "cross_market_transfer",
        "evaluation": "within_market" if args.source_market == args.target_market else "cross_market",
        "source": {
            "name": args.source_name,
            "market": args.source_market,
            "input": str(args.source_input),
            "date_start": str(source["date"].min().date()),
            "date_end": str(source["date"].max().date()),
            "ticker_count": int(source["ticker"].nunique()),
            "rows_after_filtering": len(source),
        },
        "target": {
            "name": args.target_name,
            "market": args.target_market,
            "input": str(args.target_input),
            "date_start": str(target["date"].min().date()),
            "date_end": str(target["date"].max().date()),
            "ticker_count": int(target["ticker"].nunique()),
            "rows_after_filtering": len(target),
        },
        "protocol": {
            "feature_columns": list(DEFAULT_FEATURE_COLUMNS),
            "horizon": args.horizon,
            "purge_size": purge_size,
            "train_size": args.train_size,
            "calibration_size": args.calibration_size,
            "test_size": args.test_size,
            "step_size": args.step_size if args.step_size is not None else args.test_size,
            "drawdown_threshold": args.drawdown_threshold,
            "calibration_method": calibration_method,
            "threshold_objective": args.threshold_objective,
            "scheduled_fold_count": len(folds),
            "evaluated_fold_count": len(fold_results),
        },
        "aggregate": {
            "source_calibration_metrics": _aggregate_metric_sections(
                [fold["source_calibration_metrics"] for fold in fold_results]
            ),
            "target_test_metrics": _aggregate_metric_sections(
                [fold["target_test_metrics"] for fold in fold_results]
            ),
            "calibration_degradation": _mean_metric_dict(
                [fold["calibration_degradation"] for fold in fold_results],
                metric_names=("event_rate_delta", "brier_delta", "ece_delta"),
            ),
        },
        "folds": fold_results,
        "skipped_folds": skipped_folds,
        "limitations": [
            "Market definitions and feature columns are harmonized, but the source and target data have different calendars and coverage.",
            "This evaluator measures probability transfer, not economic or trading performance.",
            "A vendor-adjusted current-universe snapshot does not remove survivorship or provider-rights limitations.",
            "Deep-model transfer is not included because sequence row-key alignment remains a separate task.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(report), indent=2) + "\n", encoding="utf-8")
    if args.predictions_output is not None:
        predictions = pd.concat(prediction_frames, ignore_index=True)
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(args.predictions_output, index=False)
    return report


def _aggregate_metric_sections(sections: Sequence[dict[str, dict[str, float]]]) -> dict[str, object]:
    return {section: _mean_metric_dict([row[section] for row in sections]) for section in sections[0]}


def _mean_metric_dict(
    rows: Sequence[dict[str, float]],
    *,
    metric_names: Sequence[str] = METRIC_NAMES,
) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for metric in metric_names:
        values = [float(row[metric]) for row in rows if _is_finite(row.get(metric))]
        result[metric] = float(np.mean(values)) if values else None
    return result


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float, np.number)) and math.isfinite(float(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def main() -> None:
    """Run the transfer evaluator and print its JSON report."""

    report = run_transfer(parse_args())
    print(json.dumps(_json_safe(report), indent=2))


if __name__ == "__main__":
    main()
