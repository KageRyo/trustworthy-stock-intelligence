"""Compare current-universe and point-in-time benchmark artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from tsi.evaluation.universe_comparison import (
    build_universe_comparison_report,
    render_universe_comparison_report,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--comparison-summary", type=Path, required=True)
    parser.add_argument("--baseline-predictions", type=Path, default=None)
    parser.add_argument("--comparison-predictions", type=Path, default=None)
    parser.add_argument(
        "--baseline-membership",
        type=Path,
        default=None,
        help="Optional local membership CSV used for aggregate member deltas only.",
    )
    parser.add_argument(
        "--comparison-membership",
        type=Path,
        default=None,
        help="Optional local membership CSV used for aggregate member deltas only.",
    )
    parser.add_argument("--baseline-coverage-audit", type=Path, default=None)
    parser.add_argument("--comparison-coverage-audit", type=Path, default=None)
    parser.add_argument("--baseline-run-id", default=None)
    parser.add_argument("--comparison-run-id", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resamples", type=int, default=4_000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--output", type=Path, required=True, help="JSON report path.")
    parser.add_argument("--report", type=Path, required=True, help="Markdown report path.")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    report = build_universe_comparison_report(
        args.baseline_summary,
        args.comparison_summary,
        baseline_predictions_path=args.baseline_predictions,
        comparison_predictions_path=args.comparison_predictions,
        baseline_membership_path=args.baseline_membership,
        comparison_membership_path=args.comparison_membership,
        baseline_coverage_audit_path=args.baseline_coverage_audit,
        comparison_coverage_audit_path=args.comparison_coverage_audit,
        baseline_run_id=args.baseline_run_id,
        comparison_run_id=args.comparison_run_id,
        seed=args.seed,
        resamples=args.resamples,
        confidence=args.confidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_universe_comparison_report(report), encoding="utf-8")
    return report


def main() -> None:
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
