"""Add paired fold-level confidence intervals to a model summary artifact."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

from tsi.evaluation.statistics import paired_fold_metric_intervals


DEFAULT_METRICS = (
    "auc",
    "pr_auc",
    "brier_score",
    "ece",
    "precision",
    "recall",
    "f1",
    "false_alarm_rate",
    "false_discovery_rate",
)
MODEL_SECTIONS = ("prior", "raw", "calibrated", "tuned")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True, help="Training summary JSON.")
    parser.add_argument("--baseline", choices=MODEL_SECTIONS, required=True)
    parser.add_argument("--comparison", choices=MODEL_SECTIONS, required=True)
    parser.add_argument("--metrics", nargs="+", default=list(DEFAULT_METRICS))
    parser.add_argument("--resamples", type=int, default=4_000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def build_bootstrap_report(
    summary: dict[str, Any],
    *,
    baseline: str,
    comparison: str,
    metrics: Sequence[str],
    resamples: int,
    confidence: float,
    seed: int,
) -> dict[str, object]:
    """Build a JSON report from fold metrics without using test rows as units."""

    folds = summary.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError("summary must contain a non-empty folds list")
    baseline_folds = _section_folds(folds, baseline)
    comparison_folds = _section_folds(folds, comparison)
    return {
        "summary_input": summary.get("input", ""),
        "model_type": summary.get("model_type", ""),
        "horizon": summary.get("horizon"),
        "purge_size": summary.get("purge_size"),
        "calibration_method": summary.get("calibration_method", ""),
        "threshold_objective": summary.get("threshold_objective", ""),
        "baseline": baseline,
        "comparison": comparison,
        "statistics": paired_fold_metric_intervals(
            baseline_folds,
            comparison_folds,
            metrics=metrics,
            resamples=resamples,
            confidence=confidence,
            seed=seed,
        ),
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    summary = _read_json(args.summary)
    report = build_bootstrap_report(
        summary,
        baseline=args.baseline,
        comparison=args.comparison,
        metrics=args.metrics,
        resamples=args.resamples,
        confidence=args.confidence,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def _section_folds(folds: list[object], section: str) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for fold in folds:
        if not isinstance(fold, dict):
            raise ValueError("every fold must be a JSON object")
        metrics = fold.get(f"{section}_metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"fold {fold.get('fold_id')!r} has no {section}_metrics")
        selected.append({"fold_id": fold.get("fold_id"), **metrics})
    return selected


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
