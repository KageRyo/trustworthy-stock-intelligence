"""Fail closed before reporting a deep-vs-baseline purged benchmark."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsi.evaluation.metrics import classification_metrics


KEY_COLUMNS = ("fold_id", "ticker", "date", "risk_label")
PREDICTION_COLUMNS = (
    "risk_probability",
    "calibrated_risk_probability",
    "alert_threshold",
)
PROTOCOL_COLUMNS = (
    "feature_columns",
    "horizon",
    "purge_size",
    "train_size",
    "calibration_size",
    "test_size",
    "step_size",
    "sequence_lookback",
    "drawdown_threshold",
    "calibration_method",
    "threshold_objective",
)
METRIC_SECTIONS = ("raw", "calibrated", "tuned")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--deep-summary", type=Path, required=True)
    parser.add_argument(
        "--expected-fold-count",
        type=int,
        default=39,
        help="Required contiguous fold count. Use 1 only for an explicitly labelled smoke audit.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def build_alignment_report(
    baseline_summary_path: Path,
    deep_summary_path: Path,
    *,
    expected_fold_count: int | None = None,
) -> dict[str, object]:
    """Verify all conditions needed for a quality comparison, or raise an error."""

    if expected_fold_count is not None and expected_fold_count < 1:
        raise ValueError("expected_fold_count must be at least 1")

    baseline = _read_json(baseline_summary_path)
    deep = _read_json(deep_summary_path)
    protocol_mismatches = {
        column: {
            "baseline": _protocol_value(baseline, column),
            "deep": _protocol_value(deep, column),
        }
        for column in PROTOCOL_COLUMNS
        if _protocol_value(baseline, column) != _protocol_value(deep, column)
    }
    if protocol_mismatches:
        raise ValueError(f"protocol mismatch; deep comparison is not valid: {protocol_mismatches}")

    input_sha256 = _require_matching_input_hash(baseline, deep)
    universe_membership = _require_matching_universe_membership(baseline, deep)
    deep_training = _require_cuda_deep_training(deep)
    baseline_predictions = _read_predictions(baseline_summary_path.with_name("predictions.csv"))
    deep_predictions = _read_predictions(deep_summary_path.with_name("predictions.csv"))
    baseline_keys = _canonical_keys(baseline_predictions)
    deep_keys = _canonical_keys(deep_predictions)
    if baseline_keys != deep_keys:
        raise ValueError(
            "prediction sample keys are not identical; refusing a deep-vs-baseline claim: "
            f"baseline_only={len(baseline_keys - deep_keys)}, "
            f"deep_only={len(deep_keys - baseline_keys)}"
        )

    baseline_fold_ids = _validate_fold_inventory(
        baseline,
        baseline_predictions,
        expected_fold_count=expected_fold_count,
        artifact_name="baseline",
    )
    deep_fold_ids = _validate_fold_inventory(
        deep,
        deep_predictions,
        expected_fold_count=expected_fold_count,
        artifact_name="deep",
    )
    if baseline_fold_ids != deep_fold_ids:
        raise ValueError("baseline and deep artifacts have different fold inventories")

    return {
        "aligned": True,
        "quality_comparison_allowed": expected_fold_count == 39,
        "expected_fold_count": expected_fold_count,
        "fold_count": len(baseline_fold_ids),
        "fold_ids": baseline_fold_ids,
        "protocol": {column: _protocol_value(baseline, column) for column in PROTOCOL_COLUMNS},
        "input_sha256": input_sha256,
        "universe_membership": universe_membership,
        "deep_training": deep_training,
        "shared_row_count": len(baseline_keys),
        "key_columns": list(KEY_COLUMNS),
        "sample_key_sha256": _keys_hash(baseline_predictions),
        "baseline_summary": str(baseline_summary_path),
        "deep_summary": str(deep_summary_path),
        "baseline_model": _model_name(baseline),
        "deep_model": _model_name(deep),
        "metrics": {
            "baseline": _recompute_metrics(baseline_predictions),
            "deep": _recompute_metrics(deep_predictions),
        },
    }


def render_report(report: dict[str, object]) -> str:
    """Render an evidence-boundary report with recomputed aggregate metrics."""

    protocol = report["protocol"]
    metrics = report["metrics"]
    baseline_metrics = metrics["baseline"]["aggregate"]
    deep_metrics = metrics["deep"]["aggregate"]
    quality_status = (
        "This is a complete 39-fold benchmark audit."
        if report["quality_comparison_allowed"]
        else "This is a smoke/custom audit and cannot support the Issue #21 quality claim."
    )
    rows = (
        ("Calibrated ROC-AUC", "calibrated", "auc"),
        ("Calibrated PR-AUC", "calibrated", "pr_auc"),
        ("Calibrated Brier", "calibrated", "brier_score"),
        ("Calibrated ECE", "calibrated", "ece"),
        ("Tuned precision", "tuned", "precision"),
        ("Tuned recall", "tuned", "recall"),
        ("Tuned F1", "tuned", "f1"),
        ("Tuned false-positive rate", "tuned", "false_alarm_rate"),
        ("Tuned false-discovery rate", "tuned", "false_discovery_rate"),
        ("Tuned alert coverage", "tuned", "prediction_rate"),
    )
    lines = [
        "# Deep-vs-Baseline Purged Benchmark Audit",
        "",
        "The audit passed only after matching the temporal protocol, raw-input",
        "fingerprint, universe-membership manifest, and every",
        "`fold_id | ticker | date | risk_label` sample key.",
        "",
        f"- Baseline model: `{report['baseline_model']}`",
        f"- Deep model: `{report['deep_model']}`",
        f"- Expected/actual folds: `{report['expected_fold_count']}` / `{report['fold_count']}`",
        f"- Fold IDs: `{', '.join(map(str, report['fold_ids']))}`",
        f"- Shared rows: `{report['shared_row_count']}`",
        f"- Input SHA-256: `{report['input_sha256']}`",
        f"- Deep training device/GPU count: `{report['deep_training']['device']}` / "
        f"`{report['deep_training']['max_gpu_count']}`",
        f"- Sample-key SHA-256: `{report['sample_key_sha256']}`",
        f"- Protocol: `{json.dumps(protocol, sort_keys=True)}`",
        "",
        quality_status,
        "",
        "## Recomputed Aggregate Metrics",
        "",
        "The JSON artifact also contains the reproducible per-fold metrics. Alert",
        "coverage is the fraction of test rows above that fold's calibration-only",
        "alert threshold; these models do not implement abstention.",
        "",
        "| Metric | Baseline | Deep |",
        "| --- | ---: | ---: |",
    ]
    for label, section, metric in rows:
        lines.append(
            f"| {label} | {_format_metric(baseline_metrics[section][metric])} | "
            f"{_format_metric(deep_metrics[section][metric])} |"
        )
    lines.extend(
        [
            "",
            "Comparable metrics establish experimental evidence only; they do not",
            "establish investment usefulness or trading performance.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, object]:
    report = build_alignment_report(
        args.baseline_summary,
        args.deep_summary,
        expected_fold_count=args.expected_fold_count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(report), encoding="utf-8")
    return report


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _read_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing sibling prediction artifact: {path}")
    frame = pd.read_csv(path)
    required = (*KEY_COLUMNS, *PREDICTION_COLUMNS)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing required prediction columns: {missing}")
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError(f"{path} contains duplicate sample keys")
    return frame


def _require_matching_input_hash(baseline: dict[str, Any], deep: dict[str, Any]) -> str:
    baseline_hash = baseline.get("input_sha256")
    deep_hash = deep.get("input_sha256")
    if not isinstance(baseline_hash, str) or not isinstance(deep_hash, str):
        raise ValueError("both summaries must record input_sha256 before a quality comparison")
    if len(baseline_hash) != 64 or len(deep_hash) != 64:
        raise ValueError("input_sha256 must be a 64-character SHA-256 digest")
    if baseline_hash != deep_hash:
        raise ValueError("input snapshot mismatch; deep comparison is not valid")
    return baseline_hash


def _require_matching_universe_membership(
    baseline: dict[str, Any], deep: dict[str, Any]
) -> dict[str, object]:
    baseline_membership = baseline.get("universe_membership")
    deep_membership = deep.get("universe_membership")
    if not isinstance(baseline_membership, dict) or not isinstance(deep_membership, dict):
        raise ValueError("both summaries must record universe_membership metadata")
    if _canonical_json(baseline_membership) != _canonical_json(deep_membership):
        raise ValueError("universe membership mismatch; deep comparison is not valid")
    return baseline_membership


def _require_cuda_deep_training(summary: dict[str, Any]) -> dict[str, object]:
    training_config = summary.get("training_config")
    if not isinstance(training_config, dict):
        raise ValueError("deep summary must record training_config before a quality comparison")
    device = training_config.get("device")
    gpu_count = training_config.get("max_gpu_count")
    if not isinstance(device, str) or not device.startswith("cuda"):
        raise ValueError("deep quality comparison requires CUDA training")
    if not isinstance(gpu_count, int) or gpu_count < 1:
        raise ValueError("deep quality comparison requires at least one CUDA GPU")
    return {
        "device": device,
        "max_gpu_count": gpu_count,
        "used_data_parallel": bool(training_config.get("used_data_parallel", False)),
    }


def _validate_fold_inventory(
    summary: dict[str, Any],
    predictions: pd.DataFrame,
    *,
    expected_fold_count: int | None,
    artifact_name: str,
) -> list[int]:
    try:
        fold_ids = [
            int(fold_id)
            for fold_id in sorted(
                pd.to_numeric(predictions["fold_id"], errors="raise").astype(int).unique()
            )
        ]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{artifact_name} predictions have invalid fold IDs") from exc
    if not fold_ids:
        raise ValueError(f"{artifact_name} predictions do not contain any folds")
    if expected_fold_count is not None and fold_ids != list(range(expected_fold_count)):
        raise ValueError(
            f"{artifact_name} fold IDs must be contiguous 0..{expected_fold_count - 1}; got {fold_ids}"
        )
    summary_fold_count = summary.get("fold_count")
    if summary_fold_count != len(fold_ids):
        raise ValueError(
            f"{artifact_name} summary fold_count={summary_fold_count!r} does not match predictions"
        )
    folds = summary.get("folds")
    if not isinstance(folds, list):
        raise ValueError(f"{artifact_name} summary must contain a folds list")
    declared_fold_ids = sorted(fold.get("fold_id") for fold in folds if isinstance(fold, dict))
    if declared_fold_ids != fold_ids:
        raise ValueError(f"{artifact_name} summary fold IDs do not match prediction fold IDs")
    return fold_ids


def _recompute_metrics(predictions: pd.DataFrame) -> dict[str, object]:
    numeric = predictions.loc[:, ["risk_label", *PREDICTION_COLUMNS]].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if numeric.isna().any().any():
        raise ValueError("predictions contain non-numeric labels, probabilities, or thresholds")
    if not numeric["risk_label"].isin([0, 1]).all():
        raise ValueError("risk_label must contain only 0 or 1")
    for column in PREDICTION_COLUMNS:
        if ((numeric[column] < 0.0) | (numeric[column] > 1.0)).any():
            raise ValueError(f"{column} must be between 0 and 1")

    per_fold: dict[str, dict[str, dict[str, float | None]]] = {}
    for fold_id, fold in predictions.assign(**numeric).groupby("fold_id", sort=True):
        thresholds = fold["alert_threshold"].unique()
        if len(thresholds) != 1:
            raise ValueError(f"fold {fold_id} has more than one alert_threshold")
        labels = fold["risk_label"].to_numpy(dtype=int)
        per_fold[str(int(fold_id))] = {
            "raw": _json_metrics(classification_metrics(labels, fold["risk_probability"].to_numpy())),
            "calibrated": _json_metrics(
                classification_metrics(labels, fold["calibrated_risk_probability"].to_numpy())
            ),
            "tuned": _json_metrics(
                classification_metrics(
                    labels,
                    fold["calibrated_risk_probability"].to_numpy(),
                    threshold=float(thresholds[0]),
                )
            ),
        }

    aggregate = {
        section: _mean_metrics([fold[section] for fold in per_fold.values()])
        for section in METRIC_SECTIONS
    }
    return {"aggregate": aggregate, "per_fold": per_fold}


def _json_metrics(metrics: dict[str, float]) -> dict[str, float | None]:
    return {
        name: float(value) if math.isfinite(float(value)) else None
        for name, value in metrics.items()
    }


def _mean_metrics(metrics: Sequence[dict[str, float | None]]) -> dict[str, float | None]:
    metric_names = metrics[0].keys()
    return {
        name: _finite_mean([metric[name] for metric in metrics])
        for name in metric_names
    }


def _finite_mean(values: Sequence[float | None]) -> float | None:
    finite_values = [float(value) for value in values if value is not None]
    return float(np.mean(finite_values)) if finite_values else None


def _canonical_keys(frame: pd.DataFrame) -> set[tuple[str, ...]]:
    keys = frame.loc[:, list(KEY_COLUMNS)].copy()
    keys = keys.astype({column: "string" for column in KEY_COLUMNS})
    return set(map(tuple, keys.itertuples(index=False, name=None)))


def _keys_hash(frame: pd.DataFrame) -> str:
    keys = frame.loc[:, list(KEY_COLUMNS)].copy()
    keys = keys.astype({column: "string" for column in KEY_COLUMNS})
    canonical = keys.sort_values(list(KEY_COLUMNS), kind="mergesort").to_csv(
        index=False,
        lineterminator="\n",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _protocol_value(summary: dict[str, Any], column: str) -> object:
    if column == "sequence_lookback":
        return summary.get(column, summary.get("lookback"))
    return summary.get(column)


def _model_name(summary: dict[str, Any]) -> str:
    model_type = summary.get("model_type")
    if isinstance(model_type, str) and model_type:
        return model_type
    folds = summary.get("folds")
    if isinstance(folds, list) and folds and isinstance(folds[0], dict):
        return str(folds[0].get("model", "unknown"))
    return "unknown"


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def main() -> None:
    report = run(parse_args())
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
