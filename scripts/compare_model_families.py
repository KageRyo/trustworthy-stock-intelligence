"""Audit and compare baseline model families from identical purged runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


KEY_COLUMNS = ("fold_id", "ticker", "date", "risk_label")
METRIC_SECTIONS = ("prior", "raw", "calibrated", "tuned")
DISPLAY_METRICS = (
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
    parser.add_argument(
        "--runs",
        type=Path,
        nargs="+",
        required=True,
        help="Summary JSON files; each must have a sibling predictions.csv.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Machine-readable comparison JSON.")
    parser.add_argument("--report", type=Path, required=True, help="Markdown report path.")
    return parser.parse_args(argv)


def build_model_family_report(summary_paths: Sequence[Path]) -> dict[str, object]:
    """Build a comparison report and fail closed on protocol/key mismatches."""

    if len(summary_paths) < 2:
        raise ValueError("at least two model summaries are required")
    artifacts = [_load_artifact(path) for path in summary_paths]
    protocol = artifacts[0]["protocol"]
    for artifact in artifacts[1:]:
        if artifact["protocol"] != protocol:
            raise ValueError("model summaries do not use identical temporal protocols")

    key_audit = _audit_sample_keys(artifacts)
    models = [_model_result(artifact) for artifact in artifacts]
    return {
        "experiment_id": "008_model_family_comparison",
        "protocol": protocol,
        "sample_key_audit": key_audit,
        "models": models,
        "deep_model_status": {
            "included": False,
            "reason": (
                "The current temporal model uses sequence lookback windows and therefore "
                "does not emit the exact row-level sample keys used by this baseline audit. "
                "It must be aligned separately before a deep-vs-baseline claim."
            ),
        },
        "limitations": [
            "The benchmark uses the current-universe S&P 100 snapshot and inherits survivorship bias.",
            "Tree hyperparameters are fixed before the test windows; no test data are used for selection.",
            "Results are pilot evidence and do not establish trading performance or investment advice.",
        ],
    }


def render_report(report: dict[str, object]) -> str:
    """Render a conservative human-readable model-family report."""

    protocol = report["protocol"]
    key_audit = report["sample_key_audit"]
    models = report["models"]
    lines = [
        "# Experiment 008: Purged Model-Family Comparison",
        "",
        "This report compares baseline model families under the same leakage-aware",
        "protocol. It is reproducible pilot evidence, not investment advice or a",
        "trading-performance claim.",
        "",
        "## Protocol",
        "",
        f"- Horizon: `{protocol['horizon']}` trading days",
        f"- Purge size: `{protocol['purge_size']}` dates",
        f"- Train/calibration/test: `{protocol['train_size']}` / `{protocol['calibration_size']}` / `{protocol['test_size']}` dates",
        f"- Fold count: `{protocol['fold_count']}`",
        f"- Feature columns: `{', '.join(protocol['feature_columns'])}`",
        "",
        "## Sample-Key Audit",
        "",
        f"- Key columns: `{', '.join(KEY_COLUMNS)}`",
        f"- Identical across models: **{key_audit['identical']}**",
        f"- Shared row count: `{key_audit['shared_row_count']}`",
        "",
        "| Model | Calibrated AUC | Calibrated PR-AUC | Calibrated Brier | Calibrated ECE | Tuned F1 | Tuned FDR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in models:
        calibrated = model["metrics"]["calibrated"]
        tuned = model["metrics"]["tuned"]
        lines.append(
            "| {model} | {auc} | {pr_auc} | {brier} | {ece} | {f1} | {fdr} |".format(
                model=model["model"],
                auc=_format_cell(calibrated.get("auc")),
                pr_auc=_format_cell(calibrated.get("pr_auc")),
                brier=_format_cell(calibrated.get("brier_score")),
                ece=_format_cell(calibrated.get("ece")),
                f1=_format_cell(tuned.get("f1")),
                fdr=_format_cell(tuned.get("false_discovery_rate")),
            )
        )
    lines.extend(
        [
            "",
            "## Deep Model Boundary",
            "",
            f"{report['deep_model_status']['reason']}",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, object]:
    report = build_model_family_report(args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(report), encoding="utf-8")
    return report


def _load_artifact(summary_path: Path) -> dict[str, object]:
    summary = _read_json(summary_path)
    folds = summary.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError(f"{summary_path} must contain a non-empty folds list")
    predictions_path = summary_path.with_name("predictions.csv")
    if not predictions_path.exists():
        raise FileNotFoundError(f"missing sibling prediction artifact: {predictions_path}")
    predictions = pd.read_csv(predictions_path)
    missing = [column for column in KEY_COLUMNS if column not in predictions.columns]
    if missing:
        raise ValueError(f"{predictions_path} is missing sample-key columns: {missing}")
    if predictions.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError(f"{predictions_path} contains duplicate sample keys")
    protocol = {
        "feature_columns": [str(column) for column in summary.get("feature_columns", [])],
        "horizon": summary.get("horizon"),
        "purge_size": summary.get("purge_size"),
        "train_size": summary.get("train_size"),
        "calibration_size": summary.get("calibration_size"),
        "test_size": summary.get("test_size"),
        "step_size": summary.get("step_size"),
        "drawdown_threshold": summary.get("drawdown_threshold"),
        "calibration_method": summary.get("calibration_method"),
        "threshold_objective": summary.get("threshold_objective"),
        "fold_count": len(folds),
        "rows_after_filtering": summary.get("rows_after_filtering"),
    }
    return {
        "summary": summary,
        "summary_path": str(summary_path),
        "predictions": predictions,
        "protocol": protocol,
    }


def _audit_sample_keys(artifacts: Sequence[dict[str, object]]) -> dict[str, object]:
    key_frames = []
    hashes: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    for artifact in artifacts:
        summary = artifact["summary"]
        predictions = artifact["predictions"]
        model = str(summary.get("model_type", "unknown"))
        keys = predictions.loc[:, list(KEY_COLUMNS)].copy()
        keys = keys.astype({column: "string" for column in KEY_COLUMNS})
        keys = keys.sort_values(list(KEY_COLUMNS), kind="mergesort")
        canonical = keys.to_csv(index=False, lineterminator="\n").encode("utf-8")
        hashes[model] = hashlib.sha256(canonical).hexdigest()
        row_counts[model] = len(keys)
        key_frames.append(set(map(tuple, keys.itertuples(index=False, name=None))))
    identical = all(frame == key_frames[0] for frame in key_frames[1:])
    return {
        "key_columns": list(KEY_COLUMNS),
        "identical": identical,
        "shared_row_count": len(key_frames[0]) if identical else None,
        "row_counts": row_counts,
        "sha256_by_model": hashes,
    }


def _model_result(artifact: dict[str, object]) -> dict[str, object]:
    summary = artifact["summary"]
    return {
        "model": summary.get("model_type", "unknown"),
        "implementation_name": _implementation_name(summary),
        "fold_count": summary.get("fold_count"),
        "test_rows": len(artifact["predictions"]),
        "metrics": {
            section: {
                metric: _json_number(_as_dict(summary.get("summary")).get(section, {}).get(metric))
                for metric in DISPLAY_METRICS
            }
            for section in METRIC_SECTIONS
        },
        "summary_std": _as_dict(summary.get("summary_std")),
    }


def _implementation_name(summary: dict[str, Any]) -> str:
    folds = summary.get("folds")
    if isinstance(folds, list) and folds and isinstance(folds[0], dict):
        return str(folds[0].get("model", summary.get("model_type", "unknown")))
    return str(summary.get("model_type", "unknown"))


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_number(value: object) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _format_cell(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


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
