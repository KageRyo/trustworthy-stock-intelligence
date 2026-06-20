"""Train a leakage-aware logistic baseline for stock risk warning."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

import pandas as pd

from tsi.data.csv import read_ohlcv_csv
from tsi.data.split import build_walk_forward_splits
from tsi.evaluation.metrics import classification_metrics
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.labeling.drawdown import add_future_drawdown_label
from tsi.labeling.warning_level import assign_warning_levels, select_alert_threshold
from tsi.models.logistic import LogisticRiskModel
from tsi.models.tree import TreeRiskModel
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to OHLCV CSV input.")
    parser.add_argument(
        "--horizon",
        type=int,
        default=5,
        help="Number of future trading days used for drawdown labeling.",
    )
    parser.add_argument(
        "--drawdown-threshold",
        type=float,
        default=-0.05,
        help="Risk threshold for future max drawdown labeling.",
    )
    parser.add_argument("--train-size", type=int, default=252, help="Train window in dates.")
    parser.add_argument(
        "--calibration-size",
        type=int,
        default=63,
        help="Calibration window in dates.",
    )
    parser.add_argument("--test-size", type=int, default=63, help="Test window in dates.")
    parser.add_argument(
        "--step-size",
        type=int,
        default=None,
        help="Date step between folds. Defaults to test-size.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path for fold metrics and summary.",
    )
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=None,
        help="Optional CSV output path for test-fold prediction rows.",
    )
    parser.add_argument(
        "--model-type",
        choices=["logistic", "random_forest", "hist_gradient_boosting"],
        default="logistic",
        help="Baseline model family.",
    )
    parser.add_argument("--tree-n-estimators", type=int, default=200)
    parser.add_argument("--tree-max-depth", type=int, default=None)
    parser.add_argument("--tree-learning-rate", type=float, default=0.05)
    parser.add_argument("--tree-max-iter", type=int, default=200)
    parser.add_argument(
        "--calibration-method",
        choices=["none", "platt", "isotonic"],
        default="platt",
        help="Probability calibration method fit on the calibration window.",
    )
    parser.add_argument(
        "--threshold-objective",
        choices=["f1", "precision", "recall"],
        default="f1",
        help="Metric optimized on the calibration window when selecting alert thresholds.",
    )
    return parser.parse_args(argv)


def prepare_training_frame(
    ohlcv: pd.DataFrame,
    *,
    horizon: int,
    drawdown_threshold: float,
) -> pd.DataFrame:
    """Build features and labels, then drop rows that cannot be trained or evaluated."""

    featured = build_technical_features(ohlcv)
    labeled = add_future_drawdown_label(
        featured,
        horizon=horizon,
        threshold=drawdown_threshold,
    )
    training_frame = labeled[labeled["label_available"]].copy()
    training_frame = training_frame.dropna(subset=DEFAULT_FEATURE_COLUMNS)
    training_frame["risk_label"] = training_frame["risk_label"].astype(int)
    training_frame = training_frame.sort_values(["date", "ticker"]).reset_index(drop=True)
    return training_frame


def run_training(args: argparse.Namespace) -> dict[str, object]:
    """Train one logistic model per walk-forward fold and return metrics."""

    ohlcv = read_ohlcv_csv(args.input)
    training_frame = prepare_training_frame(
        ohlcv,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )

    folds = build_walk_forward_splits(
        training_frame,
        train_size=args.train_size,
        calibration_size=args.calibration_size,
        test_size=args.test_size,
        step_size=args.step_size,
    )

    calibration_method: CalibrationMethod = args.calibration_method
    fold_results: list[dict[str, object]] = []
    prediction_rows: list[pd.DataFrame] = []
    for fold in folds:
        train_frame = training_frame.loc[list(fold.train_index)]
        calibration_frame = training_frame.loc[list(fold.calibration_index)]
        test_frame = training_frame.loc[list(fold.test_index)]
        train_labels = train_frame["risk_label"].to_numpy()
        calibration_labels = calibration_frame["risk_label"].to_numpy()
        test_labels = test_frame["risk_label"].to_numpy()

        unique_train_classes = pd.Series(train_labels).nunique()
        if unique_train_classes < 2:
            positive_rate = float(train_labels.mean())
            calibration_probabilities = pd.Series(
                positive_rate, index=calibration_frame.index, dtype=float
            ).to_numpy()
            probabilities = pd.Series(positive_rate, index=test_frame.index, dtype=float).to_numpy()
            model_name = "constant_prior"
        else:
            model, model_name = build_baseline_model(args)
            model.fit(train_frame[DEFAULT_FEATURE_COLUMNS].to_numpy(), train_labels)
            calibration_probabilities = model.predict_proba(
                calibration_frame[DEFAULT_FEATURE_COLUMNS].to_numpy()
            )
            probabilities = model.predict_proba(test_frame[DEFAULT_FEATURE_COLUMNS].to_numpy())
        calibrator = fit_probability_calibrator(
            calibration_probabilities,
            calibration_labels,
            method=calibration_method,
        )
        calibrated_calibration_probabilities = calibrator.predict(calibration_probabilities)
        calibrated_probabilities = calibrator.predict(probabilities)
        threshold_selection = select_alert_threshold(
            calibration_labels,
            calibrated_calibration_probabilities,
            objective=args.threshold_objective,
        )
        tuned_probabilities = calibrated_probabilities
        tuned_threshold = threshold_selection.threshold
        raw_metrics = classification_metrics(test_labels, probabilities)
        calibrated_metrics = classification_metrics(test_labels, calibrated_probabilities)
        tuned_metrics = classification_metrics(test_labels, tuned_probabilities, threshold=tuned_threshold)
        warning_levels = assign_warning_levels(
            tuned_probabilities,
            alert_threshold=tuned_threshold,
            watch_threshold=max(0.01, tuned_threshold * 0.5),
        )
        prediction_rows.append(
            test_frame.loc[:, ["date", "ticker", "risk_label"]]
            .assign(
                fold_id=fold.fold_id,
                model=model_name,
                risk_probability=probabilities,
                calibrated_risk_probability=calibrated_probabilities,
                calibration_method=calibration_method,
                alert_threshold=tuned_threshold,
                warning_level=warning_levels,
            )
            .reset_index(drop=True)
        )

        fold_results.append(
            {
                "fold_id": fold.fold_id,
                "model": model_name,
                "train_start": str(fold.train_dates[0].date()),
                "train_end": str(fold.train_dates[-1].date()),
                "calibration_start": str(fold.calibration_dates[0].date()),
                "calibration_end": str(fold.calibration_dates[-1].date()),
                "test_start": str(fold.test_dates[0].date()),
                "test_end": str(fold.test_dates[-1].date()),
                "train_rows": len(fold.train_index),
                "calibration_rows": len(fold.calibration_index),
                "test_rows": len(fold.test_index),
                "threshold_selection": {
                    "objective": threshold_selection.objective,
                    "threshold": threshold_selection.threshold,
                    "objective_value": threshold_selection.objective_value,
                    "calibration_metrics": threshold_selection.metrics,
                },
                "raw_metrics": raw_metrics,
                "calibrated_metrics": calibrated_metrics,
                "tuned_metrics": tuned_metrics,
            }
        )

    raw_metric_names = list(fold_results[0]["raw_metrics"].keys()) if fold_results else []
    calibrated_metric_names = list(fold_results[0]["calibrated_metrics"].keys()) if fold_results else []
    tuned_metric_names = list(fold_results[0]["tuned_metrics"].keys()) if fold_results else []
    summary = {
        "raw": {
            name: float(pd.Series([fold["raw_metrics"][name] for fold in fold_results]).mean(skipna=True))
            for name in raw_metric_names
        },
        "calibrated": {
            name: float(
                pd.Series([fold["calibrated_metrics"][name] for fold in fold_results]).mean(skipna=True)
            )
            for name in calibrated_metric_names
        },
        "tuned": {
            name: float(pd.Series([fold["tuned_metrics"][name] for fold in fold_results]).mean(skipna=True))
            for name in tuned_metric_names
        },
        "threshold": {
            "mean": float(
                pd.Series([fold["threshold_selection"]["threshold"] for fold in fold_results]).mean()
            ),
            "std": float(
                pd.Series([fold["threshold_selection"]["threshold"] for fold in fold_results]).std()
            ),
        },
    }

    predictions = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()

    return {
        "input": str(args.input),
        "model_type": args.model_type,
        "feature_columns": DEFAULT_FEATURE_COLUMNS,
        "horizon": args.horizon,
        "drawdown_threshold": args.drawdown_threshold,
        "calibration_method": calibration_method,
        "threshold_objective": args.threshold_objective,
        "fold_count": len(fold_results),
        "rows_after_filtering": len(training_frame),
        "folds": fold_results,
        "summary": summary,
        "predictions": predictions,
    }


def build_baseline_model(args: argparse.Namespace) -> tuple[LogisticRiskModel | TreeRiskModel, str]:
    """Build the requested baseline model without changing the legacy default."""

    if args.model_type == "logistic":
        return LogisticRiskModel(), "logistic_regression"
    if args.model_type in {"random_forest", "hist_gradient_boosting"}:
        model = TreeRiskModel(
            model_type=args.model_type,
            n_estimators=args.tree_n_estimators,
            max_depth=args.tree_max_depth,
            learning_rate=args.tree_learning_rate,
            max_iter=args.tree_max_iter,
        )
        return model, model.model_name
    raise ValueError(f"Unsupported model type: {args.model_type}")


def main() -> None:
    args = parse_args()
    results = run_training(args)
    predictions = results.pop("predictions")
    output = json.dumps(results, indent=2)
    print(output)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    if args.predictions_output is not None:
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(args.predictions_output, index=False)


if __name__ == "__main__":
    main()
