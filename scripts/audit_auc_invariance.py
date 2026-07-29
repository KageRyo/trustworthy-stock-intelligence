"""Audit raw-versus-calibrated AUC invariance for paired prediction artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

DEFAULT_TOLERANCE = 1e-12
DEFAULT_MAPPING_TOLERANCE = 1e-10


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Paired prediction CSV.")
    parser.add_argument("--summary", type=Path, default=None, help="Optional training summary JSON.")
    parser.add_argument(
        "--comparison",
        type=Path,
        default=None,
        help="Optional pooled calibration-comparison JSON.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fold-col", default="fold_id")
    parser.add_argument("--ticker-col", default="ticker")
    parser.add_argument("--date-col", default="date")
    parser.add_argument("--label-col", default="risk_label")
    parser.add_argument("--raw-prob-col", default="risk_probability")
    parser.add_argument(
        "--calibrated-prob-col",
        default="calibrated_risk_probability",
    )
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument(
        "--mapping-tolerance",
        type=float,
        default=DEFAULT_MAPPING_TOLERANCE,
    )
    return parser.parse_args(argv)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_scalar(value: object) -> object:
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


def _canonical_number(value: object) -> str:
    scalar = _json_scalar(value)
    if isinstance(scalar, float) and scalar.is_integer():
        return str(int(scalar))
    return str(scalar)


def _variant_frame(
    frame: pd.DataFrame,
    *,
    probability_col: str,
    fold_col: str,
    ticker_col: str,
    date_col: str,
    label_col: str,
) -> pd.DataFrame:
    probabilities = pd.to_numeric(frame[probability_col], errors="coerce")
    labels = pd.to_numeric(frame[label_col], errors="coerce")
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    valid = (
        probabilities.notna()
        & np.isfinite(probabilities)
        & labels.notna()
        & np.isfinite(labels)
        & frame[fold_col].notna()
        & frame[ticker_col].notna()
        & dates.notna()
    )
    selected = frame.loc[valid, [fold_col, ticker_col]].copy()
    selected["__date"] = dates.loc[valid].dt.strftime("%Y-%m-%d")
    selected["__label"] = labels.loc[valid].astype(int)
    selected["__probability"] = probabilities.loc[valid].astype(float)
    if not selected["__label"].isin([0, 1]).all():
        raise ValueError(f"{label_col} must contain only binary labels")
    selected["__sample_key"] = (
        selected[fold_col].map(_canonical_number)
        + "|"
        + selected[ticker_col].astype(str)
        + "|"
        + selected["__date"]
        + "|"
        + selected["__label"].astype(str)
    )
    return selected.loc[:, ["__sample_key", "__label", "__probability"]]


def _sample_key_hash(keys: pd.Series) -> str:
    digest = hashlib.sha256()
    for key in sorted(keys.astype(str).tolist()):
        digest.update(key.encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _safe_auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    if np.unique(labels).size < 2:
        return None
    return float(roc_auc_score(labels, probabilities))


def _spearman_rank_correlation(raw: np.ndarray, calibrated: np.ndarray) -> float | None:
    if len(raw) < 2 or np.unique(raw).size < 2 or np.unique(calibrated).size < 2:
        return None
    raw_ranks = pd.Series(raw).rank(method="average")
    calibrated_ranks = pd.Series(calibrated).rank(method="average")
    correlation = raw_ranks.corr(calibrated_ranks)
    return None if pd.isna(correlation) else float(correlation)


def _ranking_inversion_count(raw: np.ndarray, calibrated: np.ndarray) -> int:
    """Count strict order reversals, excluding pairs tied in either variant."""

    if len(raw) < 2:
        return 0
    order = np.argsort(raw, kind="stable")
    raw_sorted = raw[order]
    calibrated_sorted = calibrated[order]
    calibrated_ranks = np.searchsorted(np.unique(calibrated_sorted), calibrated_sorted)
    tree = np.zeros(int(calibrated_ranks.max()) + 2, dtype=np.int64)

    def query(index: int) -> int:
        total = 0
        while index > 0:
            total += int(tree[index])
            index -= index & -index
        return total

    def add(index: int) -> None:
        while index < len(tree):
            tree[index] += 1
            index += index & -index

    inversions = 0
    seen = 0
    start = 0
    while start < len(raw_sorted):
        end = start + 1
        while end < len(raw_sorted) and raw_sorted[end] == raw_sorted[start]:
            end += 1
        for rank in calibrated_ranks[start:end]:
            inversions += seen - query(int(rank) + 1)
        for rank in calibrated_ranks[start:end]:
            add(int(rank) + 1)
            seen += 1
        start = end
    return int(inversions)


def _strict_order_pair_count(values: np.ndarray) -> int:
    total_pairs = len(values) * (len(values) - 1) // 2
    _, counts = np.unique(values, return_counts=True)
    tied_pairs = sum(int(count) * (int(count) - 1) // 2 for count in counts)
    return int(total_pairs - tied_pairs)


def _reconstruct_platt_mapping(
    raw: np.ndarray,
    calibrated: np.ndarray,
    *,
    tolerance: float,
) -> dict[str, object]:
    if (
        len(raw) < 2
        or np.unique(raw).size < 2
        or np.any(calibrated <= 0.0)
        or np.any(calibrated >= 1.0)
    ):
        return {
            "platt_coefficient": None,
            "platt_intercept": None,
            "coefficient_sign": "unavailable",
            "platt_reconstruction_max_abs_error": None,
        }
    calibrated_logits = np.log(calibrated) - np.log1p(-calibrated)
    design = np.column_stack([raw, np.ones_like(raw)])
    coefficient, intercept = np.linalg.lstsq(design, calibrated_logits, rcond=None)[0]
    residual = calibrated_logits - design @ np.array([coefficient, intercept])
    if coefficient > tolerance:
        sign = "positive"
    elif coefficient < -tolerance:
        sign = "negative"
    else:
        sign = "zero"
    return {
        "platt_coefficient": float(coefficient),
        "platt_intercept": float(intercept),
        "coefficient_sign": sign,
        "platt_reconstruction_max_abs_error": float(np.max(np.abs(residual))),
    }


def _fold_lookup(summary: dict[str, Any] | None) -> dict[object, dict[str, Any]]:
    if summary is None:
        return {}
    return {
        _json_scalar(fold["fold_id"]): fold
        for fold in summary.get("folds", [])
        if isinstance(fold, dict) and "fold_id" in fold
    }


def _fold_metadata(fold: dict[str, Any] | None) -> dict[str, object]:
    if fold is None:
        return {}
    calibration_metrics = (
        fold.get("threshold_selection", {}).get("calibration_metrics", {})
        if isinstance(fold.get("threshold_selection"), dict)
        else {}
    )
    raw_metrics = fold.get("raw_metrics", {})
    return {
        "calibration_start": fold.get("calibration_start"),
        "calibration_end": fold.get("calibration_end"),
        "test_start": fold.get("test_start"),
        "test_end": fold.get("test_end"),
        "calibration_event_rate": calibration_metrics.get("positive_rate"),
        "test_event_rate": (
            raw_metrics.get("positive_rate") if isinstance(raw_metrics, dict) else None
        ),
    }


def _fold_diagnostic(
    frame: pd.DataFrame,
    *,
    fold_id: object,
    fold_summary: dict[str, Any] | None,
    fold_col: str,
    ticker_col: str,
    date_col: str,
    label_col: str,
    raw_prob_col: str,
    calibrated_prob_col: str,
    tolerance: float,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    raw_frame = _variant_frame(
        frame,
        probability_col=raw_prob_col,
        fold_col=fold_col,
        ticker_col=ticker_col,
        date_col=date_col,
        label_col=label_col,
    )
    calibrated_frame = _variant_frame(
        frame,
        probability_col=calibrated_prob_col,
        fold_col=fold_col,
        ticker_col=ticker_col,
        date_col=date_col,
        label_col=label_col,
    )
    raw_hash = _sample_key_hash(raw_frame["__sample_key"])
    calibrated_hash = _sample_key_hash(calibrated_frame["__sample_key"])
    raw_duplicate_count = int(raw_frame["__sample_key"].duplicated().sum())
    calibrated_duplicate_count = int(
        calibrated_frame["__sample_key"].duplicated().sum()
    )

    raw_labels = raw_frame["__label"].to_numpy(dtype=int)
    calibrated_labels = calibrated_frame["__label"].to_numpy(dtype=int)
    raw_probabilities = raw_frame["__probability"].to_numpy(dtype=float)
    calibrated_probabilities = calibrated_frame["__probability"].to_numpy(dtype=float)
    raw_auc = _safe_auc(raw_labels, raw_probabilities)
    calibrated_auc = _safe_auc(calibrated_labels, calibrated_probabilities)

    aligned = raw_frame.merge(
        calibrated_frame,
        on="__sample_key",
        how="inner",
        suffixes=("_raw", "_calibrated"),
    )
    aligned_raw = aligned["__probability_raw"].to_numpy(dtype=float)
    aligned_calibrated = aligned["__probability_calibrated"].to_numpy(dtype=float)
    spearman = _spearman_rank_correlation(aligned_raw, aligned_calibrated)
    inversions = _ranking_inversion_count(aligned_raw, aligned_calibrated)
    mapping = _reconstruct_platt_mapping(
        aligned_raw,
        aligned_calibrated,
        tolerance=tolerance,
    )
    auc_delta = (
        calibrated_auc - raw_auc
        if raw_auc is not None and calibrated_auc is not None
        else None
    )
    diagnostic = {
        "fold_id": _json_scalar(fold_id),
        "raw_sample_count": int(len(raw_frame)),
        "calibrated_sample_count": int(len(calibrated_frame)),
        "raw_positive_count": int(raw_labels.sum()),
        "calibrated_positive_count": int(calibrated_labels.sum()),
        "raw_sample_key_hash": raw_hash,
        "calibrated_sample_key_hash": calibrated_hash,
        "raw_duplicate_sample_key_count": raw_duplicate_count,
        "calibrated_duplicate_sample_key_count": calibrated_duplicate_count,
        **mapping,
        "raw_auc": raw_auc,
        "calibrated_auc": calibrated_auc,
        "auc_delta": auc_delta,
        "raw_single_class": bool(np.unique(raw_labels).size < 2),
        "calibrated_single_class": bool(np.unique(calibrated_labels).size < 2),
        "raw_valid_auc": raw_auc is not None,
        "calibrated_valid_auc": calibrated_auc is not None,
        "spearman_rank_correlation": spearman,
        "ranking_inversion_count": inversions,
        "strict_raw_order_pair_count": _strict_order_pair_count(aligned_raw),
        **_fold_metadata(fold_summary),
    }
    return diagnostic, raw_frame, calibrated_frame


def _pair(raw: float | None, calibrated: float | None) -> dict[str, float | None]:
    return {
        "raw": raw,
        "calibrated": calibrated,
        "delta_calibrated_minus_raw": (
            calibrated - raw if raw is not None and calibrated is not None else None
        ),
    }


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _weighted_mean(values: list[float], weights: list[int]) -> float | None:
    return float(np.average(values, weights=weights)) if values else None


def _reported_aggregation_checks(
    *,
    summary: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    aggregations: dict[str, dict[str, float | None]],
    tolerance: float,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    sources = [
        ("summary.json", summary, "mean_fold_auc", ("summary",)),
        ("calibration_comparison.json", comparison, "pooled_auc", ("overall",)),
    ]
    for source_name, source, aggregation_name, path in sources:
        if source is None:
            continue
        node: Any = source
        for key in path:
            node = node[key]
        recorded_raw = node["raw"]["auc"]
        recorded_calibrated = node["calibrated"]["auc"]
        recomputed = aggregations[aggregation_name]
        raw_delta = float(recorded_raw - recomputed["raw"])
        calibrated_delta = float(recorded_calibrated - recomputed["calibrated"])
        checks.append(
            {
                "source": source_name,
                "aggregation": aggregation_name,
                "recorded_raw_auc": float(recorded_raw),
                "recorded_calibrated_auc": float(recorded_calibrated),
                "recomputed_raw_auc": recomputed["raw"],
                "recomputed_calibrated_auc": recomputed["calibrated"],
                "raw_abs_delta": abs(raw_delta),
                "calibrated_abs_delta": abs(calibrated_delta),
                "passed": abs(raw_delta) <= tolerance
                and abs(calibrated_delta) <= tolerance,
            }
        )
    return checks


def build_auc_audit(
    predictions: pd.DataFrame,
    *,
    summary: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    input_metadata: dict[str, object] | None = None,
    fold_col: str = "fold_id",
    ticker_col: str = "ticker",
    date_col: str = "date",
    label_col: str = "risk_label",
    raw_prob_col: str = "risk_probability",
    calibrated_prob_col: str = "calibrated_risk_probability",
    tolerance: float = DEFAULT_TOLERANCE,
    mapping_tolerance: float = DEFAULT_MAPPING_TOLERANCE,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build overview and per-fold diagnostics for paired AUC invariance."""

    if tolerance <= 0.0 or mapping_tolerance <= 0.0:
        raise ValueError("tolerances must be positive")
    required = {
        fold_col,
        ticker_col,
        date_col,
        label_col,
        raw_prob_col,
        calibrated_prob_col,
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if predictions[fold_col].isna().any():
        raise ValueError(f"{fold_col} must not contain missing values")

    summary_by_fold = _fold_lookup(summary)
    diagnostics: list[dict[str, object]] = []
    raw_frames: list[pd.DataFrame] = []
    calibrated_frames: list[pd.DataFrame] = []
    for fold_id, frame in predictions.groupby(fold_col, sort=True):
        diagnostic, raw_frame, calibrated_frame = _fold_diagnostic(
            frame,
            fold_id=fold_id,
            fold_summary=summary_by_fold.get(_json_scalar(fold_id)),
            fold_col=fold_col,
            ticker_col=ticker_col,
            date_col=date_col,
            label_col=label_col,
            raw_prob_col=raw_prob_col,
            calibrated_prob_col=calibrated_prob_col,
            tolerance=tolerance,
        )
        diagnostics.append(diagnostic)
        raw_frames.append(raw_frame)
        calibrated_frames.append(calibrated_frame)

    valid_pairs = [
        row
        for row in diagnostics
        if row["raw_auc"] is not None and row["calibrated_auc"] is not None
    ]
    raw_fold_auc = [float(row["raw_auc"]) for row in valid_pairs]
    calibrated_fold_auc = [float(row["calibrated_auc"]) for row in valid_pairs]
    fold_weights = [int(row["raw_sample_count"]) for row in valid_pairs]

    all_raw = pd.concat(raw_frames, ignore_index=True)
    all_calibrated = pd.concat(calibrated_frames, ignore_index=True)
    pooled_raw_auc = _safe_auc(
        all_raw["__label"].to_numpy(dtype=int),
        all_raw["__probability"].to_numpy(dtype=float),
    )
    pooled_calibrated_auc = _safe_auc(
        all_calibrated["__label"].to_numpy(dtype=int),
        all_calibrated["__probability"].to_numpy(dtype=float),
    )
    aggregations = {
        "mean_fold_auc": _pair(
            _mean(raw_fold_auc),
            _mean(calibrated_fold_auc),
        ),
        "weighted_mean_fold_auc": _pair(
            _weighted_mean(raw_fold_auc, fold_weights),
            _weighted_mean(calibrated_fold_auc, fold_weights),
        ),
        "pooled_auc": _pair(pooled_raw_auc, pooled_calibrated_auc),
    }

    identical_failures = [
        row["fold_id"]
        for row in diagnostics
        if row["raw_sample_count"] != row["calibrated_sample_count"]
        or row["raw_sample_key_hash"] != row["calibrated_sample_key_hash"]
    ]
    duplicate_failures = [
        row["fold_id"]
        for row in diagnostics
        if row["raw_duplicate_sample_key_count"] != 0
        or row["calibrated_duplicate_sample_key_count"] != 0
    ]
    positive_eligible = [
        row
        for row in diagnostics
        if row["coefficient_sign"] == "positive"
        and row["raw_valid_auc"]
        and row["calibrated_valid_auc"]
    ]
    positive_failures = [
        row["fold_id"]
        for row in positive_eligible
        if abs(float(row["auc_delta"])) > tolerance
        or int(row["ranking_inversion_count"]) != 0
        or row["spearman_rank_correlation"] is None
        or abs(float(row["spearman_rank_correlation"]) - 1.0) > tolerance
    ]
    negative_eligible = [
        row
        for row in diagnostics
        if row["coefficient_sign"] == "negative"
        and row["raw_valid_auc"]
        and row["calibrated_valid_auc"]
    ]
    negative_failures = [
        row["fold_id"]
        for row in negative_eligible
        if abs(float(row["calibrated_auc"]) - (1.0 - float(row["raw_auc"])))
        > tolerance
        or int(row["ranking_inversion_count"])
        != int(row["strict_raw_order_pair_count"])
        or row["spearman_rank_correlation"] is None
        or abs(float(row["spearman_rank_correlation"]) + 1.0) > tolerance
    ]
    single_class_failures = [
        row["fold_id"]
        for row in diagnostics
        if row["raw_single_class"] != row["calibrated_single_class"]
        or row["raw_valid_auc"] != row["calibrated_valid_auc"]
        or (
            row["raw_single_class"]
            and (row["raw_auc"] is not None or row["calibrated_auc"] is not None)
        )
    ]
    mapping_failures = [
        row["fold_id"]
        for row in diagnostics
        if row["platt_reconstruction_max_abs_error"] is None
        or float(row["platt_reconstruction_max_abs_error"]) > mapping_tolerance
    ]
    reported_checks = _reported_aggregation_checks(
        summary=summary,
        comparison=comparison,
        aggregations=aggregations,
        tolerance=tolerance,
    )
    reported_failures = [
        check["source"] for check in reported_checks if not bool(check["passed"])
    ]

    invariants = {
        "identical_sample_keys": {
            "passed": not identical_failures,
            "failed_fold_ids": identical_failures,
        },
        "unique_sample_keys": {
            "passed": not duplicate_failures,
            "failed_fold_ids": duplicate_failures,
        },
        "positive_coefficient_auc_invariance": {
            "passed": not positive_failures,
            "eligible_fold_count": len(positive_eligible),
            "failed_fold_ids": positive_failures,
            "tolerance": tolerance,
        },
        "negative_coefficient_rank_reversal": {
            "passed": not negative_failures,
            "eligible_fold_count": len(negative_eligible),
            "failed_fold_ids": negative_failures,
            "expected_relation": "calibrated_auc = 1 - raw_auc",
            "tolerance": tolerance,
        },
        "single_class_auc_consistency": {
            "passed": not single_class_failures,
            "single_class_fold_count": sum(
                bool(row["raw_single_class"]) for row in diagnostics
            ),
            "failed_fold_ids": single_class_failures,
        },
        "platt_mapping_reconstruction": {
            "passed": not mapping_failures,
            "failed_fold_ids": mapping_failures,
            "max_abs_error_tolerance": mapping_tolerance,
        },
        "reported_aggregations_match_recomputation": {
            "passed": not reported_failures,
            "checks": reported_checks,
            "failed_sources": reported_failures,
        },
    }
    all_passed = all(bool(item["passed"]) for item in invariants.values())

    negative_ids = [row["fold_id"] for row in negative_eligible]
    mapping_errors = [
        float(row["platt_reconstruction_max_abs_error"])
        for row in diagnostics
        if row["platt_reconstruction_max_abs_error"] is not None
    ]
    mean_delta = aggregations["mean_fold_auc"]["delta_calibrated_minus_raw"]
    negative_delta_contribution = (
        sum(float(row["auc_delta"]) for row in negative_eligible) / len(valid_pairs)
        if valid_pairs
        else None
    )
    negative_folds_explain_mean_delta = (
        mean_delta is not None
        and negative_delta_contribution is not None
        and abs(mean_delta - negative_delta_contribution) <= tolerance
        and not positive_failures
    )

    overview = {
        "schema_version": 1,
        "audit": "raw-versus-platt-auc-invariance",
        "input": input_metadata or {},
        "sample_key_columns": [fold_col, ticker_col, date_col, label_col],
        "coefficient_source": (
            "Reconstructed by least squares from "
            "logit(calibrated_probability) = coefficient * raw_probability + intercept."
        ),
        "fold_count": len(diagnostics),
        "valid_auc_fold_count": len(valid_pairs),
        "sample_totals": {
            "raw_sample_count": int(len(all_raw)),
            "calibrated_sample_count": int(len(all_calibrated)),
            "raw_positive_count": int(all_raw["__label"].sum()),
            "calibrated_positive_count": int(all_calibrated["__label"].sum()),
            "raw_sample_key_hash": _sample_key_hash(all_raw["__sample_key"]),
            "calibrated_sample_key_hash": _sample_key_hash(
                all_calibrated["__sample_key"]
            ),
        },
        "mapping_summary": {
            "positive_coefficient_fold_count": sum(
                row["coefficient_sign"] == "positive" for row in diagnostics
            ),
            "negative_coefficient_fold_count": len(negative_ids),
            "zero_coefficient_fold_count": sum(
                row["coefficient_sign"] == "zero" for row in diagnostics
            ),
            "unavailable_coefficient_fold_count": sum(
                row["coefficient_sign"] == "unavailable" for row in diagnostics
            ),
            "max_platt_reconstruction_abs_error": (
                max(mapping_errors) if mapping_errors else None
            ),
        },
        "aggregation_definitions": {
            "mean_fold_auc": "Unweighted arithmetic mean of valid per-fold AUC values.",
            "weighted_mean_fold_auc": (
                "Mean of valid per-fold AUC values weighted by each fold's raw sample count."
            ),
            "pooled_auc": (
                "AUC after concatenating all fold predictions; fold-specific Platt mappings "
                "can change cross-fold ordering."
            ),
        },
        "auc_aggregations": aggregations,
        "invariants": invariants,
        "all_invariants_passed": all_passed,
        "finding": {
            "negative_coefficient_fold_ids": negative_ids,
            "negative_coefficient_fold_count": len(negative_ids),
            "mean_fold_auc_delta": mean_delta,
            "negative_fold_mean_delta_contribution": negative_delta_contribution,
            "negative_folds_explain_mean_fold_auc_delta": (
                negative_folds_explain_mean_delta
            ),
            "conclusion": (
                "The reported mean-fold AUC difference is explained by folds with a "
                "negative Platt coefficient; positive-coefficient folds preserve AUC."
            ),
            "pooled_auc_note": (
                "Pooled AUC is a separate cross-fold ranking statistic and is not the "
                "AUC aggregation reported in the Experiment 007 main table."
            ),
        },
    }
    fold_document = {
        "schema_version": 1,
        "audit": "fold-calibrator-diagnostics",
        "input": input_metadata or {},
        "folds": diagnostics,
    }
    return overview, fold_document


def assert_auc_audit_invariants(overview: dict[str, object]) -> None:
    """Raise when any audit invariant failed."""

    invariants = overview["invariants"]
    assert isinstance(invariants, dict)
    failures = [
        name
        for name, result in invariants.items()
        if isinstance(result, dict) and not bool(result["passed"])
    ]
    if failures:
        raise ValueError(f"AUC audit invariant failures: {', '.join(failures)}")


def run_audit(args: argparse.Namespace) -> dict[str, object]:
    """Load artifacts, validate invariants, and write the two audit JSON files."""

    predictions = pd.read_csv(args.input, dtype={args.ticker_col: "string"})
    summary = json.loads(args.summary.read_text(encoding="utf-8")) if args.summary else None
    comparison = (
        json.loads(args.comparison.read_text(encoding="utf-8"))
        if args.comparison
        else None
    )
    input_metadata: dict[str, object] = {
        "predictions_path": str(args.input),
        "predictions_sha256": _sha256_file(args.input),
    }
    if args.summary is not None:
        input_metadata.update(
            {
                "summary_path": str(args.summary),
                "summary_sha256": _sha256_file(args.summary),
            }
        )
    if args.comparison is not None:
        input_metadata.update(
            {
                "comparison_path": str(args.comparison),
                "comparison_sha256": _sha256_file(args.comparison),
            }
        )

    overview, fold_document = build_auc_audit(
        predictions,
        summary=summary,
        comparison=comparison,
        input_metadata=input_metadata,
        fold_col=args.fold_col,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        label_col=args.label_col,
        raw_prob_col=args.raw_prob_col,
        calibrated_prob_col=args.calibrated_prob_col,
        tolerance=args.tolerance,
        mapping_tolerance=args.mapping_tolerance,
    )
    assert_auc_audit_invariants(overview)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overview_path = args.output_dir / "auc_invariance.json"
    diagnostics_path = args.output_dir / "fold_calibrator_diagnostics.json"
    overview_path.write_text(
        json.dumps(overview, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    diagnostics_path.write_text(
        json.dumps(fold_document, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "auc_invariance": overview,
        "auc_invariance_path": str(overview_path),
        "fold_calibrator_diagnostics_path": str(diagnostics_path),
    }


def main() -> None:
    result = run_audit(parse_args())
    overview = result["auc_invariance"]
    assert isinstance(overview, dict)
    print(
        json.dumps(
            {
                "all_invariants_passed": overview["all_invariants_passed"],
                "finding": overview["finding"],
                "auc_invariance_path": result["auc_invariance_path"],
                "fold_calibrator_diagnostics_path": result[
                    "fold_calibrator_diagnostics_path"
                ],
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
