"""Compare alert-threshold policies with purged walk-forward evaluation.

Each fold fits the logistic baseline and probability calibration on its train and
calibration windows, chooses one alert threshold per policy on the calibration
window only, and scores the later test window. Reported metrics cover row-level
alert quality, alert volume, drawdown-episode coverage, and threshold stability.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.evaluate_selective_trust import resolve_output_dir
from scripts.train import prepare_training_frame
from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.data.split import build_walk_forward_splits
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS
from tsi.labeling.warning_level import (
    AlertPolicy,
    parse_alert_policy,
    select_alert_threshold_by_policy,
)
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator

DEFAULT_POLICIES = (
    "f1,"
    "target_precision:0.2,target_precision:0.25,target_precision:0.3,"
    "alert_rate:0.02,alert_rate:0.05,alert_rate:0.1,alert_rate:0.2"
)
TRADING_DAYS_PER_MONTH = 21
# Serving default: watch threshold = 0.8 * alert threshold (predict_latest_baseline).
WATCH_THRESHOLD_RATIO = 0.8


def parse_policies(text: str, *, min_alerts: int) -> list[AlertPolicy]:
    """Parse ``kind[:target]`` items separated by commas."""

    policies = [
        parse_alert_policy(item, min_alerts=min_alerts) for item in text.split(",") if item.strip()
    ]
    if not policies:
        raise ValueError("at least one alert policy is required")
    return policies


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--policies", default=DEFAULT_POLICIES)
    parser.add_argument("--min-alerts", type=int, default=20)
    return parser.parse_args(argv)


def drawdown_episodes(frame: pd.DataFrame) -> pd.Series:
    """Label consecutive positive rows per ticker as one episode id (-1 for negatives)."""

    ordered = frame.sort_values(["ticker", "date"])
    positive = ordered["risk_label"].to_numpy() == 1
    ticker_change = ordered["ticker"].ne(ordered["ticker"].shift()).to_numpy()
    starts = positive & (ticker_change | ~np.roll(positive, 1) | (np.arange(len(positive)) == 0))
    episode_ids = np.where(positive, np.cumsum(starts) - 1, -1)
    return pd.Series(episode_ids, index=ordered.index).reindex(frame.index)


def policy_test_metrics(
    labels: np.ndarray,
    alerts: np.ndarray,
    episodes: np.ndarray,
    *,
    tickers: int,
    dates: int,
) -> dict[str, float]:
    """Row-, volume-, and episode-level metrics for one alert vector."""

    true_positives = int(np.sum(alerts & (labels == 1)))
    alert_count = int(alerts.sum())
    positives = int(labels.sum())
    episode_ids = episodes[episodes >= 0]
    caught = np.unique(episodes[(episodes >= 0) & alerts])
    episode_count = np.unique(episode_ids).size
    precision = true_positives / alert_count if alert_count else float("nan")
    recall = true_positives / positives if positives else float("nan")
    return {
        "alerts": float(alert_count),
        "alert_rate": float(alerts.mean()),
        "precision": precision,
        "false_discovery_rate": 1.0 - precision if alert_count else float("nan"),
        "recall": recall,
        "episode_recall": caught.size / episode_count if episode_count else float("nan"),
        "alert_days_per_ticker_month": (
            alert_count / (tickers * dates) * TRADING_DAYS_PER_MONTH if tickers and dates else 0.0
        ),
    }


def score_fold(
    train_frame: pd.DataFrame,
    calibration_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    *,
    policies: Sequence[AlertPolicy],
    calibration_method: CalibrationMethod,
) -> list[dict[str, object]]:
    model = LogisticRiskModel().fit(
        train_frame[DEFAULT_FEATURE_COLUMNS].to_numpy(), train_frame["risk_label"].to_numpy()
    )
    raw_calibration = model.predict_proba(calibration_frame[DEFAULT_FEATURE_COLUMNS].to_numpy())
    calibration_labels = calibration_frame["risk_label"].to_numpy()
    calibrator = fit_probability_calibrator(
        raw_calibration, calibration_labels, method=calibration_method
    )
    calibrated_calibration = calibrator.predict(raw_calibration)
    calibrated_test = calibrator.predict(
        model.predict_proba(test_frame[DEFAULT_FEATURE_COLUMNS].to_numpy())
    )
    test_labels = test_frame["risk_label"].to_numpy()
    episodes = drawdown_episodes(test_frame).to_numpy()
    tickers = int(test_frame["ticker"].nunique())
    dates = int(test_frame["date"].nunique())

    rows: list[dict[str, object]] = []
    for policy in policies:
        selection = select_alert_threshold_by_policy(
            calibration_labels, calibrated_calibration, policy
        )
        alerts = calibrated_test >= selection.threshold
        watch_or_alert = calibrated_test >= selection.threshold * WATCH_THRESHOLD_RATIO
        watch_metrics = policy_test_metrics(
            test_labels, watch_or_alert, episodes, tickers=tickers, dates=dates
        )
        rows.append(
            {
                "policy": policy.label,
                "threshold": selection.threshold,
                "calibration_target_met": selection.target_met,
                "calibration_precision": selection.metrics["precision"],
                "calibration_alert_rate": selection.metrics["prediction_rate"],
                **policy_test_metrics(
                    test_labels, alerts, episodes, tickers=tickers, dates=dates
                ),
                "watch_or_alert_rate": watch_metrics["alert_rate"],
                "watch_or_alert_recall": watch_metrics["recall"],
                "watch_or_alert_episode_recall": watch_metrics["episode_recall"],
            }
        )
    return rows


def summarize(per_fold: pd.DataFrame, policies: Sequence[AlertPolicy]) -> dict[str, object]:
    """Pool fold results; precision and recall are pooled over all test rows."""

    summary: dict[str, dict[str, float]] = {}
    f1_precision = per_fold[per_fold["policy"] == "f1"].set_index("fold_id")["precision"]
    for policy in policies:
        rows = per_fold[per_fold["policy"] == policy.label]
        alerts = rows["alerts"].sum()
        true_positives = (rows["precision"].fillna(0.0) * rows["alerts"]).sum()
        positives = (rows["positives"]).sum()
        fold_precision = rows.set_index("fold_id")["precision"]
        paired = fold_precision.dropna().index.intersection(f1_precision.dropna().index)
        summary[policy.label] = {
            "alert_rate": float(alerts / rows["rows"].sum()),
            "precision": float(true_positives / alerts) if alerts else float("nan"),
            "recall": float(true_positives / positives) if positives else float("nan"),
            "episode_recall": float(rows["episode_recall"].mean()),
            "watch_or_alert_rate": float(
                (rows["watch_or_alert_rate"] * rows["rows"]).sum() / rows["rows"].sum()
            ),
            "watch_or_alert_recall": float(
                (rows["watch_or_alert_recall"] * rows["positives"]).sum() / positives
            )
            if positives
            else float("nan"),
            "watch_or_alert_episode_recall": float(rows["watch_or_alert_episode_recall"].mean()),
            "fold_median_alert_rate": float(rows["alert_rate"].median()),
            "fold_median_precision": float(rows["precision"].median()),
            "fold_median_recall": float(rows["recall"].median()),
            "alert_days_per_ticker_month": float(rows["alert_days_per_ticker_month"].mean()),
            "threshold_mean": float(rows["threshold"].mean()),
            "threshold_std": float(rows["threshold"].std()),
            "fold_precision_std": float(rows["precision"].std()),
            "calibration_target_met_rate": float(rows["calibration_target_met"].mean()),
            "folds_without_alerts": float((rows["alerts"] == 0).sum()),
            "fold_precision_beats_f1_rate": (
                float((fold_precision[paired] > f1_precision[paired]).mean())
                if len(paired)
                else float("nan")
            ),
        }
    return summary


def run(args: argparse.Namespace) -> dict[str, object]:
    output_dir = resolve_output_dir(args.output_dir, root=args.output_root)
    policies = parse_policies(args.policies, min_alerts=args.min_alerts)
    if "f1" not in {policy.label for policy in policies}:
        policies.insert(0, AlertPolicy(kind="f1", min_alerts=args.min_alerts))
    frame = prepare_training_frame(
        read_ohlcv_csv(args.input),
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
    )
    purge_size = args.horizon if args.purge_size is None else args.purge_size
    if purge_size < args.horizon:
        raise ValueError("purge_size must be at least horizon to prevent label-window leakage")
    folds = build_walk_forward_splits(
        frame,
        train_size=args.train_size,
        calibration_size=args.calibration_size,
        test_size=args.test_size,
        purge_size=purge_size,
        label_end_date_col="label_end_date",
    )
    if args.max_folds is not None:
        folds = folds[: args.max_folds]

    fold_rows: list[dict[str, object]] = []
    skipped = 0
    for fold in folds:
        train_frame = frame.loc[list(fold.train_index)]
        calibration_frame = frame.loc[list(fold.calibration_index)]
        test_frame = frame.loc[list(fold.test_index)]
        if (
            train_frame["risk_label"].nunique() < 2
            or calibration_frame["risk_label"].nunique() < 2
            or test_frame.empty
        ):
            skipped += 1
            continue
        for row in score_fold(
            train_frame,
            calibration_frame,
            test_frame,
            policies=policies,
            calibration_method=args.calibration_method,
        ):
            fold_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "test_start": str(fold.test_dates[0].date()),
                    "rows": float(len(test_frame)),
                    "positives": float(test_frame["risk_label"].sum()),
                    **row,
                }
            )
    if not fold_rows:
        raise ValueError("No walk-forward fold had both classes in train and calibration windows")
    per_fold = pd.DataFrame(fold_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    per_fold.to_csv(output_dir / "per_fold.csv", index=False)
    summary = {
        "input": str(args.input),
        "input_sha256": file_sha256(args.input),
        "protocol": {
            "feature_interval": "1d",
            "feature_columns": list(DEFAULT_FEATURE_COLUMNS),
            "horizon": args.horizon,
            "drawdown_threshold": args.drawdown_threshold,
            "train_size": args.train_size,
            "calibration_size": args.calibration_size,
            "test_size": args.test_size,
            "purge_size": purge_size,
            "calibration_method": args.calibration_method,
            "min_alerts": args.min_alerts,
            "skipped_folds": skipped,
        },
        "rows": int(per_fold.groupby("fold_id")["rows"].first().sum()),
        "fold_count": int(per_fold["fold_id"].nunique()),
        "event_rate": float(
            per_fold.groupby("fold_id")["positives"].first().sum()
            / per_fold.groupby("fold_id")["rows"].first().sum()
        ),
        "policies": summarize(per_fold, policies),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    summary = run(parse_args())
    policies = summary["policies"]
    assert isinstance(policies, dict)
    for label, metrics in policies.items():
        print(
            f"{label:24s} rate={metrics['alert_rate']:.3f} prec={metrics['precision']:.3f} "
            f"recall={metrics['recall']:.3f} episodes={metrics['episode_recall']:.3f} "
            f"thr={metrics['threshold_mean']:.3f}±{metrics['threshold_std']:.3f}"
        )


if __name__ == "__main__":
    main()
