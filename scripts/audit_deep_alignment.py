"""Fail-closed audit for deep-vs-baseline protocol and prediction-key parity."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


KEY_COLUMNS = ("fold_id", "ticker", "date", "risk_label")
PROTOCOL_COLUMNS = (
    "feature_columns",
    "horizon",
    "purge_size",
    "train_size",
    "calibration_size",
    "test_size",
    "step_size",
    "drawdown_threshold",
    "calibration_method",
    "threshold_objective",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--deep-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def build_alignment_report(
    baseline_summary_path: Path,
    deep_summary_path: Path,
) -> dict[str, object]:
    """Require identical protocol and prediction keys before reporting parity."""

    baseline = _read_json(baseline_summary_path)
    deep = _read_json(deep_summary_path)
    protocol_mismatches = {
        column: {"baseline": baseline.get(column), "deep": deep.get(column)}
        for column in PROTOCOL_COLUMNS
        if baseline.get(column) != deep.get(column)
    }
    if protocol_mismatches:
        raise ValueError(f"protocol mismatch; deep comparison is not valid: {protocol_mismatches}")

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

    return {
        "aligned": True,
        "protocol": {column: baseline.get(column) for column in PROTOCOL_COLUMNS},
        "fold_count": len(set(baseline_predictions["fold_id"])),
        "shared_row_count": len(baseline_keys),
        "key_columns": list(KEY_COLUMNS),
        "sample_key_sha256": _keys_hash(baseline_predictions),
        "baseline_summary": str(baseline_summary_path),
        "deep_summary": str(deep_summary_path),
        "baseline_model": _model_name(baseline),
        "deep_model": _model_name(deep),
    }


def render_report(report: dict[str, object]) -> str:
    """Render the successful alignment audit."""

    protocol = report["protocol"]
    return "\n".join(
        [
            "# Deep-vs-Baseline Sample-Key Alignment",
            "",
            "The audit passed only after matching the temporal protocol and every",
            "`fold_id | ticker | date | risk_label` sample key.",
            "",
            f"- Baseline model: `{report['baseline_model']}`",
            f"- Deep model: `{report['deep_model']}`",
            f"- Fold count: `{report['fold_count']}`",
            f"- Shared rows: `{report['shared_row_count']}`",
            f"- Sample-key SHA-256: `{report['sample_key_sha256']}`",
            f"- Protocol: `{json.dumps(protocol, sort_keys=True)}`",
            "",
            "This establishes comparable sample support; it does not establish model",
            "quality, calibration stability, or investment usefulness.",
            "",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, object]:
    report = build_alignment_report(args.baseline_summary, args.deep_summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
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
    missing = [column for column in KEY_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing sample-key columns: {missing}")
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError(f"{path} contains duplicate sample keys")
    return frame


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


def _model_name(summary: dict[str, Any]) -> str:
    folds = summary.get("folds")
    if isinstance(folds, list) and folds and isinstance(folds[0], dict):
        return str(folds[0].get("model", "unknown"))
    return str(summary.get("model_type", "unknown"))


def main() -> None:
    report = run(parse_args())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
