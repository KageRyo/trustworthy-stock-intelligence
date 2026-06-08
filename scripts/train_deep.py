"""Train a GPU-backed Temporal Transformer for stock risk warning."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from scripts.train import prepare_training_frame
from tsi.data.split import build_walk_forward_splits
from tsi.evaluation.metrics import classification_metrics
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS
from tsi.labeling.warning_level import select_alert_threshold
from tsi.models.temporal_transformer import TemporalTransformerRiskModel
from tsi.training.dataset import SequenceDataset, build_sequence_dataset
from tsi.training.trainer import (
    DeepTrainingConfig,
    fit_sequence_standardizer,
    predict_probabilities,
    resolve_training_device,
    train_binary_sequence_model,
    transform_sequence_features,
)
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator
from tsi.trust.decision import (
    TrustDecisionConfig,
    assign_trust_decisions,
    compute_watch_threshold,
)
from tsi.trust.trust_score import compute_trust_score
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to OHLCV CSV input.")
    parser.add_argument("--lookback", type=int, default=60, help="Sequence lookback window.")
    parser.add_argument("--horizon", type=int, default=5, help="Future label horizon.")
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--step-size", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--d-model", type=int, default=64)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dim-feedforward", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.1)
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
    parser.add_argument(
        "--uncertainty-method",
        choices=["entropy", "margin"],
        default="entropy",
        help="Uncertainty score used by the trust layer.",
    )
    parser.add_argument("--uncertainty-penalty", type=float, default=0.5)
    parser.add_argument("--trust-threshold", type=float, default=0.5)
    parser.add_argument("--uncertainty-threshold", type=float, default=0.8)
    parser.add_argument("--watch-threshold-ratio", type=float, default=0.8)
    parser.add_argument("--min-watch-threshold", type=float, default=0.05)
    parser.add_argument("--device", choices=["cuda", "cpu", "auto"], default="cuda")
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow CPU fallback. Use only for tests or local debugging.",
    )
    parser.add_argument(
        "--disable-multi-gpu",
        action="store_true",
        help="Disable DataParallel when multiple CUDA devices are available.",
    )
    parser.add_argument("--max-folds", type=int, default=None, help="Optional fold cap for smoke runs.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--predictions-output", type=Path, default=None)
    return parser.parse_args(argv)


def subset_sequence_dataset(dataset: SequenceDataset, source_indices: Sequence[int]) -> SequenceDataset:
    """Select sequence samples whose target rows belong to the given frame indices."""

    source_index_set = set(int(index) for index in source_indices)
    mask = dataset.metadata["source_index"].isin(source_index_set).to_numpy()
    metadata = dataset.metadata.loc[mask].reset_index(drop=True)
    return SequenceDataset(
        x=dataset.x[mask],
        y=dataset.y[mask],
        metadata=metadata,
        feature_columns=dataset.feature_columns,
        lookback=dataset.lookback,
    )


def build_prediction_frame(
    metadata: pd.DataFrame,
    *,
    labels: np.ndarray,
    probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray,
    calibration_method: str,
    uncertainty_scores: np.ndarray,
    trust_scores: np.ndarray,
    alert_threshold: float,
    warning_levels: np.ndarray,
    fold_id: int,
    model_name: str,
) -> pd.DataFrame:
    """Build a prediction artifact with risk and trust-layer outputs."""

    return metadata.loc[:, ["date", "ticker"]].assign(
        risk_label=labels.astype(int),
        fold_id=fold_id,
        model=model_name,
        risk_probability=probabilities,
        calibrated_risk_probability=calibrated_probabilities,
        calibration_method=calibration_method,
        uncertainty_score=uncertainty_scores,
        trust_score=trust_scores,
        alert_threshold=alert_threshold,
        warning_level=warning_levels,
    )


def _build_model(args: argparse.Namespace, input_size: int) -> TemporalTransformerRiskModel:
    return TemporalTransformerRiskModel(
        input_size=input_size,
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        dim_feedforward=args.dim_feedforward,
        dropout=args.dropout,
        max_sequence_length=args.lookback,
    )


def _uncertainty_scores(probabilities: np.ndarray, *, method: str) -> np.ndarray:
    if method == "entropy":
        return binary_entropy_uncertainty(probabilities)
    if method == "margin":
        return margin_uncertainty(probabilities)
    raise ValueError(f"Unsupported uncertainty method: {method}")


def run_training(args: argparse.Namespace) -> dict[str, object]:
    """Train one Temporal Transformer per walk-forward fold."""

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = resolve_training_device(args.device, allow_cpu=args.allow_cpu)

    ohlcv = pd.read_csv(args.input)
    training_frame = prepare_training_frame(
        ohlcv,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )
    sequence_dataset = build_sequence_dataset(
        training_frame,
        feature_columns=DEFAULT_FEATURE_COLUMNS,
        lookback=args.lookback,
    )
    if len(sequence_dataset.y) == 0:
        raise ValueError("No sequence samples were created; reduce lookback or check input data")

    folds = build_walk_forward_splits(
        training_frame,
        train_size=args.train_size,
        calibration_size=args.calibration_size,
        test_size=args.test_size,
        step_size=args.step_size,
    )
    if args.max_folds is not None:
        folds = folds[: args.max_folds]

    training_config = DeepTrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        num_workers=args.num_workers,
    )
    calibration_method: CalibrationMethod = args.calibration_method

    fold_results: list[dict[str, object]] = []
    prediction_rows: list[pd.DataFrame] = []
    for fold in folds:
        train_dataset = subset_sequence_dataset(sequence_dataset, fold.train_index)
        calibration_dataset = subset_sequence_dataset(sequence_dataset, fold.calibration_index)
        test_dataset = subset_sequence_dataset(sequence_dataset, fold.test_index)
        if len(train_dataset.y) == 0 or len(calibration_dataset.y) == 0 or len(test_dataset.y) == 0:
            continue

        standardizer = fit_sequence_standardizer(train_dataset.x)
        train_features = transform_sequence_features(train_dataset.x, standardizer)
        calibration_features = transform_sequence_features(calibration_dataset.x, standardizer)
        test_features = transform_sequence_features(test_dataset.x, standardizer)

        model = _build_model(args, input_size=len(sequence_dataset.feature_columns))
        trained_model, training_result = train_binary_sequence_model(
            model,
            train_features,
            train_dataset.y,
            calibration_features,
            calibration_dataset.y,
            config=training_config,
            device=device,
            use_multi_gpu=not args.disable_multi_gpu,
        )
        calibration_probabilities = predict_probabilities(
            trained_model,
            calibration_features,
            batch_size=args.batch_size,
            device=device,
            num_workers=args.num_workers,
        )
        probabilities = predict_probabilities(
            trained_model,
            test_features,
            batch_size=args.batch_size,
            device=device,
            num_workers=args.num_workers,
        )
        calibrator = fit_probability_calibrator(
            calibration_probabilities,
            calibration_dataset.y,
            method=calibration_method,
        )
        calibrated_calibration_probabilities = calibrator.predict(calibration_probabilities)
        calibrated_probabilities = calibrator.predict(probabilities)
        threshold_selection = select_alert_threshold(
            calibration_dataset.y,
            calibrated_calibration_probabilities,
            objective=args.threshold_objective,
        )
        alert_threshold = threshold_selection.threshold
        watch_threshold = compute_watch_threshold(
            alert_threshold,
            watch_threshold_ratio=args.watch_threshold_ratio,
            min_watch_threshold=args.min_watch_threshold,
        )
        uncertainty_scores = _uncertainty_scores(
            calibrated_probabilities,
            method=args.uncertainty_method,
        )
        trust_scores = compute_trust_score(
            calibrated_probabilities,
            uncertainty_scores,
            uncertainty_penalty=args.uncertainty_penalty,
        )
        warning_levels = assign_trust_decisions(
            calibrated_probabilities=calibrated_probabilities,
            uncertainty_scores=uncertainty_scores,
            trust_scores=trust_scores,
            config=TrustDecisionConfig(
                alert_threshold=alert_threshold,
                watch_threshold=watch_threshold,
                trust_threshold=args.trust_threshold,
                uncertainty_threshold=args.uncertainty_threshold,
            ),
        )
        raw_metrics = classification_metrics(test_dataset.y, probabilities)
        calibrated_metrics = classification_metrics(test_dataset.y, calibrated_probabilities)
        tuned_metrics = classification_metrics(
            test_dataset.y,
            calibrated_probabilities,
            threshold=alert_threshold,
        )
        prediction_rows.append(
            build_prediction_frame(
                test_dataset.metadata,
                labels=test_dataset.y,
                probabilities=probabilities,
                calibrated_probabilities=calibrated_probabilities,
                calibration_method=calibration_method,
                uncertainty_scores=uncertainty_scores,
                trust_scores=trust_scores,
                alert_threshold=alert_threshold,
                warning_levels=warning_levels,
                fold_id=fold.fold_id,
                model_name="temporal_transformer",
            )
        )

        fold_results.append(
            {
                "fold_id": fold.fold_id,
                "model": "temporal_transformer",
                "train_start": str(fold.train_dates[0].date()),
                "train_end": str(fold.train_dates[-1].date()),
                "calibration_start": str(fold.calibration_dates[0].date()),
                "calibration_end": str(fold.calibration_dates[-1].date()),
                "test_start": str(fold.test_dates[0].date()),
                "test_end": str(fold.test_dates[-1].date()),
                "train_rows": int(len(train_dataset.y)),
                "calibration_rows": int(len(calibration_dataset.y)),
                "test_rows": int(len(test_dataset.y)),
                "training": {
                    "epochs": args.epochs,
                    "batch_size": args.batch_size,
                    "device": training_result.device,
                    "gpu_count": training_result.gpu_count,
                    "used_data_parallel": training_result.used_data_parallel,
                    "train_loss": training_result.train_loss,
                    "validation_loss": training_result.validation_loss,
                },
                "threshold_selection": {
                    "objective": threshold_selection.objective,
                    "threshold": threshold_selection.threshold,
                    "objective_value": threshold_selection.objective_value,
                    "calibration_metrics": threshold_selection.metrics,
                    "watch_threshold": watch_threshold,
                    "trust_threshold": args.trust_threshold,
                    "uncertainty_threshold": args.uncertainty_threshold,
                    "watch_threshold_ratio": args.watch_threshold_ratio,
                    "min_watch_threshold": args.min_watch_threshold,
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
            name: float(
                pd.Series([fold["tuned_metrics"][name] for fold in fold_results]).mean(skipna=True)
            )
            for name in tuned_metric_names
        },
    }
    predictions = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()
    gpu_counts = [fold["training"]["gpu_count"] for fold in fold_results]
    used_data_parallel = any(fold["training"]["used_data_parallel"] for fold in fold_results)

    return {
        "input": str(args.input),
        "feature_columns": DEFAULT_FEATURE_COLUMNS,
        "lookback": args.lookback,
        "horizon": args.horizon,
        "drawdown_threshold": args.drawdown_threshold,
        "model_config": {
            "d_model": args.d_model,
            "num_heads": args.num_heads,
            "num_layers": args.num_layers,
            "dim_feedforward": args.dim_feedforward,
            "dropout": args.dropout,
        },
        "trust_config": {
            "calibration_method": calibration_method,
            "threshold_objective": args.threshold_objective,
            "uncertainty_method": args.uncertainty_method,
            "uncertainty_penalty": args.uncertainty_penalty,
            "trust_threshold": args.trust_threshold,
            "uncertainty_threshold": args.uncertainty_threshold,
            "watch_threshold_ratio": args.watch_threshold_ratio,
            "min_watch_threshold": args.min_watch_threshold,
        },
        "training_config": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "num_workers": args.num_workers,
            "device": str(device),
            "max_gpu_count": max(gpu_counts) if gpu_counts else 0,
            "used_data_parallel": used_data_parallel,
        },
        "fold_count": len(fold_results),
        "rows_after_filtering": len(training_frame),
        "sequence_count": len(sequence_dataset.y),
        "folds": fold_results,
        "summary": summary,
        "predictions": predictions,
    }


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
