"""Generate a Markdown report for a Temporal Transformer trust experiment."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True, help="Training summary JSON.")
    parser.add_argument("--warning-eval", type=Path, required=True, help="Warning eval JSON.")
    parser.add_argument("--threshold-sweep", type=Path, required=True, help="Threshold sweep CSV.")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report output.")
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _dict_table(values: dict[str, object], *, keys: Sequence[str] | None = None) -> str:
    selected_keys = list(keys) if keys is not None else list(values.keys())
    lines = ["| Metric | Value |", "| --- | ---: |"]
    for key in selected_keys:
        if key in values and not isinstance(values[key], dict):
            lines.append(f"| `{key}` | {_format_value(values[key])} |")
    return "\n".join(lines)


def _config_block(title: str, config: dict[str, object]) -> str:
    return f"## {title}\n\n```json\n{json.dumps(config, indent=2)}\n```"


def select_sweep_candidate(
    sweep: pd.DataFrame,
    *,
    coverage_min: float,
    coverage_max: float,
    alert_rate_min: float = 0.0,
    sort_columns: Sequence[str],
    ascending: Sequence[bool],
) -> dict[str, object]:
    """Select one threshold policy from a coverage band."""

    candidates = sweep[(sweep["coverage"] >= coverage_min) & (sweep["coverage"] <= coverage_max)]
    if alert_rate_min > 0.0 and "alert_rate" in candidates.columns:
        alerting_candidates = candidates[candidates["alert_rate"] >= alert_rate_min]
        if not alerting_candidates.empty:
            candidates = alerting_candidates
    if candidates.empty:
        candidates = sweep
    available = [
        (column, is_ascending)
        for column, is_ascending in zip(sort_columns, ascending, strict=True)
        if column in candidates.columns
    ]
    if not available:
        return candidates.iloc[0].to_dict()
    ranked = candidates.sort_values(
        [column for column, _ in available],
        ascending=[is_ascending for _, is_ascending in available],
    )
    return ranked.iloc[0].to_dict()


def _candidate_table(candidates: dict[str, dict[str, object]]) -> str:
    keys = [
        "trust_score_method",
        "watch_threshold_ratio",
        "trust_threshold",
        "uncertainty_threshold",
        "uncertainty_penalty",
        "coverage",
        "selective_risk",
        "alert_or_watch_selective_risk",
        "alert_precision",
        "alert_false_alarm_rate",
        "watch_rate",
        "no_alert_rate",
    ]
    lines = ["| Policy | " + " | ".join(keys) + " |", "| --- | " + " | ".join(["---:"] * len(keys)) + " |"]
    for name, row in candidates.items():
        values = [_format_value(row.get(key, "")) for key in keys]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def _metric_summary_table(summary: dict[str, object]) -> str:
    sections = summary.get("summary", {})
    if not isinstance(sections, dict):
        return ""
    metrics = ["auc", "f1", "brier_score", "ece", "precision", "recall"]
    lines = ["| Metric | Raw | Calibrated | Tuned |", "| --- | ---: | ---: | ---: |"]
    for metric in metrics:
        row = []
        for section in ("raw", "calibrated", "tuned"):
            values = sections.get(section, {})
            value = values.get(metric, "") if isinstance(values, dict) else ""
            row.append(_format_value(value))
        lines.append(f"| `{metric}` | " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_report(
    summary: dict[str, object],
    warning_eval: dict[str, object],
    threshold_sweep: pd.DataFrame,
) -> str:
    """Render a Markdown experiment report."""

    overall = warning_eval.get("overall", {})
    if not isinstance(overall, dict):
        overall = {}
    candidates = {
        "balanced": select_sweep_candidate(
            threshold_sweep,
            coverage_min=0.25,
            coverage_max=0.50,
            alert_rate_min=0.005,
            sort_columns=("selective_risk", "alert_false_alarm_rate"),
            ascending=(True, True),
        ),
        "conservative": select_sweep_candidate(
            threshold_sweep,
            coverage_min=0.10,
            coverage_max=0.30,
            alert_rate_min=0.005,
            sort_columns=("alert_precision", "alert_false_alarm_rate"),
            ascending=(False, True),
        ),
        "broad": select_sweep_candidate(
            threshold_sweep,
            coverage_min=0.50,
            coverage_max=0.70,
            alert_rate_min=0.005,
            sort_columns=("alert_miss_rate", "selective_risk"),
            ascending=(True, True),
        ),
    }

    sections = [
        "# Temporal Transformer Trust Experiment Report",
        "## Overview",
        (
            "This report summarizes a Temporal Transformer risk model with "
            "calibration, uncertainty scoring, trust scoring, and warning-level decisions."
        ),
        _config_block("Model Config", summary.get("model_config", {})),
        _config_block("Training Config", summary.get("training_config", {})),
        _config_block("Trust Config", summary.get("trust_config", {})),
        "## Raw / Calibrated / Tuned Metrics",
        _metric_summary_table(summary),
        "## Warning-Level Distribution",
        _dict_table(
            overall,
            keys=(
                "alert_count",
                "watch_count",
                "abstain_count",
                "no_alert_count",
                "alert_rate",
                "watch_rate",
                "abstain_rate",
                "no_alert_rate",
            ),
        ),
        "## Warning Quality",
        _dict_table(
            overall,
            keys=(
                "alert_precision",
                "alert_recall",
                "alert_false_alarm_rate",
                "alert_miss_rate",
                "coverage",
                "selective_risk",
                "alert_only_selective_risk",
                "alert_or_watch_selective_risk",
            ),
        ),
        "## Threshold Sweep Candidates",
        _candidate_table(candidates),
        "## Observations",
        "- Interpret `alert` as the strongest warning and `watch` as lower-intensity monitoring.",
        (
            "- The current subtractive trust score is overly conservative under entropy "
            "uncertainty when trust thresholds are high; compare multiplicative trust scoring "
            "before dashboard presentation."
        ),
        "- Use threshold sweep candidates to choose a policy before dashboard presentation.",
        "- Compare calibrated metrics against raw metrics before making warning policy claims.",
        "## Limitations",
        "- This is a risk-event warning experiment, not investment advice or an automated trading system.",
        "- Threshold policies should be validated across more folds and market regimes.",
        "- Watch decisions are weaker than alerts and should not be interpreted as positive predictions without context.",
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def run_report(args: argparse.Namespace) -> str:
    summary = _read_json(args.summary)
    warning_eval = _read_json(args.warning_eval)
    threshold_sweep = pd.read_csv(args.threshold_sweep)
    report = render_report(summary, warning_eval, threshold_sweep)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    report = run_report(args)
    print(report)


if __name__ == "__main__":
    main()
