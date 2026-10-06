"""Compare trust signals with walk-forward selective-prediction evaluation.

For each purged walk-forward fold this fits the logistic baseline, Platt or isotonic
calibration, and the reliability assessor on train/calibration rows only, then
scores the later test rows. A useful trust signal should improve retained-subset
quality as coverage shrinks and make high-trust alerts more precise than
low-trust alerts.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.train import prepare_training_frame
from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.data.split import build_walk_forward_splits
from tsi.evaluation.selective import risk_coverage_curve, selective_summary
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS
from tsi.labeling.warning_level import select_alert_threshold
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import CalibrationMethod, fit_probability_calibrator
from tsi.trust.reliability import ReliabilityAssessor, ReliabilityConfig
from tsi.trust.trust_score import (
    compute_reliability_trust,
    compute_trust_score,
    data_quality_scores,
)
from tsi.trust.uncertainty import binary_entropy_uncertainty

CONFIDENCE_SIGNALS = (
    "random",
    "legacy_trust",
    "legacy_entropy_confidence",
    "disagreement_confidence",
    "novelty_confidence",
    "epistemic_trust",
)
ALERT_GATE_THRESHOLDS = (0.05, 0.1, 0.2, 0.3)
ABSTAIN_UNCERTAINTY_THRESHOLDS = (0.8, 0.9)


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
    parser.add_argument("--n-members", type=int, default=10)
    parser.add_argument("--conformal-alpha", type=float, default=0.1)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args(argv)


def score_fold(
    train_frame: pd.DataFrame,
    calibration_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    *,
    calibration_method: CalibrationMethod,
    train_size: int,
    config: ReliabilityConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Return test rows with calibrated probabilities and every confidence signal."""

    train_features = train_frame[DEFAULT_FEATURE_COLUMNS].to_numpy()
    calibration_features = calibration_frame[DEFAULT_FEATURE_COLUMNS].to_numpy()
    test_features = test_frame[DEFAULT_FEATURE_COLUMNS].to_numpy()
    train_labels = train_frame["risk_label"].to_numpy()
    calibration_labels = calibration_frame["risk_label"].to_numpy()

    model = LogisticRiskModel().fit(train_features, train_labels)
    raw_calibration = model.predict_proba(calibration_features)
    calibrator = fit_probability_calibrator(
        raw_calibration, calibration_labels, method=calibration_method
    )
    calibrated_calibration = calibrator.predict(raw_calibration)
    calibrated_test = calibrator.predict(model.predict_proba(test_features))
    alert_threshold = select_alert_threshold(
        calibration_labels, calibrated_calibration, objective="f1"
    ).threshold

    assessor = ReliabilityAssessor(config).fit(
        train_features=train_features,
        train_labels=train_labels,
        train_groups=pd.to_datetime(train_frame["date"]).to_numpy(),
        calibration_features=calibration_features,
        calibration_labels=calibration_labels,
        calibrated_calibration_probabilities=calibrated_calibration,
        calibrator=calibrator,
    )
    history_rows = test_frame["ticker"].map(train_frame["ticker"].value_counts()).fillna(0)
    quality = data_quality_scores(
        history_rows=history_rows.to_numpy(),
        required_history_rows=train_size,
        stale=np.zeros(len(test_frame), dtype=bool),
    )
    scores = assessor.score(
        test_features,
        calibrated_probabilities=calibrated_test,
        data_quality=quality,
    )
    entropy = binary_entropy_uncertainty(calibrated_test)
    scored = test_frame.loc[:, ["date", "ticker", "risk_label"]].reset_index(drop=True)
    scored = scored.assign(
        calibrated_risk_probability=calibrated_test,
        alert_threshold=alert_threshold,
        random=rng.random(len(test_frame)),
        legacy_trust=compute_trust_score(
            calibrated_test, entropy, uncertainty_penalty=0.5, method="multiplicative"
        ),
        legacy_entropy_confidence=1.0 - entropy,
        disagreement_confidence=1.0 - scores.disagreement_percentile,
        novelty_confidence=1.0 - scores.novelty_percentile,
        epistemic_trust=compute_reliability_trust(
            epistemic_uncertainty=scores.uncertainty,
            data_quality=quality,
            epistemic_weight=1.0,
        ),
        served_trust=scores.trust,
        reliability_uncertainty=scores.uncertainty,
    )
    if scores.conformal_sets is not None:
        scored["conformal_contains_no_drawdown"] = scores.conformal_sets[:, 0]
        scored["conformal_contains_drawdown"] = scores.conformal_sets[:, 1]
    return scored


def alert_precision_split(scored: pd.DataFrame, signal: str) -> dict[str, float]:
    """Compare alert FDR above and below each fold's median confidence."""

    median = scored.groupby("fold_id")[signal].transform("median")
    alerts = scored["calibrated_risk_probability"] >= scored["alert_threshold"]
    result: dict[str, float] = {}
    for name, mask in {
        "high": scored[signal] > median,
        "low": scored[signal] <= median,
    }.items():
        selected = scored.loc[alerts & mask, "risk_label"]
        result[f"alerts_{name}_confidence"] = float(len(selected))
        result[f"alert_fdr_{name}_confidence"] = (
            float(1.0 - selected.mean()) if len(selected) else float("nan")
        )
    return result


def epistemic_alert_gate(scored: pd.DataFrame) -> list[dict[str, float]]:
    """Measure what happens if alerts require epistemic trust above a threshold."""

    alerts = scored["calibrated_risk_probability"] >= scored["alert_threshold"]
    positives = int((scored["risk_label"] == 1).sum())
    rows = []
    for threshold in ALERT_GATE_THRESHOLDS:
        kept = alerts & (scored["epistemic_trust"] >= threshold)
        blocked = alerts & ~kept
        rows.append(
            {
                "trust_threshold": threshold,
                "alerts_kept": float(kept.sum()),
                "alerts_blocked": float(blocked.sum()),
                "fdr_kept": _fdr(scored.loc[kept, "risk_label"]),
                "fdr_blocked": _fdr(scored.loc[blocked, "risk_label"]),
                "recall_kept": float((kept & (scored["risk_label"] == 1)).sum() / positives)
                if positives
                else float("nan"),
            }
        )
    return rows


def legacy_alert_gate(scored: pd.DataFrame, *, trust_threshold: float = 0.1) -> dict[str, float]:
    """Measure the previous serving rule: alert only when legacy trust passes 0.1."""

    alerts = scored["calibrated_risk_probability"] >= scored["alert_threshold"]
    gated = alerts & (scored["legacy_trust"] >= trust_threshold)
    positives = int((scored["risk_label"] == 1).sum())
    result: dict[str, float] = {"trust_threshold": trust_threshold}
    for name, mask in {"ungated": alerts, "gated": gated}.items():
        result[f"{name}_alert_rate"] = float(mask.mean())
        result[f"{name}_fdr"] = _fdr(scored.loc[mask, "risk_label"])
        result[f"{name}_recall"] = (
            float((mask & (scored["risk_label"] == 1)).sum() / positives)
            if positives
            else float("nan")
        )
    return result


def uncertainty_abstain(scored: pd.DataFrame, *, watch_ratio: float = 0.8) -> list[dict[str, float]]:
    """Compare observed event rates for below-watch rows that would abstain."""

    below_watch = scored["calibrated_risk_probability"] < watch_ratio * scored["alert_threshold"]
    rows = []
    for threshold in ABSTAIN_UNCERTAINTY_THRESHOLDS:
        abstain = below_watch & (scored["reliability_uncertainty"] >= threshold)
        no_alert = below_watch & ~abstain
        rows.append(
            {
                "uncertainty_threshold": threshold,
                "abstain_share": float(abstain.mean()),
                "abstain_event_rate": _mean(scored.loc[abstain, "risk_label"]),
                "abstain_mean_probability": _mean(
                    scored.loc[abstain, "calibrated_risk_probability"]
                ),
                "no_alert_event_rate": _mean(scored.loc[no_alert, "risk_label"]),
                "no_alert_mean_probability": _mean(
                    scored.loc[no_alert, "calibrated_risk_probability"]
                ),
            }
        )
    return rows


def _fdr(labels: pd.Series) -> float:
    return float(1.0 - labels.mean()) if len(labels) else float("nan")


def _mean(values: pd.Series) -> float:
    return float(values.mean()) if len(values) else float("nan")


def conformal_coverage(scored: pd.DataFrame) -> dict[str, float]:
    if "conformal_contains_drawdown" not in scored:
        return {}
    labels = scored["risk_label"].to_numpy()
    contains = np.where(
        labels == 1,
        scored["conformal_contains_drawdown"].to_numpy(),
        scored["conformal_contains_no_drawdown"].to_numpy(),
    )
    ambiguous = scored["conformal_contains_drawdown"] & scored["conformal_contains_no_drawdown"]
    return {
        "coverage_drawdown": float(contains[labels == 1].mean()),
        "coverage_no_drawdown": float(contains[labels == 0].mean()),
        "ambiguous_rate": float(ambiguous.mean()),
    }


def summarize(scored: pd.DataFrame) -> dict[str, object]:
    labels = scored["risk_label"].to_numpy()
    probabilities = scored["calibrated_risk_probability"].to_numpy()
    pooled: dict[str, dict[str, float]] = {}
    for signal in CONFIDENCE_SIGNALS:
        pooled[signal] = {
            **selective_summary(labels, probabilities, scored[signal].to_numpy()),
            **alert_precision_split(scored, signal),
        }

    per_fold = []
    for fold_id, fold in scored.groupby("fold_id"):
        row: dict[str, float] = {"fold_id": float(fold_id)}
        for signal in CONFIDENCE_SIGNALS:
            row[signal] = selective_summary(
                fold["risk_label"].to_numpy(),
                fold["calibrated_risk_probability"].to_numpy(),
                fold[signal].to_numpy(),
            )["mean_brier_skill_score"]
        per_fold.append(row)
    per_fold_frame = pd.DataFrame(per_fold)
    fold_win_rate = {
        f"epistemic_trust_beats_{signal}": float(
            (per_fold_frame["epistemic_trust"] > per_fold_frame[signal]).mean()
        )
        for signal in CONFIDENCE_SIGNALS
        if signal != "epistemic_trust"
    }
    trust_correlation = float(
        np.corrcoef(scored["epistemic_trust"], scored["calibrated_risk_probability"])[0, 1]
    )
    legacy_correlation = float(
        np.corrcoef(scored["legacy_trust"], scored["calibrated_risk_probability"])[0, 1]
    )
    return {
        "rows": int(len(scored)),
        "fold_count": int(scored["fold_id"].nunique()),
        "event_rate": float(labels.mean()),
        "pooled": pooled,
        "fold_mean_brier_skill_win_rate": fold_win_rate,
        "correlation_with_risk_probability": {
            "epistemic_trust": trust_correlation,
            "legacy_trust": legacy_correlation,
        },
        "epistemic_trust_quantiles": {
            str(q): float(scored["epistemic_trust"].quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)
        },
        "served_trust_mean": float(scored["served_trust"].mean()),
        "legacy_alert_gate": legacy_alert_gate(scored),
        "epistemic_alert_gate": epistemic_alert_gate(scored),
        "uncertainty_abstain": uncertainty_abstain(scored),
        "conformal": conformal_coverage(scored),
    }


def resolve_output_dir(output_dir: Path, *, root: Path) -> Path:
    """Resolve ``output_dir`` against ``root`` and reject paths that escape it."""

    base = root.resolve()
    resolved = (base / output_dir).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"--output-dir must stay inside {base}")
    return resolved


def run(args: argparse.Namespace) -> dict[str, object]:
    output_dir = resolve_output_dir(args.output_dir, root=args.output_root)
    ohlcv = read_ohlcv_csv(args.input)
    frame = prepare_training_frame(
        ohlcv, horizon=args.horizon, drawdown_threshold=args.drawdown_threshold
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

    config = ReliabilityConfig(
        n_members=args.n_members,
        random_state=args.random_state,
        conformal_alpha=args.conformal_alpha,
    )
    rng = np.random.default_rng(args.random_state)
    scored_folds: list[pd.DataFrame] = []
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
        scored = score_fold(
            train_frame,
            calibration_frame,
            test_frame,
            calibration_method=args.calibration_method,
            train_size=args.train_size,
            config=config,
            rng=rng,
        )
        scored_folds.append(scored.assign(fold_id=fold.fold_id))
    if not scored_folds:
        raise ValueError("No walk-forward fold had both classes in train and calibration windows")
    scored_all = pd.concat(scored_folds, ignore_index=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    curves = pd.concat(
        [
            risk_coverage_curve(
                scored_all["risk_label"].to_numpy(),
                scored_all["calibrated_risk_probability"].to_numpy(),
                scored_all[signal].to_numpy(),
            ).assign(signal=signal)
            for signal in CONFIDENCE_SIGNALS
        ],
        ignore_index=True,
    )
    curves.to_csv(output_dir / "risk_coverage.csv", index=False)
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
            "n_members": args.n_members,
            "conformal_alpha": args.conformal_alpha,
            "random_state": args.random_state,
            "skipped_folds": skipped,
        },
        **summarize(scored_all),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    summary = run(parse_args())
    pooled = summary["pooled"]
    assert isinstance(pooled, dict)
    for signal, metrics in pooled.items():
        print(
            f"{signal:28s} AURC={metrics['aurc_brier']:.5f} "
            f"BSS={metrics['mean_brier_skill_score']:.4f} "
            f"FDR high/low={metrics['alert_fdr_high_confidence']:.3f}/"
            f"{metrics['alert_fdr_low_confidence']:.3f}"
        )


if __name__ == "__main__":
    main()
