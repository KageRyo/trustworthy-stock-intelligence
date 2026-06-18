"""Compare baseline and Transformer model variants from experiment summaries."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd


VARIANTS = ("raw", "calibrated", "tuned")
MODEL_METRICS = ("auc", "brier_score", "ece", "precision", "recall", "f1")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="Run directories to compare.")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report output path.")
    return parser.parse_args(argv)


def build_variant_comparison_frame(run_dirs: Sequence[Path]) -> pd.DataFrame:
    """Build model-variant comparison rows from run directories or summary files."""

    if not run_dirs:
        raise ValueError("at least one run directory is required")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        rows.extend(load_variant_rows(run_dir))
    return pd.DataFrame(rows)


def load_variant_rows(run_dir: Path) -> list[dict[str, Any]]:
    """Load raw/calibrated/tuned and optional trust-decision rows for one run."""

    summary_path, warning_eval_path, run_name = _resolve_run_paths(run_dir)
    summary = _read_json(summary_path)
    warning_eval = _read_json_if_exists(warning_eval_path)
    model_name = _infer_model_name(summary)
    sections = _as_dict(summary.get("summary"))
    rows = []
    for variant in VARIANTS:
        metrics = _as_dict(sections.get(variant))
        if not metrics:
            continue
        rows.append(_metric_row(run_name, model_name, variant, metrics))

    overall = _as_dict(warning_eval.get("overall"))
    if overall:
        base_metrics = _as_dict(sections.get("tuned")) or _as_dict(sections.get("calibrated"))
        row = _metric_row(run_name, model_name, "trust_decision", base_metrics)
        row.update(
            {
                "alert_precision": overall.get("alert_precision", ""),
                "false_alarm_rate": overall.get("alert_false_alarm_rate", ""),
                "coverage": overall.get("coverage", ""),
            }
        )
        rows.append(row)
    return rows


def _resolve_run_paths(path: Path) -> tuple[Path, Path, str]:
    if path.is_dir():
        return path / "summary.json", path / "warning_eval.json", path.name
    run_name = path.stem
    if run_name.endswith("_summary"):
        run_name = run_name[: -len("_summary")]
    warning_eval_name = path.name.replace("summary", "warning_eval")
    return path, path.with_name(warning_eval_name), run_name


def render_variant_comparison_report(frame: pd.DataFrame) -> str:
    columns = [
        "run",
        "model",
        "variant",
        "auc",
        "brier_score",
        "ece",
        "precision",
        "recall",
        "f1",
        "alert_precision",
        "false_alarm_rate",
        "coverage",
    ]
    return (
        "# Baseline vs Transformer Comparison\n\n"
        "This report compares model and decision variants. Interpret calibration metrics "
        "separately from warning-decision metrics: a calibrated model can still need a "
        "conservative or recall-oriented warning policy.\n\n"
        f"{_markdown_table(frame, columns)}\n\n"
        "## Reading Notes\n\n"
        "- `raw`, `calibrated`, and `tuned` rows are probability-threshold model variants.\n"
        "- `trust_decision` rows use the warning-level evaluation artifact when present.\n"
        "- A useful v1 claim is improved reliability or more conservative alerting, not "
        "guaranteed drawdown prediction.\n"
    )


def run_comparison(args: argparse.Namespace) -> str:
    frame = build_variant_comparison_frame(args.runs)
    report = render_variant_comparison_report(frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def _metric_row(run_name: str, model_name: str, variant: str, metrics: dict[str, Any]) -> dict[str, Any]:
    row = {
        "run": run_name,
        "model": model_name,
        "variant": variant,
        "alert_precision": "",
        "false_alarm_rate": metrics.get("false_alarm_rate", ""),
        "coverage": "",
    }
    for metric in MODEL_METRICS:
        row[metric] = metrics.get(metric, "")
    return row


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _infer_model_name(summary: dict[str, Any]) -> str:
    folds = summary.get("folds")
    if isinstance(folds, list) and folds:
        first = folds[0]
        if isinstance(first, dict) and first.get("model"):
            return str(first["model"])
    if "model_config" in summary:
        return "temporal_transformer"
    return "unknown"


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


def main() -> None:
    args = parse_args()
    report = run_comparison(args)
    print(report)


if __name__ == "__main__":
    main()
