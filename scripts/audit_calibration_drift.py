"""Evaluate a heuristic calibration-drift gate over experiment folds."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

from tsi.evaluation.drift import CalibrationDriftConfig, assess_calibration_drift


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-rate-delta-threshold", type=float, default=0.10)
    parser.add_argument("--ece-increase-threshold", type=float, default=0.05)
    parser.add_argument("--brier-increase-threshold", type=float, default=0.05)
    parser.add_argument("--abstain-signal-count", type=int, default=2)
    parser.add_argument("--degraded-trust-multiplier", type=float, default=0.5)
    return parser.parse_args(argv)


def build_drift_report(
    summary: dict[str, Any],
    *,
    config: CalibrationDriftConfig | None = None,
) -> dict[str, object]:
    """Build fold-level drift decisions and an abstention coverage summary."""

    folds = summary.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError("summary must contain a non-empty folds list")
    config = config or CalibrationDriftConfig()
    fold_reports: list[dict[str, object]] = []
    total_rows = 0
    selected_rows = 0
    selected_positive_rows = 0.0
    for fold in folds:
        if not isinstance(fold, dict):
            raise ValueError("every fold must be a JSON object")
        threshold_selection = fold.get("threshold_selection")
        if not isinstance(threshold_selection, dict):
            raise ValueError(f"fold {fold.get('fold_id')!r} has no threshold_selection")
        calibration_metrics = threshold_selection.get("calibration_metrics")
        recent_metrics = fold.get("calibrated_metrics")
        if not isinstance(calibration_metrics, dict) or not isinstance(recent_metrics, dict):
            raise ValueError(f"fold {fold.get('fold_id')!r} has incomplete metric sections")
        assessment = assess_calibration_drift(
            calibration_metrics,
            recent_metrics,
            config=config,
        )
        test_rows = int(fold.get("test_rows", 0))
        positive_rate = float(recent_metrics.get("positive_rate", 0.0))
        total_rows += test_rows
        if not assessment.abstain:
            selected_rows += test_rows
            selected_positive_rows += test_rows * positive_rate
        fold_reports.append(
            {
                "fold_id": fold.get("fold_id"),
                "test_rows": test_rows,
                "test_positive_rate": positive_rate,
                **assessment.as_dict(),
            }
        )

    abstained_rows = total_rows - selected_rows
    return {
        "summary_input": summary.get("input", ""),
        "model_type": summary.get("model_type", ""),
        "fold_count": len(fold_reports),
        "config": {
            "event_rate_delta_threshold": config.event_rate_delta_threshold,
            "ece_increase_threshold": config.ece_increase_threshold,
            "brier_increase_threshold": config.brier_increase_threshold,
            "abstain_signal_count": config.abstain_signal_count,
            "degraded_trust_multiplier": config.degraded_trust_multiplier,
        },
        "folds": fold_reports,
        "aggregate": {
            "degraded_fold_count": sum(bool(fold["degraded"]) for fold in fold_reports),
            "abstain_fold_count": sum(bool(fold["abstain"]) for fold in fold_reports),
            "degraded_fold_ids": [fold["fold_id"] for fold in fold_reports if fold["degraded"]],
            "abstain_fold_ids": [fold["fold_id"] for fold in fold_reports if fold["abstain"]],
            "total_rows": total_rows,
            "selected_rows": selected_rows,
            "abstained_rows": abstained_rows,
            "coverage": selected_rows / total_rows if total_rows else 0.0,
            "selective_risk": (
                selected_positive_rows / selected_rows if selected_rows else None
            ),
        },
        "limitations": [
            "Thresholds are engineering heuristics, not a statistically calibrated detector.",
            "The gate is evaluated at fold level and abstains a whole fold in this audit.",
            "Selective risk here is the observed positive-label rate among non-abstained folds.",
            "Serving integration and future rolling-window validation remain open work.",
        ],
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    summary = _read_json(args.summary)
    config = CalibrationDriftConfig(
        event_rate_delta_threshold=args.event_rate_delta_threshold,
        ece_increase_threshold=args.ece_increase_threshold,
        brier_increase_threshold=args.brier_increase_threshold,
        abstain_signal_count=args.abstain_signal_count,
        degraded_trust_multiplier=args.degraded_trust_multiplier,
    )
    report = build_drift_report(summary, config=config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def main() -> None:
    args = parse_args()
    print(json.dumps(run(args), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
