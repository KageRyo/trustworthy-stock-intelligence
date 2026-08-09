"""Schema-first TAI audit artifacts for model-run evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

AuditStatus = Literal["met", "partial", "open"]
TAIDimension = Literal[
    "accuracy",
    "reliability",
    "safety",
    "resilience",
    "transparency",
    "accountability",
    "explainability",
    "autonomy",
    "privacy",
    "fairness",
    "security",
]


class TAIDimensionAssessment(BaseModel):
    """Evidence and remaining risks for one TAI dimension."""

    status: AuditStatus
    evidence: list[str] = Field(default_factory=list)
    open_risks: list[str] = Field(default_factory=list)


class TAIDataProvenance(BaseModel):
    """Data identity and freshness evidence available to the audit."""

    input_path: str | None = None
    input_sha256: str | None = None
    data_as_of: str | None = None
    feature_interval: str | None = None
    ticker_count: int | None = None
    row_count: int | None = None
    universe_membership_status: str | None = None


class TAIModelProvenance(BaseModel):
    """Model and temporal-validation evidence available to the audit."""

    model_type: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    fold_count: int | None = None
    horizon: int | None = None
    purge_size: int | None = None
    calibration_method: str | None = None
    threshold_objective: str | None = None


class TAIMetrics(BaseModel):
    """Aggregate calibrated and tuned metrics copied from the run summary."""

    calibrated: dict[str, float] = Field(default_factory=dict)
    tuned: dict[str, float] = Field(default_factory=dict)
    warning_quality: dict[str, float] = Field(default_factory=dict)


class TAIAuditArtifact(BaseModel):
    """Versioned, conservative audit record for one model run."""

    schema_version: Literal["tai_audit.v1"] = "tai_audit.v1"
    generated_at_utc: str
    run_id: str
    data: TAIDataProvenance
    model: TAIModelProvenance
    metrics: TAIMetrics
    dimensions: dict[TAIDimension, TAIDimensionAssessment]
    known_limitations: list[str]
    open_risks: list[str]


def build_tai_audit(
    training_summary: Mapping[str, object],
    *,
    data_manifest: Mapping[str, object] | None = None,
    warning_evaluation: Mapping[str, object] | None = None,
    run_id: str | None = None,
    data_as_of: str | None = None,
    feature_interval: str | None = "1d",
    known_limitations: Sequence[str] = (),
) -> TAIAuditArtifact:
    """Build a conservative TAI audit from structured run artifacts.

    Missing evidence is reported as an open risk. The artifact must not be read
    as an assertion that an unchecked TAI control is satisfied.
    """

    summary_metrics = _mapping(training_summary.get("summary"))
    calibrated = _numeric_metrics(_mapping(summary_metrics.get("calibrated")))
    tuned = _numeric_metrics(_mapping(summary_metrics.get("tuned")))
    warning_quality = _numeric_metrics(
        _mapping(_mapping(warning_evaluation).get("overall"))
    )
    membership_status = _membership_status(training_summary.get("universe_membership"))
    data = TAIDataProvenance(
        input_path=_optional_string(training_summary.get("input")),
        input_sha256=_optional_string(training_summary.get("input_sha256")),
        data_as_of=data_as_of or _manifest_timestamp(data_manifest),
        feature_interval=feature_interval,
        ticker_count=_optional_int(_mapping(data_manifest).get("downloaded_ticker_count")),
        row_count=_optional_int(_mapping(data_manifest).get("row_count")),
        universe_membership_status=membership_status,
    )
    model = TAIModelProvenance(
        model_type=_optional_string(training_summary.get("model_type")),
        feature_columns=_string_list(training_summary.get("feature_columns")),
        fold_count=_optional_int(training_summary.get("fold_count")),
        horizon=_optional_int(training_summary.get("horizon")),
        purge_size=_optional_int(training_summary.get("purge_size")),
        calibration_method=_optional_string(training_summary.get("calibration_method")),
        threshold_objective=_optional_string(training_summary.get("threshold_objective")),
    )
    metrics = TAIMetrics(calibrated=calibrated, tuned=tuned, warning_quality=warning_quality)
    limitations = list(known_limitations)
    risks: list[str] = []
    accuracy_risks: list[str] = []

    if data.data_as_of is None:
        risks.append("Data freshness is unknown because no data manifest or --data-as-of was supplied.")
    if data.universe_membership_status in {None, "not_supplied"}:
        risks.append("Point-in-time universe membership was not supplied for this run.")
    if not warning_quality:
        risk = "Warning-level quality metrics were not supplied to the TAI audit."
        risks.append(risk)
        accuracy_risks.append(risk)
    if not _mapping(training_summary.get("trust_config")):
        risks.append("Trust and uncertainty configuration were not supplied to the TAI audit.")
    tuned_fdr = tuned.get("false_discovery_rate")
    if tuned_fdr is not None and tuned_fdr >= 0.5:
        risk = f"Tuned false-discovery rate is high ({tuned_fdr:.4f})."
        risks.append(risk)
        accuracy_risks.append(risk)

    dimensions: dict[TAIDimension, TAIDimensionAssessment] = {
        "accuracy": _accuracy_assessment(metrics, accuracy_risks),
        "reliability": _reliability_assessment(model),
        "safety": _safety_assessment(tuned_fdr),
        "resilience": _resilience_assessment(data),
        "transparency": _transparency_assessment(data, model),
        "accountability": _accountability_assessment(model, limitations),
        "explainability": _explainability_assessment(model),
        "autonomy": _partial("Run artifact records risk-model evidence only.", "Human-over-the-loop UI evidence is not supplied to this audit."),
        "privacy": _partial("The artifact contains aggregate metadata rather than raw rows.", "Data minimization and access controls require deployment evidence."),
        "fairness": _fairness_assessment(data),
        "security": _partial("Input SHA-256 provides an integrity reference.", "Dependency, credential, and deployment-control evidence is not supplied to this audit."),
    }
    return TAIAuditArtifact(
        generated_at_utc=datetime.now(UTC).isoformat(),
        run_id=run_id or _default_run_id(data, model),
        data=data,
        model=model,
        metrics=metrics,
        dimensions=dimensions,
        known_limitations=_unique(limitations),
        open_risks=_unique(risks + _dimension_risks(dimensions)),
    )


def render_tai_audit_markdown(audit: TAIAuditArtifact) -> str:
    """Render a compact, human-readable companion to the JSON audit."""

    lines = [
        "# Trustworthy AI Audit",
        "",
        f"- Run ID: `{audit.run_id}`",
        f"- Model: `{audit.model.model_type or 'unknown'}`",
        f"- Data as of: `{audit.data.data_as_of or 'unknown'}`",
        f"- Feature interval: `{audit.data.feature_interval or 'unknown'}`",
        "",
        "| Dimension | Status | Evidence | Open risks |",
        "| --- | --- | --- | --- |",
    ]
    for name, assessment in audit.dimensions.items():
        evidence = "; ".join(assessment.evidence) or "—"
        risks = "; ".join(assessment.open_risks) or "—"
        lines.append(f"| {name} | {assessment.status} | {evidence} | {risks} |")
    lines.extend(["", "## Known Limitations", ""])
    lines.extend(f"- {item}" for item in audit.known_limitations or ["None supplied."])
    lines.extend(["", "## Open Risks", ""])
    lines.extend(f"- {item}" for item in audit.open_risks or ["None identified from supplied artifacts."])
    return "\n".join(lines) + "\n"


def _accuracy_assessment(metrics: TAIMetrics, risks: list[str]) -> TAIDimensionAssessment:
    required = {"auc", "pr_auc", "brier_score", "ece"}
    if required.issubset(metrics.calibrated):
        evidence = [
            "Calibrated AUC, PR-AUC, Brier score, and ECE are recorded.",
            f"Calibrated AUC: {metrics.calibrated['auc']:.4f}.",
        ]
        return TAIDimensionAssessment(status="partial", evidence=evidence, open_risks=list(risks))
    return TAIDimensionAssessment(
        status="open",
        open_risks=["Calibrated AUC, PR-AUC, Brier score, and ECE are incomplete."],
    )


def _reliability_assessment(model: TAIModelProvenance) -> TAIDimensionAssessment:
    if model.fold_count and model.purge_size is not None:
        return _partial(
            f"Temporal validation records {model.fold_count} folds with purge size {model.purge_size}.",
            "Provider outage, drift, and perturbation evidence is not supplied to this audit.",
        )
    return TAIDimensionAssessment(status="open", open_risks=["Temporal-validation evidence is incomplete."])


def _safety_assessment(tuned_fdr: float | None) -> TAIDimensionAssessment:
    if tuned_fdr is None:
        return TAIDimensionAssessment(status="open", open_risks=["Tuned false-discovery rate is unavailable."])
    if tuned_fdr >= 0.5:
        return TAIDimensionAssessment(
            status="open",
            evidence=[f"Tuned false-discovery rate: {tuned_fdr:.4f}."],
            open_risks=["High false-discovery rate makes the policy non-actionable."],
        )
    return _partial(
        f"Tuned false-discovery rate: {tuned_fdr:.4f}.",
        "Safety still requires stale-data and low-trust serving controls.",
    )


def _resilience_assessment(data: TAIDataProvenance) -> TAIDimensionAssessment:
    if data.feature_interval and data.ticker_count:
        return _partial(
            f"Input declares {data.feature_interval} bars for {data.ticker_count} tickers.",
            "Provider-recovery and scheduled-ingestion evidence is not supplied to this audit.",
        )
    return TAIDimensionAssessment(status="open", open_risks=["Interval or ticker coverage evidence is missing."])


def _transparency_assessment(data: TAIDataProvenance, model: TAIModelProvenance) -> TAIDimensionAssessment:
    if data.input_sha256 and model.feature_columns and model.calibration_method:
        return TAIDimensionAssessment(
            status="met",
            evidence=[
                "Input fingerprint, feature columns, calibration method, and temporal protocol are recorded.",
                f"Input SHA-256: {data.input_sha256}.",
            ],
        )
    return TAIDimensionAssessment(
        status="partial",
        open_risks=["Input, feature, calibration, or temporal-protocol provenance is incomplete."],
    )


def _accountability_assessment(
    model: TAIModelProvenance, limitations: list[str]
) -> TAIDimensionAssessment:
    if model.model_type and limitations:
        return _partial(
            "Model type and known limitations are recorded.",
            "Owner, approval, and remediation records require project-process evidence.",
        )
    return TAIDimensionAssessment(
        status="open",
        open_risks=["Model metadata or known limitations were not supplied."],
    )


def _explainability_assessment(model: TAIModelProvenance) -> TAIDimensionAssessment:
    if model.feature_columns:
        return _partial(
            "Feature columns are recorded.",
            "Run-level feature attribution and reason-code evidence is not supplied.",
        )
    return TAIDimensionAssessment(status="open", open_risks=["Feature or explanation evidence is missing."])


def _fairness_assessment(data: TAIDataProvenance) -> TAIDimensionAssessment:
    if data.ticker_count and data.universe_membership_status not in {None, "not_supplied"}:
        return _partial(
            "Ticker-count and universe-membership metadata are recorded.",
            "Sector, liquidity, market-cap, and provider-coverage slices are not supplied.",
        )
    return TAIDimensionAssessment(
        status="open",
        open_risks=["Coverage-bias and point-in-time membership evidence is missing."],
    )


def _partial(evidence: str, risk: str) -> TAIDimensionAssessment:
    return TAIDimensionAssessment(status="partial", evidence=[evidence], open_risks=[risk])


def _mapping(value: object | None) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _numeric_metrics(values: Mapping[str, object]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in values.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[str(key)] = float(value)
    return metrics


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _membership_status(value: object) -> str | None:
    membership = _mapping(value)
    return _optional_string(membership.get("status")) or _optional_string(membership.get("name"))


def _manifest_timestamp(manifest: Mapping[str, object] | None) -> str | None:
    values = _mapping(manifest)
    return _optional_string(values.get("data_as_of")) or _optional_string(values.get("downloaded_at_utc"))


def _default_run_id(data: TAIDataProvenance, model: TAIModelProvenance) -> str:
    model_name = model.model_type or "unknown-model"
    input_suffix = data.input_sha256[:12] if data.input_sha256 else "unknown-input"
    return f"{model_name}-{input_suffix}"


def _dimension_risks(
    dimensions: Mapping[TAIDimension, TAIDimensionAssessment],
) -> list[str]:
    return [risk for assessment in dimensions.values() for risk in assessment.open_risks]


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
