"""Compare named feature sets with purged walk-forward evaluation.

Every feature set is scored on identical rows and folds: rows missing any column
of any compared set are dropped before splitting. Each fold fits the logistic
baseline and probability calibration per set on its train and calibration
windows only, picks the serving alert and watch thresholds on the calibration
window, and scores the later test window for ranking (AUC, PR-AUC), calibration
(Brier, ECE), and alert quality. Comparisons against the baseline set use paired
fold-level bootstrap intervals.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json

import numpy as np
import pandas as pd

from scripts.evaluate_alert_policies import drawdown_episodes, policy_test_metrics
from scripts.walk_forward_experiment import (
    FoldFrames,
    add_walk_forward_arguments,
    fit_calibrated_logistic,
    load_walk_forward_folds,
    resolve_output_dir,
    walk_forward_protocol,
)
from tsi.data.csv import file_sha256
from tsi.evaluation.metrics import classification_metrics
from tsi.evaluation.statistics import paired_fold_metric_intervals
from tsi.features.sets import FEATURE_SETS, resolve_feature_set
from tsi.labeling.warning_level import (
    AlertPolicy,
    parse_alert_policy,
    select_alert_threshold_by_policy,
)
from tsi.trust.calibration import CalibrationMethod

DEFAULT_FEATURE_SETS = ",".join(FEATURE_SETS)
PAIRED_METRICS = (
    "auc",
    "pr_auc",
    "brier_score",
    "brier_skill_score",
    "ece",
    "alert_precision",
    "alert_recall",
    "watch_recall",
)
FOLD_MEDIAN_METRICS = ("auc", "pr_auc", "brier_skill_score", "ece", "alert_precision")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_walk_forward_arguments(parser, feature_set_argument=False)
    parser.add_argument("--feature-sets", default=DEFAULT_FEATURE_SETS)
    parser.add_argument("--baseline-feature-set", default="technical")
    parser.add_argument(
        "--extra-pairs",
        default="",
        help="Extra paired comparisons as comparison:baseline items separated by commas.",
    )
    parser.add_argument("--alert-policy", default="alert_rate:0.05")
    parser.add_argument("--watch-policy", default="alert_rate:0.2")
    parser.add_argument("--min-alerts", type=int, default=20)
    parser.add_argument("--bootstrap-resamples", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def parse_feature_sets(text: str, *, baseline: str) -> dict[str, list[str]]:
    """Resolve comma-separated set names, always including the baseline first."""

    names = [name.strip() for name in text.split(",") if name.strip()]
    ordered = [baseline, *(name for name in names if name != baseline)]
    return {name: resolve_feature_set(name) for name in dict.fromkeys(ordered)}


def parse_pairs(
    text: str, feature_sets: dict[str, list[str]], *, baseline: str
) -> list[tuple[str, str]]:
    """Every set versus ``baseline`` plus ``comparison:baseline`` extras, without repeats."""

    pairs = [(name, baseline) for name in feature_sets if name != baseline]
    for item in (item.strip() for item in text.split(",") if item.strip()):
        comparison, _, reference = item.partition(":")
        if comparison not in feature_sets or reference not in feature_sets:
            raise ValueError(f"Paired comparison {item!r} must name two compared feature sets")
        if comparison == reference:
            raise ValueError(f"Paired comparison {item!r} compares a set with itself")
        pairs.append((comparison, reference))
    return list(dict.fromkeys(pairs))


def union_columns(feature_sets: dict[str, list[str]]) -> list[str]:
    return list(dict.fromkeys(column for columns in feature_sets.values() for column in columns))


def score_probabilities(
    item: FoldFrames,
    calibration_probabilities: np.ndarray,
    test_probabilities: np.ndarray,
    *,
    reference_labels: np.ndarray,
    alert_policy: AlertPolicy,
    watch_policy: AlertPolicy,
) -> dict[str, float]:
    """Score calibrated test probabilities with thresholds picked on the calibration window.

    Brier skill is measured against a constant forecast at the ``reference_labels`` event rate.
    """

    calibration_labels = item.calibration["risk_label"].to_numpy()
    test_labels = item.test["risk_label"].to_numpy()
    metrics = classification_metrics(test_labels, test_probabilities)
    prior_brier = float(np.mean((reference_labels.mean() - test_labels) ** 2))
    episodes = drawdown_episodes(item.test).to_numpy()
    tickers = int(item.test["ticker"].nunique())
    dates = int(item.test["date"].nunique())
    alert_threshold = select_alert_threshold_by_policy(
        calibration_labels, calibration_probabilities, alert_policy
    ).threshold
    watch_threshold = select_alert_threshold_by_policy(
        calibration_labels, calibration_probabilities, watch_policy
    ).threshold
    alert = policy_test_metrics(
        test_labels, test_probabilities >= alert_threshold, episodes, tickers=tickers, dates=dates
    )
    watch = policy_test_metrics(
        test_labels,
        test_probabilities >= min(alert_threshold, watch_threshold),
        episodes,
        tickers=tickers,
        dates=dates,
    )
    return {
        "auc": metrics["auc"],
        "pr_auc": metrics["pr_auc"],
        "brier_score": metrics["brier_score"],
        "brier_skill_score": 1.0 - metrics["brier_score"] / prior_brier,
        "ece": metrics["ece"],
        "alert_threshold": alert_threshold,
        "alerts": alert["alerts"],
        "alert_rate": alert["alert_rate"],
        "alert_precision": alert["precision"],
        "alert_recall": alert["recall"],
        "alert_episode_recall": alert["episode_recall"],
        "watch_rate": watch["alert_rate"],
        "watch_recall": watch["recall"],
        "watch_episode_recall": watch["episode_recall"],
    }


def score_fold(
    item: FoldFrames,
    feature_columns: Sequence[str],
    *,
    calibration_method: CalibrationMethod,
    alert_policy: AlertPolicy,
    watch_policy: AlertPolicy,
) -> tuple[dict[str, float], np.ndarray]:
    """Return test metrics and standardized logistic coefficients for one fold and set."""

    fit = fit_calibrated_logistic(
        item.train,
        item.calibration,
        item.test,
        feature_columns=feature_columns,
        calibration_method=calibration_method,
    )
    row = score_probabilities(
        item,
        fit.calibration_probabilities,
        fit.test_probabilities,
        reference_labels=item.train["risk_label"].to_numpy(),
        alert_policy=alert_policy,
        watch_policy=watch_policy,
    )
    coefficients = fit.model.pipeline.named_steps["classifier"].coef_[0]
    return row, coefficients


def summarize_set(rows: pd.DataFrame) -> dict[str, float]:
    """Pool alert counts over test rows; ranking and calibration metrics are fold means."""

    alerts = rows["alerts"].sum()
    positives = rows["positives"].sum()
    true_positives = (rows["alert_precision"].fillna(0.0) * rows["alerts"]).sum()
    summary = {
        "auc_mean": float(rows["auc"].mean()),
        "pr_auc_mean": float(rows["pr_auc"].mean()),
        "brier_score_mean": float(rows["brier_score"].mean()),
        "brier_skill_score_mean": float(rows["brier_skill_score"].mean()),
        "ece_mean": float(rows["ece"].mean()),
        "alert_rate": float(alerts / rows["rows"].sum()),
        "alert_precision": float(true_positives / alerts) if alerts else float("nan"),
        "alert_recall": float(true_positives / positives) if positives else float("nan"),
        "alert_episode_recall": float(rows["alert_episode_recall"].mean()),
        "watch_rate": float((rows["watch_rate"] * rows["rows"]).sum() / rows["rows"].sum()),
        "watch_recall": (
            float((rows["watch_recall"] * rows["positives"]).sum() / positives)
            if positives
            else float("nan")
        ),
    }
    for metric in FOLD_MEDIAN_METRICS:
        summary[f"fold_median_{metric}"] = float(rows[metric].median())
    return summary


def compare_to_baseline(
    per_fold: pd.DataFrame,
    *,
    baseline: str,
    comparison: str,
    resamples: int,
    seed: int,
    group_column: str = "feature_set",
) -> dict[str, object]:
    """Paired fold bootstrap deltas (comparison - baseline) plus fold win rates."""

    def folds(name: str) -> list[dict[str, object]]:
        rows = per_fold[per_fold[group_column] == name].sort_values("fold_id")
        return rows[["fold_id", *PAIRED_METRICS]].to_dict("records")

    baseline_rows = per_fold[per_fold[group_column] == baseline].set_index("fold_id")
    comparison_rows = per_fold[per_fold[group_column] == comparison].set_index("fold_id")
    report = paired_fold_metric_intervals(
        folds(baseline), folds(comparison), metrics=PAIRED_METRICS, seed=seed, resamples=resamples
    )
    report["fold_win_rate"] = {
        metric: float((comparison_rows[metric] > baseline_rows[metric]).mean())
        for metric in ("auc", "pr_auc", "brier_skill_score", "alert_precision")
    }
    return report


def run(args: argparse.Namespace) -> dict[str, object]:
    output_dir = resolve_output_dir(args.output_dir, root=args.output_root)
    feature_sets = parse_feature_sets(args.feature_sets, baseline=args.baseline_feature_set)
    alert_policy = parse_alert_policy(args.alert_policy, min_alerts=args.min_alerts)
    watch_policy = parse_alert_policy(args.watch_policy, min_alerts=args.min_alerts)
    pairs = parse_pairs(args.extra_pairs, feature_sets, baseline=args.baseline_feature_set)
    walk_forward = load_walk_forward_folds(args, feature_columns=union_columns(feature_sets))

    fold_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    for item in walk_forward.folds:
        for name, columns in feature_sets.items():
            metrics, coefficients = score_fold(
                item,
                columns,
                calibration_method=args.calibration_method,
                alert_policy=alert_policy,
                watch_policy=watch_policy,
            )
            fold_rows.append(
                {
                    "fold_id": item.fold.fold_id,
                    "test_start": str(item.fold.test_dates[0].date()),
                    "feature_set": name,
                    "rows": float(len(item.test)),
                    "positives": float(item.test["risk_label"].sum()),
                    **metrics,
                }
            )
            coefficient_rows.extend(
                {"feature_set": name, "feature": column, "coefficient": float(value)}
                for column, value in zip(columns, coefficients, strict=True)
            )
    per_fold = pd.DataFrame(fold_rows)
    coefficients = (
        pd.DataFrame(coefficient_rows)
        .groupby(["feature_set", "feature"], sort=False)["coefficient"]
        .agg(["mean", "std"])
        .reset_index()
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    per_fold.to_csv(output_dir / "per_fold.csv", index=False)
    coefficients.to_csv(output_dir / "coefficients.csv", index=False)
    baseline = args.baseline_feature_set
    first_set = per_fold[per_fold["feature_set"] == baseline]
    summary = {
        "input": str(args.input),
        "input_sha256": file_sha256(args.input),
        "protocol": walk_forward_protocol(
            args,
            walk_forward,
            feature_sets=feature_sets,
            baseline_feature_set=baseline,
            alert_policy=alert_policy.label,
            watch_policy=watch_policy.label,
            min_alerts=args.min_alerts,
        ),
        "rows": int(first_set["rows"].sum()),
        "fold_count": int(first_set["fold_id"].nunique()),
        "event_rate": float(first_set["positives"].sum() / first_set["rows"].sum()),
        "feature_sets": {
            name: summarize_set(per_fold[per_fold["feature_set"] == name]) for name in feature_sets
        },
        "paired_comparisons": {
            f"{comparison} vs {reference}": compare_to_baseline(
                per_fold,
                baseline=reference,
                comparison=comparison,
                resamples=args.bootstrap_resamples,
                seed=args.seed,
            )
            for comparison, reference in pairs
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    summary = run(parse_args())
    sets = summary["feature_sets"]
    assert isinstance(sets, dict)
    for name, metrics in sets.items():
        print(
            f"{name:24s} AUC={metrics['auc_mean']:.4f} PR-AUC={metrics['pr_auc_mean']:.4f} "
            f"BSS={metrics['brier_skill_score_mean']:.4f} ECE={metrics['ece_mean']:.4f} "
            f"alert prec={metrics['alert_precision']:.3f} recall={metrics['alert_recall']:.3f} "
            f"watch recall={metrics['watch_recall']:.3f}"
        )


if __name__ == "__main__":
    main()
