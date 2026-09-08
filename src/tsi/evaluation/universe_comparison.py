"""Schema-first paired comparison of current and point-in-time runs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi.evaluation.statistics import paired_fold_metric_intervals

UNIVERSE_COMPARISON_SCHEMA_VERSION = "universe_benchmark_comparison.v1"
PREDICTION_KEY_COLUMNS = ("fold_id", "ticker", "date", "risk_label")
METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "roc_auc": ("roc_auc", "auc"),
    "pr_auc": ("pr_auc",),
    "brier_score": ("brier_score",),
    "ece": ("ece",),
    "precision": ("precision",),
    "recall": ("recall",),
    "f1": ("f1",),
    "miss_rate": ("miss_rate",),
    "false_alarm_rate": ("false_alarm_rate",),
    "false_discovery_rate": ("false_discovery_rate",),
    "alert_coverage": ("alert_coverage", "coverage", "prediction_rate"),
    "lead_time": ("lead_time", "mean_lead_time", "alert_lead_time"),
}
METRIC_SECTIONS = ("prior", "raw", "calibrated", "tuned")


class ComparisonCoverageDelta(BaseModel):
    """Counts and hashes for evaluation/member coverage changes."""

    model_config = ConfigDict(extra="forbid")

    baseline_evaluation_row_count: int = Field(ge=0)
    comparison_evaluation_row_count: int = Field(ge=0)
    shared_evaluation_row_count: int = Field(ge=0)
    evaluation_rows_added_count: int = Field(ge=0)
    evaluation_rows_removed_count: int = Field(ge=0)
    baseline_evaluation_sha256: str
    comparison_evaluation_sha256: str
    evaluation_rows_added_sha256: str
    evaluation_rows_removed_sha256: str
    membership_comparison_available: bool
    baseline_membership_count: int | None = Field(default=None, ge=0)
    comparison_membership_count: int | None = Field(default=None, ge=0)
    membership_rows_added_count: int | None = Field(default=None, ge=0)
    membership_rows_removed_count: int | None = Field(default=None, ge=0)
    baseline_membership_sha256: str | None = None
    comparison_membership_sha256: str | None = None
    membership_rows_added_sha256: str | None = None
    membership_rows_removed_sha256: str | None = None
    coverage_audit_fields: dict[str, dict[str, int | None]]


class UniverseComparisonReport(BaseModel):
    """Public comparison artifact with no raw member or prediction rows."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = UNIVERSE_COMPARISON_SCHEMA_VERSION
    claim_status: Literal["comparable", "inconclusive"]
    run_ids: dict[str, str]
    input_manifests: dict[str, dict[str, object]]
    membership_manifests: dict[str, dict[str, object]]
    protocol: dict[str, object]
    coverage: ComparisonCoverageDelta
    metrics: dict[str, dict[str, object]]
    limitations: list[str]


@dataclass(frozen=True)
class _RunArtifact:
    summary: dict[str, Any]
    predictions: pd.DataFrame
    run_id: str
    protocol: dict[str, object]
    membership_manifest: dict[str, object]


def build_universe_comparison_report(
    baseline_summary_path: str | Path,
    comparison_summary_path: str | Path,
    *,
    baseline_predictions_path: str | Path | None = None,
    comparison_predictions_path: str | Path | None = None,
    baseline_membership_path: str | Path | None = None,
    comparison_membership_path: str | Path | None = None,
    baseline_coverage_audit_path: str | Path | None = None,
    comparison_coverage_audit_path: str | Path | None = None,
    baseline_run_id: str | None = None,
    comparison_run_id: str | None = None,
    seed: int = 42,
    resamples: int = 4_000,
    confidence: float = 0.95,
) -> dict[str, object]:
    """Build a fail-closed paired current-vs-PIT benchmark report."""

    baseline = _load_run(
        Path(baseline_summary_path),
        predictions_path=Path(baseline_predictions_path) if baseline_predictions_path else None,
        run_id=baseline_run_id,
    )
    comparison = _load_run(
        Path(comparison_summary_path),
        predictions_path=Path(comparison_predictions_path) if comparison_predictions_path else None,
        run_id=comparison_run_id,
    )
    _validate_protocol_compatibility(baseline.protocol, comparison.protocol)
    coverage = _build_coverage_delta(
        baseline,
        comparison,
        baseline_membership_path=(
            Path(baseline_membership_path) if baseline_membership_path else None
        ),
        comparison_membership_path=(
            Path(comparison_membership_path) if comparison_membership_path else None
        ),
        baseline_coverage_audit_path=(
            Path(baseline_coverage_audit_path) if baseline_coverage_audit_path else None
        ),
        comparison_coverage_audit_path=(
            Path(comparison_coverage_audit_path) if comparison_coverage_audit_path else None
        ),
    )
    metrics = _build_metric_report(
        baseline,
        comparison,
        seed=seed,
        resamples=resamples,
        confidence=confidence,
    )
    report = UniverseComparisonReport(
        claim_status="comparable",
        run_ids={"baseline": baseline.run_id, "comparison": comparison.run_id},
        input_manifests={
            "baseline": _input_manifest(baseline),
            "comparison": _input_manifest(comparison),
        },
        membership_manifests={
            "baseline": baseline.membership_manifest,
            "comparison": comparison.membership_manifest,
        },
        protocol=baseline.protocol,
        coverage=coverage,
        metrics=metrics,
        limitations=[
            "The statistical unit is the temporal test fold; intervals are paired fold-level percentile bootstraps.",
            "Evaluation-row and member deltas are coverage diagnostics, not evidence that all inactive or delisted history is available.",
            "A valid paired comparison is still operational pilot evidence and does not prove survivorship-bias absence.",
            "The report contains aggregate counts and fingerprints only; licensed source rows must remain outside version control.",
        ],
    )
    return report.model_dump(mode="json")


def render_universe_comparison_report(report: dict[str, object]) -> str:
    """Render a compact Markdown report from the machine-readable artifact."""

    coverage = report["coverage"]
    metrics = report["metrics"]
    lines = [
        "# Paired Current-vs-Point-in-Time Universe Benchmark",
        "",
        "This is a schema-compatible, leakage-aware coverage comparison. It is not investment advice",
        "and does not prove survivorship-bias absence.",
        "",
        f"- Claim status: **{report['claim_status']}**",
        f"- Baseline run: `{report['run_ids']['baseline']}`",
        f"- Comparison run: `{report['run_ids']['comparison']}`",
        f"- Evaluation rows added by comparison: `{coverage['evaluation_rows_added_count']}`",
        f"- Evaluation rows removed by comparison: `{coverage['evaluation_rows_removed_count']}`",
        f"- Membership comparison available: **{coverage['membership_comparison_available']}**",
        "",
        "## Paired metrics",
        "",
        "The uncertainty unit is the temporal test fold, not an independent row.",
        "",
        "| Section | Metric | Available | Delta estimate | 95% interval |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for section, section_metrics in metrics.items():
        for metric, result in section_metrics.items():
            if not isinstance(result, dict):
                continue
            if not result.get("available"):
                lines.append(f"| {section} | {metric} | no | n/a | n/a |")
                continue
            statistics = result.get("statistics", {})
            delta = statistics.get("delta", {})
            estimate = delta.get("estimate", "n/a")
            interval = f"[{delta.get('lower', 'n/a')}, {delta.get('upper', 'n/a')}]"
            lines.append(f"| {section} | {metric} | yes | {estimate} | {interval} |")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"


def _load_run(
    summary_path: Path,
    *,
    predictions_path: Path | None,
    run_id: str | None,
) -> _RunArtifact:
    summary = _read_json(summary_path)
    folds = summary.get("folds")
    if not isinstance(folds, list) or not folds:
        raise ValueError(f"{summary_path} must contain a non-empty folds list")
    if not all(isinstance(fold, dict) for fold in folds):
        raise ValueError(f"{summary_path} folds must be JSON objects")
    prediction_path = predictions_path or summary_path.with_name("predictions.csv")
    if not prediction_path.exists():
        raise FileNotFoundError(f"missing prediction artifact: {prediction_path}")
    predictions = pd.read_csv(prediction_path, dtype={"ticker": "string"})
    missing = [column for column in PREDICTION_KEY_COLUMNS if column not in predictions.columns]
    if missing:
        raise ValueError(f"{prediction_path} is missing prediction key columns: {missing}")
    if predictions.duplicated(list(PREDICTION_KEY_COLUMNS)).any():
        raise ValueError(f"{prediction_path} contains duplicate prediction keys")
    predictions = _normalize_prediction_keys(predictions, prediction_path)
    if predictions.duplicated(list(PREDICTION_KEY_COLUMNS)).any():
        raise ValueError(f"{prediction_path} contains duplicate normalized prediction keys")
    resolved_run_id = run_id or _string_or_none(summary.get("run_id")) or summary_path.stem
    return _RunArtifact(
        summary=summary,
        predictions=predictions,
        run_id=resolved_run_id,
        protocol=_protocol_contract(summary, folds),
        membership_manifest=_public_membership_manifest(summary.get("universe_membership")),
    )


def _protocol_contract(summary: dict[str, Any], folds: list[object]) -> dict[str, object]:
    schedule: list[dict[str, object]] = []
    for fold in folds:
        assert isinstance(fold, dict)
        required = (
            "fold_id",
            "train_start",
            "train_end",
            "calibration_start",
            "calibration_end",
            "test_start",
            "test_end",
        )
        missing = [key for key in required if key not in fold]
        if missing:
            raise ValueError(f"fold {fold.get('fold_id')!r} is missing schedule fields: {missing}")
        schedule.append({key: fold[key] for key in required})
    schedule.sort(key=lambda item: str(item["fold_id"]))
    return {
        "feature_columns": [str(column) for column in summary.get("feature_columns", [])],
        "label_contract": {
            "label_column": str(summary.get("label_column", "risk_label")),
            "horizon": summary.get("horizon"),
            "drawdown_threshold": summary.get("drawdown_threshold"),
        },
        "fold_schedule": schedule,
        "fold_count": len(schedule),
        "purge_size": summary.get("purge_size"),
        "train_size": summary.get("train_size"),
        "calibration_size": summary.get("calibration_size"),
        "test_size": summary.get("test_size"),
        "step_size": summary.get("step_size"),
        "calibration_method": summary.get("calibration_method"),
        "threshold_objective": summary.get("threshold_objective"),
        "model_config": {
            "model_type": summary.get("model_type"),
            "parameters": summary.get("model_config", {}),
        },
    }


def _validate_protocol_compatibility(
    baseline: dict[str, object],
    comparison: dict[str, object],
) -> None:
    if baseline == comparison:
        return
    for key in baseline:
        if baseline.get(key) != comparison.get(key):
            if key == "fold_schedule":
                raise ValueError("incompatible date windows or fold schedule")
            if key == "label_contract":
                raise ValueError("incompatible label contract")
            if key == "feature_columns":
                raise ValueError("incompatible feature contract")
            if key in {"calibration_method", "threshold_objective"}:
                raise ValueError("incompatible calibration or threshold configuration")
            if key == "model_config":
                raise ValueError("incompatible model configuration")
            raise ValueError(f"incompatible benchmark protocol: {key}")


def _build_metric_report(
    baseline: _RunArtifact,
    comparison: _RunArtifact,
    *,
    seed: int,
    resamples: int,
    confidence: float,
) -> dict[str, dict[str, object]]:
    baseline_folds = _section_folds(baseline.summary["folds"])
    comparison_folds = _section_folds(comparison.summary["folds"])
    report: dict[str, dict[str, object]] = {}
    for section in METRIC_SECTIONS:
        baseline_section = baseline_folds[section]
        comparison_section = comparison_folds[section]
        section_report: dict[str, object] = {}
        for metric in METRIC_ALIASES:
            base_values = [fold.get(metric) for fold in baseline_section]
            comparison_values = [fold.get(metric) for fold in comparison_section]
            if not _metric_has_finite_pair(base_values, comparison_values):
                section_report[metric] = {
                    "available": False,
                    "reason": "metric is absent or has no finite paired fold values",
                }
                continue
            stats = paired_fold_metric_intervals(
                _metric_folds(baseline_section, metric),
                _metric_folds(comparison_section, metric),
                metrics=[metric],
                seed=seed,
                resamples=resamples,
                confidence=confidence,
            )
            section_report[metric] = {
                "available": True,
                "statistics": stats["metrics"][metric],
            }
        report[section] = section_report
    return report


def _section_folds(folds: list[object]) -> dict[str, list[dict[str, object]]]:
    result = {section: [] for section in METRIC_SECTIONS}
    for fold in folds:
        assert isinstance(fold, dict)
        for section in METRIC_SECTIONS:
            metrics = fold.get(f"{section}_metrics")
            if not isinstance(metrics, dict):
                raise ValueError(f"fold {fold.get('fold_id')!r} has no {section}_metrics")
            normalized: dict[str, object] = {"fold_id": fold.get("fold_id")}
            for canonical, aliases in METRIC_ALIASES.items():
                normalized[canonical] = _first_numeric(metrics, aliases)
            result[section].append(normalized)
    return result


def _metric_folds(
    folds: Sequence[dict[str, object]],
    metric: str,
) -> list[dict[str, object]]:
    return [
        {"fold_id": fold.get("fold_id"), metric: _finite_or_nan(fold.get(metric))} for fold in folds
    ]


def _metric_has_finite_pair(
    baseline_values: Sequence[object], comparison_values: Sequence[object]
) -> bool:
    return any(
        _is_finite(left) and _is_finite(right)
        for left, right in zip(baseline_values, comparison_values, strict=True)
    )


def _first_numeric(metrics: dict[str, object], aliases: Sequence[str]) -> float | None:
    for alias in aliases:
        value = metrics.get(alias)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        return number if pd.notna(number) else None
    return None


def _build_coverage_delta(
    baseline: _RunArtifact,
    comparison: _RunArtifact,
    *,
    baseline_membership_path: Path | None,
    comparison_membership_path: Path | None,
    baseline_coverage_audit_path: Path | None,
    comparison_coverage_audit_path: Path | None,
) -> ComparisonCoverageDelta:
    baseline_keys = _prediction_key_set(baseline.predictions)
    comparison_keys = _prediction_key_set(comparison.predictions)
    added = comparison_keys - baseline_keys
    removed = baseline_keys - comparison_keys
    membership = _membership_delta(baseline_membership_path, comparison_membership_path)
    baseline_audit = _coverage_audit_fields(baseline, baseline_coverage_audit_path)
    comparison_audit = _coverage_audit_fields(comparison, comparison_coverage_audit_path)
    audit_fields = {
        "baseline": baseline_audit,
        "comparison": comparison_audit,
    }
    return ComparisonCoverageDelta(
        baseline_evaluation_row_count=len(baseline_keys),
        comparison_evaluation_row_count=len(comparison_keys),
        shared_evaluation_row_count=len(baseline_keys & comparison_keys),
        evaluation_rows_added_count=len(added),
        evaluation_rows_removed_count=len(removed),
        baseline_evaluation_sha256=_tuple_set_fingerprint(baseline_keys),
        comparison_evaluation_sha256=_tuple_set_fingerprint(comparison_keys),
        evaluation_rows_added_sha256=_tuple_set_fingerprint(added),
        evaluation_rows_removed_sha256=_tuple_set_fingerprint(removed),
        membership_comparison_available=membership is not None,
        baseline_membership_count=membership["baseline_count"] if membership else None,
        comparison_membership_count=membership["comparison_count"] if membership else None,
        membership_rows_added_count=membership["added_count"] if membership else None,
        membership_rows_removed_count=membership["removed_count"] if membership else None,
        baseline_membership_sha256=membership["baseline_sha256"] if membership else None,
        comparison_membership_sha256=membership["comparison_sha256"] if membership else None,
        membership_rows_added_sha256=membership["added_sha256"] if membership else None,
        membership_rows_removed_sha256=membership["removed_sha256"] if membership else None,
        coverage_audit_fields=audit_fields,
    )


def _membership_delta(
    baseline_path: Path | None,
    comparison_path: Path | None,
) -> dict[str, object] | None:
    if baseline_path is None or comparison_path is None:
        return None
    baseline_keys = _membership_key_set(baseline_path)
    comparison_keys = _membership_key_set(comparison_path)
    added = comparison_keys - baseline_keys
    removed = baseline_keys - comparison_keys
    return {
        "baseline_count": len(baseline_keys),
        "comparison_count": len(comparison_keys),
        "added_count": len(added),
        "removed_count": len(removed),
        "baseline_sha256": _tuple_set_fingerprint(baseline_keys),
        "comparison_sha256": _tuple_set_fingerprint(comparison_keys),
        "added_sha256": _tuple_set_fingerprint(added),
        "removed_sha256": _tuple_set_fingerprint(removed),
    }


def _membership_key_set(path: Path) -> set[tuple[str, ...]]:
    frame = pd.read_csv(path, dtype="string")
    required = ("security_id", "ticker", "valid_from")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing membership key columns: {missing}")
    columns = [*required, "valid_to"]
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    normalized = (
        frame.loc[:, columns].fillna("").astype(str).apply(lambda column: column.str.strip())
    )
    return {tuple(row) for row in normalized.itertuples(index=False, name=None)}


def _coverage_audit_fields(
    artifact: _RunArtifact,
    audit_path: Path | None,
) -> dict[str, int | None]:
    payload: object = artifact.summary.get(
        "membership_coverage", artifact.summary.get("coverage_audit", {})
    )
    if audit_path is not None:
        payload = _read_json(audit_path)
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("coverage_audit"), dict):
        payload = payload["coverage_audit"]
    fields = (
        "active_membership_count",
        "inactive_membership_count",
        "unavailable_data_membership_count",
        "removed_or_delisted_membership_count",
        "removed_or_delisted_missing_bars",
        "unmatched_identifier_count",
        "nonmembership_row_count",
    )
    return {
        field: int(payload[field]) if isinstance(payload.get(field), (int, float)) else None
        for field in fields
        if field in payload
    }


def _input_manifest(artifact: _RunArtifact) -> dict[str, object]:
    summary = artifact.summary
    return {
        "run_id": artifact.run_id,
        "input_sha256": summary.get("input_sha256"),
        "rows_after_filtering": summary.get("rows_after_filtering"),
        "feature_columns": [str(column) for column in summary.get("feature_columns", [])],
        "model_type": summary.get("model_type"),
    }


def _public_membership_manifest(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"status": "not_supplied"}
    allowed = (
        "status",
        "schema_version",
        "name",
        "source",
        "source_license",
        "interval_semantics",
        "membership_count",
        "security_count",
        "ticker_count",
        "provider_symbol_count",
        "valid_from",
        "valid_to",
        "membership_sha256",
        "input_sha256",
        "mapping_version",
        "note",
    )
    return {key: value[key] for key in allowed if key in value}


def _normalize_prediction_keys(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["ticker"] = normalized["ticker"].astype("string").str.strip()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if normalized["date"].isna().any():
        raise ValueError(f"{path} contains invalid prediction dates")
    if normalized.loc[:, list(PREDICTION_KEY_COLUMNS)].isna().any().any():
        raise ValueError(f"{path} contains missing prediction key values")
    return normalized


def _prediction_key_set(frame: pd.DataFrame) -> set[tuple[str, ...]]:
    keys = frame.loc[:, list(PREDICTION_KEY_COLUMNS)].copy()
    keys["fold_id"] = keys["fold_id"].astype(str)
    keys["ticker"] = keys["ticker"].astype(str)
    keys["date"] = keys["date"].astype(str)
    keys["risk_label"] = keys["risk_label"].astype(str)
    return {tuple(row) for row in keys.itertuples(index=False, name=None)}


def _tuple_set_fingerprint(values: set[tuple[str, ...]]) -> str:
    canonical = json.dumps(sorted(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _finite_or_nan(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if pd.notna(number) else float("nan")


def _is_finite(value: object) -> bool:
    try:
        return bool(pd.notna(float(value)))
    except (TypeError, ValueError):
        return False


def _string_or_none(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload
