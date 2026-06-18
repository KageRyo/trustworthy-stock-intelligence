"""Generate a Markdown comparison report for trust experiment runs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd


WARNING_METRICS = (
    "alert_rate",
    "watch_rate",
    "no_alert_rate",
    "alert_precision",
    "alert_recall",
    "alert_false_alarm_rate",
    "coverage",
    "selective_risk",
)
MODEL_METRICS = ("auc", "brier_score", "ece", "precision", "recall", "f1")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="Run directories to compare.")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report output path.")
    return parser.parse_args(argv)


def load_run_metrics(run_dir: Path) -> dict[str, Any]:
    """Load a compact comparison row from one experiment run directory."""

    summary = _read_json_if_exists(run_dir / "summary.json")
    warning_eval = _read_json_if_exists(run_dir / "warning_eval.json")
    diagnostics = _read_json_if_exists(run_dir / "diagnostics.json")

    trust_config = _as_dict(summary.get("trust_config"))
    summary_sections = _as_dict(summary.get("summary"))
    calibrated_metrics = _as_dict(summary_sections.get("calibrated"))
    tuned_metrics = _as_dict(summary_sections.get("tuned"))
    overall = _as_dict(warning_eval.get("overall"))
    trust_score_method = trust_config.get("trust_score_method") or _infer_trust_score_method(run_dir.name)

    row: dict[str, Any] = {
        "run": run_dir.name,
        "path": str(run_dir),
        "trust_score_method": trust_score_method,
        "calibration_method": trust_config.get("calibration_method", ""),
        "uncertainty_method": trust_config.get("uncertainty_method", ""),
        "row_count": _first_present(
            warning_eval.get("row_count"),
            diagnostics.get("row_count"),
            summary.get("rows_after_filtering"),
        ),
    }
    for metric in WARNING_METRICS:
        source_key = metric
        if metric == "alert_false_alarm_rate":
            source_key = "alert_false_alarm_rate"
        row[metric] = overall.get(source_key, "")
    for metric in MODEL_METRICS:
        row[f"calibrated_{metric}"] = calibrated_metrics.get(metric, "")
        row[f"tuned_{metric}"] = tuned_metrics.get(metric, "")
    return row


def build_comparison_frame(run_dirs: Sequence[Path]) -> pd.DataFrame:
    """Build comparison rows for the provided run directories."""

    if not run_dirs:
        raise ValueError("at least one run directory is required")
    rows = [load_run_metrics(run_dir) for run_dir in run_dirs]
    return pd.DataFrame(rows)


def render_comparison_report(frame: pd.DataFrame) -> str:
    """Render a conservative trust experiment comparison report."""

    display_columns = [
        "run",
        "trust_score_method",
        "alert_rate",
        "watch_rate",
        "no_alert_rate",
        "alert_precision",
        "alert_recall",
        "alert_false_alarm_rate",
        "coverage",
        "selective_risk",
        "calibrated_ece",
        "calibrated_brier_score",
        "calibrated_auc",
    ]
    table = _markdown_table(frame, display_columns)
    notes = _comparison_notes(frame)
    return (
        "# Experiment Comparison Report\n\n"
        "This report compares risk-warning experiment runs as a trust-aware conservative "
        "alerting demo. It should not be read as an investment recommendation, a precise "
        "price forecast, or an automated trading result.\n\n"
        "## Runs\n\n"
        f"{table}\n\n"
        "## Interpretation\n\n"
        f"{notes}\n"
    )


def run_comparison(args: argparse.Namespace) -> str:
    frame = build_comparison_frame(args.runs)
    report = render_comparison_report(frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_present(*values: object) -> object:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _infer_trust_score_method(run_name: str) -> str:
    if "multiplicative" in run_name:
        return "multiplicative"
    if "subtractive" in run_name or "entropy" in run_name:
        return "subtractive"
    return ""


def _format_cell(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    available_columns = [column for column in columns if column in frame.columns]
    lines = [
        "| " + " | ".join(available_columns) + " |",
        "| " + " | ".join(["---"] * len(available_columns)) + " |",
    ]
    for _, row in frame.loc[:, available_columns].iterrows():
        lines.append("| " + " | ".join(_format_cell(row[column]) for column in available_columns) + " |")
    return "\n".join(lines)


def _comparison_notes(frame: pd.DataFrame) -> str:
    lines = [
        "- Prefer language such as `trust-aware conservative risk alerting demo` when "
        "describing these runs.",
        "- Compare alert precision, false alarm rate, and coverage together; a low alert "
        "rate can be useful for triage but usually implies low recall.",
        "- Use calibrated ECE and Brier score to discuss reliability, not directional "
        "trading performance.",
    ]
    if "alert_rate" in frame.columns and len(frame) >= 2:
        alert_rates = pd.to_numeric(frame["alert_rate"], errors="coerce")
        if alert_rates.min(skipna=True) == 0.0 and alert_rates.max(skipna=True) > 0.0:
            lines.append(
                "- In these runs, at least one policy emitted no alerts while another emitted "
                "a non-zero alert rate; this supports the subtractive-versus-multiplicative "
                "trust-score comparison story."
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    report = run_comparison(args)
    print(report)


if __name__ == "__main__":
    main()
