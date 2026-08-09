"""Compute paired fold-level intervals between two model summary artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

from scripts.compare_model_families import _load_artifact, build_model_family_report
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--comparison-summary", type=Path, required=True)
    parser.add_argument("--section", choices=["prior", "raw", "calibrated", "tuned"], default="calibrated")
    parser.add_argument("--metrics", nargs="+", default=list(DEFAULT_METRICS))
    parser.add_argument("--resamples", type=int, default=4_000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def build_report(
    baseline_summary_path: Path,
    comparison_summary_path: Path,
    *,
    section: str,
    metrics: Sequence[str],
    resamples: int,
    confidence: float,
    seed: int,
) -> dict[str, object]:
    """Verify shared sample keys and calculate paired model deltas."""

    comparison_audit = build_model_family_report([baseline_summary_path, comparison_summary_path])
    baseline = _load_artifact(baseline_summary_path)["summary"]
    comparison = _load_artifact(comparison_summary_path)["summary"]
    return {
        "baseline_model": baseline.get("model_type", "unknown"),
        "comparison_model": comparison.get("model_type", "unknown"),
        "section": section,
        "protocol": comparison_audit["protocol"],
        "sample_key_audit": comparison_audit["sample_key_audit"],
        "statistics": paired_fold_metric_intervals(
            _section_folds(baseline, section),
            _section_folds(comparison, section),
            metrics=metrics,
            resamples=resamples,
            confidence=confidence,
            seed=seed,
        ),
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    report = build_report(
        args.baseline_summary,
        args.comparison_summary,
        section=args.section,
        metrics=args.metrics,
        resamples=args.resamples,
        confidence=args.confidence,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def _section_folds(summary: dict[str, Any], section: str) -> list[dict[str, object]]:
    folds = summary.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError("summary must contain a non-empty folds list")
    selected: list[dict[str, object]] = []
    for fold in folds:
        if not isinstance(fold, dict):
            raise ValueError("every fold must be a JSON object")
        metrics = fold.get(f"{section}_metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"fold {fold.get('fold_id')!r} has no {section}_metrics")
        selected.append({"fold_id": fold.get("fold_id"), **metrics})
    return selected


def main() -> None:
    args = parse_args()
    print(json.dumps(run(args), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
