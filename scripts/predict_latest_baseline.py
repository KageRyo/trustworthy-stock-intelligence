"""Train a leakage-aware baseline and write latest serving warnings."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from tsi.data.csv import read_ohlcv_csv
from tsi.data.postgres import write_prediction_batch_to_postgres
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.labeling.drawdown import add_future_drawdown_label
from tsi.labeling.warning_level import select_alert_threshold
from tsi.models.logistic import LogisticRiskModel
from tsi.serving.schema import build_prediction_batch, write_prediction_batch_json
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator
from tsi.trust.decision import (
    TrustDecisionConfig,
    assign_trust_decisions,
    compute_watch_threshold,
)
from tsi.trust.reason_codes import build_reason_codes
from tsi.trust.trust_score import TrustScoreMethod, compute_trust_score
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="OHLCV CSV input.")
    parser.add_argument("--output", type=Path, required=True, help="Prediction CSV output.")
    parser.add_argument("--json-output", type=Path, required=True, help="Serving JSON output.")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--train-size", type=int, default=None)
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
    parser.add_argument("--watch-threshold-ratio", type=float, default=0.8)
    parser.add_argument("--min-watch-threshold", type=float, default=0.01)
    parser.add_argument("--trust-threshold", type=float, default=0.1)
    parser.add_argument("--uncertainty-threshold", type=float, default=0.8)
    parser.add_argument("--uncertainty-penalty", type=float, default=0.5)
    parser.add_argument(
        "--uncertainty-method",
        choices=["entropy", "margin"],
        default="entropy",
    )
    parser.add_argument(
        "--trust-score-method",
        choices=["subtractive", "multiplicative"],
        default="multiplicative",
    )
    parser.add_argument("--run-id", default="baseline_latest")
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write the prediction batch into PostgreSQL prediction/warning tables.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to TSI_DATABASE_URL.",
    )
    parser.add_argument(
        "--feature-interval",
        choices=["1m", "5m", "1d"],
        default="1d",
        help="Feature interval metadata stored with the prediction batch.",
    )
    return parser.parse_args(argv)


def prepare_frames(
    ohlcv: pd.DataFrame,
    *,
    horizon: int,
    drawdown_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build leakage-aware training rows and latest inference rows."""

    featured = build_technical_features(ohlcv)
    latest_frame = select_latest_feature_rows(featured)

    labeled = add_future_drawdown_label(
        featured,
        horizon=horizon,
        threshold=drawdown_threshold,
    )
    training_frame = labeled[labeled["label_available"]].copy()
    training_frame = training_frame.dropna(subset=DEFAULT_FEATURE_COLUMNS)
    training_frame["date"] = pd.to_datetime(training_frame["date"])
    training_frame["risk_label"] = training_frame["risk_label"].astype(int)
    training_frame = training_frame.sort_values(["date", "ticker"]).reset_index(drop=True)
    return training_frame, latest_frame


def select_latest_feature_rows(featured: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest feature-complete row for each ticker."""

    frame = featured.dropna(subset=DEFAULT_FEATURE_COLUMNS).copy()
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    return (
        frame.sort_values(["ticker", "date"])
        .groupby("ticker", as_index=False, sort=True)
        .tail(1)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )


def split_train_calibration(
    training_frame: pd.DataFrame,
    *,
    calibration_size: int,
    train_size: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split historical labeled rows into train and later calibration windows."""

    if calibration_size < 1:
        raise ValueError("calibration_size must be at least 1")
    unique_dates = pd.Index(sorted(pd.to_datetime(training_frame["date"]).unique()))
    if len(unique_dates) <= calibration_size:
        raise ValueError("Not enough labeled dates for the requested calibration_size")

    calibration_dates = set(unique_dates[-calibration_size:])
    train_dates = unique_dates[:-calibration_size]
    if train_size is not None:
        if train_size < 1:
            raise ValueError("train_size must be at least 1 when provided")
        train_dates = train_dates[-train_size:]
    train_date_set = set(train_dates)

    train_frame = training_frame[training_frame["date"].isin(train_date_set)].copy()
    calibration_frame = training_frame[training_frame["date"].isin(calibration_dates)].copy()
    if train_frame.empty or calibration_frame.empty:
        raise ValueError("train and calibration frames must not be empty")
    return train_frame, calibration_frame


def run_prediction(args: argparse.Namespace) -> pd.DataFrame:
    """Train a baseline on historical labels and write latest predictions."""

    ohlcv = read_ohlcv_csv(args.input)
    training_frame, latest_frame = prepare_frames(
        ohlcv,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )
    if latest_frame.empty:
        raise ValueError("No latest feature rows were created; check input data")

    train_frame, calibration_frame = split_train_calibration(
        training_frame,
        calibration_size=args.calibration_size,
        train_size=args.train_size,
    )
    model, model_name = fit_baseline_model(train_frame)
    calibration_probabilities = model.predict_proba(calibration_frame[DEFAULT_FEATURE_COLUMNS].to_numpy())
    probabilities = model.predict_proba(latest_frame[DEFAULT_FEATURE_COLUMNS].to_numpy())

    calibration_method: CalibrationMethod = args.calibration_method
    calibrator = fit_probability_calibrator(
        calibration_probabilities,
        calibration_frame["risk_label"].to_numpy(),
        method=calibration_method,
    )
    calibrated_calibration_probabilities = calibrator.predict(calibration_probabilities)
    calibrated_probabilities = calibrator.predict(probabilities)
    threshold_selection = select_alert_threshold(
        calibration_frame["risk_label"].to_numpy(),
        calibrated_calibration_probabilities,
        objective=args.threshold_objective,
    )
    alert_threshold = threshold_selection.threshold
    watch_threshold = compute_watch_threshold(
        alert_threshold,
        watch_threshold_ratio=args.watch_threshold_ratio,
        min_watch_threshold=args.min_watch_threshold,
    )
    uncertainty = uncertainty_scores(calibrated_probabilities, method=args.uncertainty_method)
    trust_score_method: TrustScoreMethod = args.trust_score_method
    trust_scores = compute_trust_score(
        calibrated_probabilities,
        uncertainty,
        uncertainty_penalty=args.uncertainty_penalty,
        method=trust_score_method,
    )
    decision_config = TrustDecisionConfig(
        alert_threshold=alert_threshold,
        watch_threshold=watch_threshold,
        trust_threshold=args.trust_threshold,
        uncertainty_threshold=args.uncertainty_threshold,
    )
    warning_levels = assign_trust_decisions(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        config=decision_config,
    )
    reason_codes = build_reason_codes(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        warning_levels=warning_levels,
        config=decision_config,
    )
    predictions = latest_frame.loc[:, ["date", "ticker"]].assign(
        model=model_name,
        risk_probability=probabilities,
        calibrated_risk_probability=calibrated_probabilities,
        calibration_method=calibration_method,
        uncertainty_score=uncertainty,
        trust_score=trust_scores,
        alert_threshold=alert_threshold,
        watch_threshold=watch_threshold,
        warning_level=warning_levels,
        model_bundle=f"baseline_latest:{args.input}",
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    serving_frame = predictions.assign(reason_codes=reason_codes)
    batch = build_prediction_batch(serving_frame, run_id=args.run_id)
    write_prediction_batch_json(batch, args.json_output)
    if args.write_db:
        if not args.database_url:
            raise ValueError("--database-url or TSI_DATABASE_URL is required with --write-db")
        write_prediction_batch_to_postgres(
            args.database_url,
            batch,
            feature_interval=args.feature_interval,
        )
    return predictions


def fit_baseline_model(train_frame: pd.DataFrame) -> tuple[LogisticRiskModel, str]:
    """Fit a logistic model or a constant prior fallback for single-class data."""

    labels = train_frame["risk_label"].to_numpy()
    if pd.Series(labels).nunique() < 2:
        model = ConstantProbabilityModel(float(np.mean(labels)))
        return model, "constant_prior_latest"
    model = LogisticRiskModel()
    model.fit(train_frame[DEFAULT_FEATURE_COLUMNS].to_numpy(), labels)
    return model, "logistic_regression_latest"


class ConstantProbabilityModel:
    """Minimal probability model used when training data has one class."""

    def __init__(self, probability: float) -> None:
        self.probability = float(np.clip(probability, 0.0, 1.0))

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return np.full(features.shape[0], self.probability, dtype=float)


def uncertainty_scores(probabilities: np.ndarray, *, method: str) -> np.ndarray:
    if method == "entropy":
        return binary_entropy_uncertainty(probabilities)
    if method == "margin":
        return margin_uncertainty(probabilities)
    raise ValueError(f"Unsupported uncertainty method: {method}")


def main() -> None:
    args = parse_args()
    predictions = run_prediction(args)
    print(f"Wrote {len(predictions)} latest baseline prediction rows to {args.output}")
    print(f"Wrote serving JSON to {args.json_output}")
    if args.write_db:
        print("Wrote serving warning batch to PostgreSQL")


if __name__ == "__main__":
    main()
