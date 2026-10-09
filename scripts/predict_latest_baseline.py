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
from tsi.evaluation.drift import (
    CalibrationDriftAssessment,
    assess_calibration_drift,
    calibration_drift_reason_codes,
)
from tsi.evaluation.metrics import classification_metrics
from tsi.features.sets import (
    FEATURE_SETS,
    build_feature_frame,
    feature_set_requires_market_reference,
    resolve_feature_set,
)
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS
from tsi.labeling.drawdown import add_future_drawdown_label
from tsi.labeling.warning_level import (
    parse_alert_policy,
    select_alert_threshold,
    select_alert_threshold_by_policy,
)
from tsi.models.logistic import LogisticRiskModel
from tsi.serving.schema import (
    AlertPolicyMetadata,
    CalibrationDriftMetadata,
    build_prediction_batch,
    write_prediction_batch_json,
)
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator
from tsi.trust.decision import (
    TrustDecisionConfig,
    assign_trust_decisions,
    compute_watch_threshold,
)
from tsi.trust.explainability import build_logistic_feature_attributions
from tsi.trust.reason_codes import build_reason_codes
from tsi.trust.reliability import ReliabilityAssessor, ReliabilityConfig, ReliabilityScores
from tsi.trust.trust_score import TrustScoreMethod, compute_trust_score, data_quality_scores
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty


class InsufficientHistoryError(ValueError):
    """The input has too little labeled or feature-complete history to fit and score a model.

    Callers such as the on-demand bridge turn this into a typed ``insufficient_history``
    abstention; configuration errors stay plain ``ValueError``.
    """


# Below this many calibration-window alerts, policy thresholds are too noisy to trust.
MIN_RELIABLE_CALIBRATION_ALERTS = 20
# Serving computes features from the ticker's own OHLCV only; market-relative sets need a
# reference-data path that serving does not have yet. See experiments/017_feature_sets.
SERVING_FEATURE_SETS = [
    name for name, columns in FEATURE_SETS.items()
    if not feature_set_requires_market_reference(columns)
]
DEFAULT_SERVING_FEATURE_SET = "technical_range"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="OHLCV CSV input.")
    parser.add_argument("--output", type=Path, required=True, help="Prediction CSV output.")
    parser.add_argument("--json-output", type=Path, required=True, help="Serving JSON output.")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument(
        "--feature-set",
        choices=SERVING_FEATURE_SETS,
        default=DEFAULT_SERVING_FEATURE_SET,
        help="Named OHLCV feature set. See experiments/017_feature_sets.",
    )
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument(
        "--drift-size",
        type=int,
        default=21,
        help="Later labeled dates used only to evaluate calibration drift; zero disables the gate.",
    )
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
    parser.add_argument(
        "--alert-policy",
        default="alert_rate:0.05",
        help=(
            "Alert threshold policy chosen on the calibration window: alert_rate:<rate>, "
            "target_precision:<precision>, f1, or objective (uses --threshold-objective). "
            "See experiments/016_alert_policy."
        ),
    )
    parser.add_argument(
        "--watch-policy",
        default="alert_rate:0.2",
        help="Watch threshold policy (same forms as --alert-policy), or ratio to use "
        "--watch-threshold-ratio times the alert threshold.",
    )
    parser.add_argument("--watch-threshold-ratio", type=float, default=0.8)
    parser.add_argument("--min-watch-threshold", type=float, default=0.01)
    parser.add_argument(
        "--trust-method",
        choices=["reliability", "legacy"],
        default="reliability",
        help=(
            "reliability: uncertainty from ensemble disagreement and feature novelty, trust "
            "from data quality and drift. legacy: entropy of the risk probability."
        ),
    )
    parser.add_argument(
        "--trust-threshold",
        type=float,
        default=None,
        help="Minimum trust for alerts. Defaults to 0.4 (reliability) or 0.1 (legacy).",
    )
    parser.add_argument("--uncertainty-threshold", type=float, default=0.8)
    parser.add_argument("--reliability-members", type=int, default=10)
    parser.add_argument("--required-history-rows", type=int, default=252)
    parser.add_argument("--conformal-alpha", type=float, default=0.1)
    parser.add_argument("--uncertainty-penalty", type=float, default=0.5)
    parser.add_argument(
        "--uncertainty-method",
        choices=["entropy", "margin"],
        default="entropy",
        help="Legacy trust method only.",
    )
    parser.add_argument(
        "--trust-score-method",
        choices=["subtractive", "multiplicative"],
        default="multiplicative",
        help="Legacy trust method only.",
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
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build leakage-aware training rows and latest inference rows."""

    featured = build_feature_frame(ohlcv, feature_columns)
    latest_frame = select_latest_feature_rows(featured, feature_columns)

    labeled = add_future_drawdown_label(
        featured,
        horizon=horizon,
        threshold=drawdown_threshold,
    )
    training_frame = labeled[labeled["label_available"]].copy()
    training_frame = training_frame.dropna(subset=list(feature_columns))
    training_frame["date"] = pd.to_datetime(training_frame["date"])
    training_frame["risk_label"] = training_frame["risk_label"].astype(int)
    training_frame = training_frame.sort_values(["date", "ticker"]).reset_index(drop=True)
    return training_frame, latest_frame


def select_latest_feature_rows(
    featured: pd.DataFrame,
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS,
) -> pd.DataFrame:
    """Keep the latest feature-complete row for each ticker."""

    frame = featured.dropna(subset=list(feature_columns)).copy()
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

    train_frame, calibration_frame, _ = split_train_calibration_recent(
        training_frame,
        calibration_size=calibration_size,
        drift_size=0,
        train_size=train_size,
    )
    return train_frame, calibration_frame


def split_train_calibration_recent(
    training_frame: pd.DataFrame,
    *,
    calibration_size: int,
    drift_size: int,
    train_size: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split rows into train, calibration reference, and later drift windows."""

    if calibration_size < 1:
        raise ValueError("calibration_size must be at least 1")
    if drift_size < 0:
        raise ValueError("drift_size must be non-negative")
    unique_dates = pd.Index(sorted(pd.to_datetime(training_frame["date"]).unique()))
    required_window_size = calibration_size + drift_size
    if len(unique_dates) <= required_window_size:
        raise InsufficientHistoryError(
            "Not enough labeled dates for the requested calibration and drift windows"
        )

    recent_dates = set(unique_dates[-drift_size:]) if drift_size else set()
    calibration_end = len(unique_dates) - drift_size if drift_size else len(unique_dates)
    calibration_start = calibration_end - calibration_size
    calibration_dates = set(unique_dates[calibration_start:calibration_end])
    train_dates = unique_dates[:calibration_start]
    if train_size is not None:
        if train_size < 1:
            raise ValueError("train_size must be at least 1 when provided")
        train_dates = train_dates[-train_size:]
    train_date_set = set(train_dates)

    train_frame = training_frame[training_frame["date"].isin(train_date_set)].copy()
    calibration_frame = training_frame[training_frame["date"].isin(calibration_dates)].copy()
    recent_frame = training_frame[training_frame["date"].isin(recent_dates)].copy()
    if train_frame.empty or calibration_frame.empty or (drift_size and recent_frame.empty):
        raise InsufficientHistoryError("train, calibration, and drift frames must not be empty")
    return train_frame, calibration_frame, recent_frame


def run_prediction(args: argparse.Namespace) -> pd.DataFrame:
    """Train a baseline on historical labels and write latest predictions."""

    if args.drift_size < 0:
        raise ValueError("--drift-size must be non-negative")
    ohlcv = read_ohlcv_csv(args.input)
    feature_columns = resolve_feature_set(args.feature_set)
    training_frame, latest_frame = prepare_frames(
        ohlcv,
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
        feature_columns=feature_columns,
    )
    if latest_frame.empty:
        raise InsufficientHistoryError("No latest feature rows were created; check input data")

    drift_evaluated = args.drift_size > 0 and _has_drift_history(
        training_frame,
        calibration_size=args.calibration_size,
        drift_size=args.drift_size,
    )
    drift_note = (
        "Calibration drift evaluation was disabled by --drift-size=0."
        if args.drift_size == 0
        else "No later labeled window was available for drift evaluation."
    )
    if drift_evaluated:
        drift_note = "Compared a fitted calibration reference window with later labeled rows."
    if drift_evaluated:
        train_frame, calibration_frame, recent_frame = split_train_calibration_recent(
            training_frame,
            calibration_size=args.calibration_size,
            drift_size=args.drift_size,
            train_size=args.train_size,
        )
    else:
        train_frame, calibration_frame = split_train_calibration(
            training_frame,
            calibration_size=args.calibration_size,
            train_size=args.train_size,
        )
        recent_frame = training_frame.iloc[0:0].copy()
    model, model_name = fit_baseline_model(train_frame, feature_columns)
    calibration_probabilities = model.predict_proba(calibration_frame[feature_columns].to_numpy())
    probabilities = model.predict_proba(latest_frame[feature_columns].to_numpy())

    calibration_method: CalibrationMethod = args.calibration_method
    calibrator = fit_probability_calibrator(
        calibration_probabilities,
        calibration_frame["risk_label"].to_numpy(),
        method=calibration_method,
    )
    calibrated_calibration_probabilities = calibrator.predict(calibration_probabilities)
    calibrated_probabilities = calibrator.predict(probabilities)
    drift_assessment, calibration_drift = evaluate_calibration_drift(
        model,
        calibrator,
        calibration_frame,
        recent_frame,
        evaluated=drift_evaluated,
        note=drift_note,
        feature_columns=feature_columns,
    )
    alert_threshold, watch_threshold, alert_policy_metadata = select_warning_thresholds(
        args,
        calibration_frame["risk_label"].to_numpy(),
        calibrated_calibration_probabilities,
    )
    row_reason_codes: list[list[str]] | None = None
    if args.trust_method == "reliability":
        reliability = assess_reliability(
            args,
            model,
            calibrator,
            train_frame=train_frame,
            calibration_frame=calibration_frame,
            training_frame=training_frame,
            latest_frame=latest_frame,
            calibrated_calibration_probabilities=calibrated_calibration_probabilities,
            calibrated_probabilities=calibrated_probabilities,
            feature_columns=feature_columns,
        )
        uncertainty = reliability.uncertainty
        trust_scores = reliability.trust
        row_reason_codes = reliability.reason_codes
    else:
        uncertainty = uncertainty_scores(calibrated_probabilities, method=args.uncertainty_method)
        trust_score_method: TrustScoreMethod = args.trust_score_method
        trust_scores = compute_trust_score(
            calibrated_probabilities,
            uncertainty,
            uncertainty_penalty=args.uncertainty_penalty,
            method=trust_score_method,
        )
    if drift_assessment is not None:
        trust_scores = np.clip(trust_scores * drift_assessment.trust_multiplier, 0.0, 1.0)
    decision_config = TrustDecisionConfig(
        alert_threshold=alert_threshold,
        watch_threshold=watch_threshold,
        trust_threshold=resolve_trust_threshold(args),
        uncertainty_threshold=args.uncertainty_threshold,
    )
    warning_levels = assign_trust_decisions(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        config=decision_config,
    )
    if drift_assessment is not None and drift_assessment.abstain:
        warning_levels = np.full(warning_levels.shape, "abstain", dtype=object)
    drift_reason_codes = calibration_drift_reason_codes(
        drift_assessment,
        evaluated=drift_evaluated,
    )
    reason_codes = build_reason_codes(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        warning_levels=warning_levels,
        config=decision_config,
        extra_reason_codes=drift_reason_codes,
        row_reason_codes=row_reason_codes,
    )
    feature_attributions = build_logistic_feature_attributions(
        model,
        latest_frame[feature_columns].to_numpy(),
        feature_columns,
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
        model_bundle=f"baseline_latest:{args.feature_set}:{args.input}",
        feature_attributions=feature_attributions,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    serving_frame = predictions.assign(reason_codes=reason_codes)
    batch = build_prediction_batch(
        serving_frame,
        run_id=args.run_id,
        calibration_drift=calibration_drift,
        feature_interval=args.feature_interval,
        alert_policy=alert_policy_metadata,
    )
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


def select_warning_thresholds(
    args: argparse.Namespace,
    labels: np.ndarray,
    calibrated_probabilities: np.ndarray,
) -> tuple[float, float, AlertPolicyMetadata]:
    """Choose alert and watch thresholds on calibration rows according to the CLI policies."""

    if args.alert_policy == "objective":
        selection = select_alert_threshold(
            labels, calibrated_probabilities, objective=args.threshold_objective
        )
        alert_label = f"objective:{args.threshold_objective}"
        alert_threshold, alert_met, alert_metrics = selection.threshold, True, selection.metrics
    else:
        policy = parse_alert_policy(args.alert_policy)
        chosen = select_alert_threshold_by_policy(labels, calibrated_probabilities, policy)
        alert_label = policy.label
        alert_threshold, alert_met, alert_metrics = chosen.threshold, chosen.target_met, chosen.metrics

    if args.watch_policy == "ratio":
        watch_threshold = compute_watch_threshold(
            alert_threshold,
            watch_threshold_ratio=args.watch_threshold_ratio,
            min_watch_threshold=args.min_watch_threshold,
        )
        watch_label, watch_met = f"ratio:{args.watch_threshold_ratio:g}", True
    else:
        watch_policy = parse_alert_policy(args.watch_policy)
        watch = select_alert_threshold_by_policy(labels, calibrated_probabilities, watch_policy)
        watch_threshold = min(alert_threshold, watch.threshold)
        watch_label, watch_met = watch_policy.label, watch.target_met

    calibration_alerts = int(np.sum(calibrated_probabilities >= alert_threshold))
    note = ""
    if calibration_alerts < MIN_RELIABLE_CALIBRATION_ALERTS:
        note = (
            f"small calibration window: {calibration_alerts} alert rows out of "
            f"{len(calibrated_probabilities)}; thresholds and calibration precision are noisy"
        )
    metadata = AlertPolicyMetadata(
        alert_policy=alert_label,
        watch_policy=watch_label,
        alert_target_met=alert_met,
        watch_target_met=watch_met,
        calibration_alert_rate=float(np.mean(calibrated_probabilities >= alert_threshold)),
        calibration_watch_rate=float(np.mean(calibrated_probabilities >= watch_threshold)),
        calibration_alert_precision=float(alert_metrics["precision"]),
        note=note,
    )
    return alert_threshold, watch_threshold, metadata


def resolve_trust_threshold(args: argparse.Namespace) -> float:
    if args.trust_threshold is not None:
        return float(args.trust_threshold)
    # 0.4 lets full-quality data pass under the 0.5 drift multiplier only when quality >= 0.8.
    return 0.4 if args.trust_method == "reliability" else 0.1


def ticker_data_quality(
    training_frame: pd.DataFrame,
    latest_frame: pd.DataFrame,
    *,
    required_history_rows: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Score each latest row by labeled history depth and staleness versus the batch."""

    history_rows = latest_frame["ticker"].map(training_frame["ticker"].value_counts()).fillna(0)
    latest_dates = pd.to_datetime(latest_frame["date"])
    stale = (latest_dates < latest_dates.max()).to_numpy()
    quality = data_quality_scores(
        history_rows=history_rows.to_numpy(),
        required_history_rows=required_history_rows,
        stale=stale,
    )
    return quality, stale


def assess_reliability(
    args: argparse.Namespace,
    model: LogisticRiskModel | ConstantProbabilityModel,
    calibrator: object,
    *,
    train_frame: pd.DataFrame,
    calibration_frame: pd.DataFrame,
    training_frame: pd.DataFrame,
    latest_frame: pd.DataFrame,
    calibrated_calibration_probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray,
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS,
) -> ReliabilityScores:
    """Score latest rows with model/data reliability, failing closed when unavailable."""

    if isinstance(model, ConstantProbabilityModel):
        return ReliabilityAssessor.unavailable(len(latest_frame))
    config = ReliabilityConfig(
        n_members=args.reliability_members,
        conformal_alpha=args.conformal_alpha,
    )
    try:
        assessor = ReliabilityAssessor(config).fit(
            train_features=train_frame[list(feature_columns)].to_numpy(),
            train_labels=train_frame["risk_label"].to_numpy(),
            train_groups=pd.to_datetime(train_frame["date"]).to_numpy(),
            calibration_features=calibration_frame[list(feature_columns)].to_numpy(),
            calibration_labels=calibration_frame["risk_label"].to_numpy(),
            calibrated_calibration_probabilities=calibrated_calibration_probabilities,
            calibrator=calibrator,
        )
    except ValueError:
        return ReliabilityAssessor.unavailable(len(latest_frame))
    quality, stale = ticker_data_quality(
        training_frame,
        latest_frame,
        required_history_rows=args.required_history_rows,
    )
    scores = assessor.score(
        latest_frame[list(feature_columns)].to_numpy(),
        calibrated_probabilities=calibrated_probabilities,
        data_quality=quality,
    )
    for codes, is_stale in zip(scores.reason_codes, stale, strict=True):
        if is_stale:
            codes.append("stale_ticker_data")
    return scores


def _has_drift_history(
    training_frame: pd.DataFrame,
    *,
    calibration_size: int,
    drift_size: int,
) -> bool:
    unique_dates = pd.Index(sorted(pd.to_datetime(training_frame["date"]).unique()))
    return drift_size > 0 and len(unique_dates) > calibration_size + drift_size


def evaluate_calibration_drift(
    model: LogisticRiskModel | ConstantProbabilityModel,
    calibrator: object,
    calibration_frame: pd.DataFrame,
    recent_frame: pd.DataFrame,
    *,
    evaluated: bool,
    note: str,
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS,
) -> tuple[CalibrationDriftAssessment | None, CalibrationDriftMetadata]:
    """Evaluate later labeled rows without fitting on the recent window."""

    if not evaluated or recent_frame.empty:
        return None, CalibrationDriftMetadata(
            note=note,
            calibration_rows=len(calibration_frame),
        )

    calibration_probabilities = calibrator.predict(
        model.predict_proba(calibration_frame[list(feature_columns)].to_numpy())
    )
    recent_probabilities = calibrator.predict(
        model.predict_proba(recent_frame[list(feature_columns)].to_numpy())
    )
    calibration_metrics = classification_metrics(
        calibration_frame["risk_label"].to_numpy(),
        calibration_probabilities,
    )
    recent_metrics = classification_metrics(
        recent_frame["risk_label"].to_numpy(),
        recent_probabilities,
    )
    assessment = assess_calibration_drift(calibration_metrics, recent_metrics)
    return assessment, CalibrationDriftMetadata(
        status="degraded" if assessment.degraded else "stable",
        event_rate_delta=assessment.event_rate_delta,
        ece_delta=assessment.ece_delta,
        brier_delta=assessment.brier_delta,
        signals=list(assessment.signals),
        degraded=assessment.degraded,
        abstain=assessment.abstain,
        trust_multiplier=assessment.trust_multiplier,
        calibration_rows=len(calibration_frame),
        recent_rows=len(recent_frame),
        note=note,
    )


def fit_baseline_model(
    train_frame: pd.DataFrame,
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS,
) -> tuple[LogisticRiskModel, str]:
    """Fit a logistic model or a constant prior fallback for single-class data."""

    labels = train_frame["risk_label"].to_numpy()
    if pd.Series(labels).nunique() < 2:
        model = ConstantProbabilityModel(float(np.mean(labels)))
        return model, "constant_prior_latest"
    model = LogisticRiskModel()
    model.fit(train_frame[list(feature_columns)].to_numpy(), labels)
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
