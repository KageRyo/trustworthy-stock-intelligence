"""Typed import and coverage audits for external membership archives.

The importer is deliberately metadata-first: it accepts an explicitly mapped
external table, emits a versioned v2 membership universe, and exposes only
counts and fingerprints in its reports.  Raw licensed rows remain at the
caller-provided path and are never embedded in a manifest.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from tsi.data.universe import (
    PointInTimeSecurityMembership,
    PointInTimeUniverseV2,
)

MEMBERSHIP_IMPORT_SCHEMA_VERSION = "membership_import.v1"
COVERAGE_AUDIT_SCHEMA_VERSION = "membership_coverage_audit.v1"
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


class MembershipColumnMapping(BaseModel):
    """Map arbitrary archive columns to the canonical v2 membership fields."""

    model_config = ConfigDict(extra="forbid")

    mapping_version: str = Field(min_length=1)
    security_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    valid_from: str = Field(min_length=1)
    known_at: str = Field(min_length=1)
    valid_to: str | None = None
    provider_symbol: str | None = None
    market: str | None = None
    exchange: str | None = None
    change_reason: str | None = None
    interval_semantics: Literal["half_open"] = "half_open"
    empty_valid_to_means_open: bool = True

    @field_validator(
        "mapping_version",
        "security_id",
        "ticker",
        "valid_from",
        "known_at",
        "valid_to",
        "provider_symbol",
        "market",
        "exchange",
        "change_reason",
    )
    @classmethod
    def normalize_column_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class MembershipImportConfig(BaseModel):
    """Provenance and mapping contract for one archive import."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_license: str = Field(min_length=1)
    retrieved_at: datetime
    snapshot_date: date
    mapping: MembershipColumnMapping

    @field_validator("name", "source", "source_license")
    @classmethod
    def normalize_metadata(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("metadata values must not be empty")
        return normalized

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieval_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


ImportIssueSeverity = Literal["error", "warning"]


class MembershipImportIssue(BaseModel):
    """A redacted import finding; it contains no provider row values."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: ImportIssueSeverity
    row_number: int | None = Field(default=None, ge=2)
    field: str | None = None
    message: str = Field(min_length=1)


class MembershipImportReport(BaseModel):
    """Public import report containing provenance, counts, and issue metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = MEMBERSHIP_IMPORT_SCHEMA_VERSION
    status: Literal["valid", "invalid"]
    input_sha256: str
    source: str
    source_license: str
    retrieved_at: str
    snapshot_date: str
    mapping_version: str
    row_count: int = Field(ge=0)
    accepted_row_count: int = Field(ge=0)
    issue_counts: dict[str, int]
    issues: list[MembershipImportIssue]
    universe_manifest: dict[str, object] | None = None


class MembershipImportError(ValueError):
    """Raised when an archive cannot be converted into a safe identity map."""

    def __init__(self, report: MembershipImportReport) -> None:
        self.report = report
        super().__init__(
            "membership archive failed closed: "
            + ", ".join(f"{code}={count}" for code, count in sorted(report.issue_counts.items()))
        )


@dataclass(frozen=True)
class ImportedMembershipArchive:
    """Typed valid archive plus its redacted import report."""

    universe: PointInTimeUniverseV2
    report: MembershipImportReport


class MembershipCoverageAudit(BaseModel):
    """Coverage counts separating missing data from nonmembership."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = COVERAGE_AUDIT_SCHEMA_VERSION
    as_of: str
    membership_sha256: str
    ohlcv_key_sha256: str
    membership_count: int = Field(ge=0)
    active_membership_count: int = Field(ge=0)
    inactive_membership_count: int = Field(ge=0)
    removed_or_delisted_membership_count: int = Field(ge=0)
    coverage_start: str | None = None
    coverage_end: str | None = None
    ohlcv_row_count: int = Field(ge=0)
    complete_ohlcv_row_count: int = Field(ge=0)
    incomplete_ohlcv_row_count: int = Field(ge=0)
    missing_ohlcv_by_column: dict[str, int]
    active_memberships_with_bars: int = Field(ge=0)
    active_memberships_missing_bars: int = Field(ge=0)
    inactive_memberships_with_bars: int = Field(ge=0)
    inactive_memberships_missing_bars: int = Field(ge=0)
    removed_or_delisted_with_bars: int = Field(ge=0)
    removed_or_delisted_missing_bars: int = Field(ge=0)
    unavailable_data_membership_count: int = Field(ge=0)
    nonmembership_row_count: int = Field(ge=0)
    unmatched_identifier_count: int = Field(ge=0)
    unmatched_identifier_row_count: int = Field(ge=0)
    unmatched_identifier_sha256: str
    limitations: list[str]


def import_membership_archive(
    path: str | Path,
    config: MembershipImportConfig,
) -> ImportedMembershipArchive:
    """Import an explicitly mapped archive and fail closed on identity errors."""

    archive_path = Path(path)
    input_sha256 = _file_sha256(archive_path)
    frame = pd.read_csv(archive_path, dtype="string")
    issues: list[MembershipImportIssue] = []
    missing_columns = _missing_columns(frame, config.mapping)
    for column in missing_columns:
        issues.append(
            MembershipImportIssue(
                code="missing_column",
                severity="error",
                field=column,
                message="mapped source column is not present in the archive",
            )
        )

    memberships: list[PointInTimeSecurityMembership] = []
    seen_rows: set[tuple[object, ...]] = set()
    if not missing_columns:
        for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
            parsed = _parse_membership_row(row, config.mapping, row_number, issues)
            if parsed is None:
                continue
            canonical_key = tuple(parsed.model_dump(mode="json").items())
            if canonical_key in seen_rows:
                issues.append(
                    MembershipImportIssue(
                        code="duplicate_row",
                        severity="error",
                        row_number=row_number,
                        message="canonical membership row is duplicated",
                    )
                )
                continue
            seen_rows.add(canonical_key)
            memberships.append(parsed)

    universe: PointInTimeUniverseV2 | None = None
    if memberships:
        try:
            universe = PointInTimeUniverseV2(
                name=config.name,
                source=config.source,
                source_license=config.source_license,
                memberships=memberships,
            )
        except ValueError as exc:
            message = str(exc)
            if "overlapping identity" in message:
                code = "overlap"
            elif "ambiguous" in message:
                code = "ambiguous_symbol"
            else:
                code = "invalid_identity_mapping"
            issues.append(
                MembershipImportIssue(
                    code=code,
                    severity="error",
                    message="canonical identity validation failed: " + message,
                )
            )

    if universe is not None:
        issues.extend(_identity_gap_issues(universe))
    if not memberships:
        issues.append(
            MembershipImportIssue(
                code="empty_archive",
                severity="error",
                message="the archive contains no valid membership rows",
            )
        )
    issue_counts = dict(Counter(issue.code for issue in issues))
    status: Literal["valid", "invalid"] = (
        "invalid" if any(issue.severity == "error" for issue in issues) else "valid"
    )
    report = MembershipImportReport(
        status=status,
        input_sha256=input_sha256,
        source=config.source,
        source_license=config.source_license,
        retrieved_at=config.retrieved_at.isoformat(),
        snapshot_date=config.snapshot_date.isoformat(),
        mapping_version=config.mapping.mapping_version,
        row_count=len(frame),
        accepted_row_count=len(memberships) if universe is not None else 0,
        issue_counts=issue_counts,
        issues=issues,
        universe_manifest=_import_manifest(config, universe, input_sha256),
    )
    if report.status == "invalid" or universe is None:
        raise MembershipImportError(report)
    return ImportedMembershipArchive(universe=universe, report=report)


def audit_membership_coverage(
    universe: PointInTimeUniverseV2,
    ohlcv: pd.DataFrame,
    *,
    as_of: date | str | None = None,
    date_column: str = "date",
    ticker_column: str = "ticker",
) -> MembershipCoverageAudit:
    """Audit OHLCV availability without confusing it with membership facts."""

    required_columns = {date_column, ticker_column, *OHLCV_COLUMNS}
    missing_columns = sorted(required_columns - set(ohlcv.columns))
    if missing_columns:
        raise ValueError("OHLCV frame is missing columns: " + ", ".join(missing_columns))
    dates = pd.to_datetime(ohlcv[date_column], errors="coerce")
    tickers = ohlcv[ticker_column].astype("string").str.strip()
    if dates.isna().any():
        raise ValueError("OHLCV frame contains invalid dates")

    data_dates = dates.dt.date
    data_max = data_dates.max() if len(data_dates) else None
    inferred_as_of = max(
        data_max or min(item.valid_from for item in universe.memberships),
        max(item.valid_from for item in universe.memberships),
    )
    evaluation_date = (
        _parse_date(as_of, field_name="as_of") if as_of is not None else inferred_as_of
    )
    active_intervals = [
        item
        for item in universe.memberships
        if item.valid_from <= evaluation_date
        and (item.valid_to is None or evaluation_date < item.valid_to)
        and item.known_at <= evaluation_date
    ]
    inactive_intervals = [item for item in universe.memberships if item not in active_intervals]
    removed_intervals = [
        item
        for item in universe.memberships
        if item.valid_to is not None and item.valid_to <= evaluation_date
    ]

    numeric_missing = pd.DataFrame(
        {
            column: ohlcv[column].isna() | pd.to_numeric(ohlcv[column], errors="coerce").isna()
            for column in OHLCV_COLUMNS
        }
    )
    complete_mask = ~numeric_missing.any(axis=1)
    missing_by_column = {column: int(numeric_missing[column].sum()) for column in OHLCV_COLUMNS}
    coverage_start = data_dates.min() if len(data_dates) else None
    coverage_end = data_dates.max() if len(data_dates) else None
    with_bars: dict[str, bool] = {}
    for membership in universe.memberships:
        mask = (tickers == membership.ticker) & (
            (data_dates >= membership.valid_from)
            & (
                membership.valid_to is None
                if membership.valid_to is None
                else data_dates < membership.valid_to
            )
        )
        with_bars[_membership_key(membership)] = bool(mask.any())

    known_tickers = {membership.ticker for membership in universe.memberships}
    nonmembership_rows = 0
    unmatched_rows = 0
    unmatched_tickers: set[str] = set()
    for ticker, row_date in zip(tickers, data_dates, strict=True):
        normalized_ticker = "" if pd.isna(ticker) else str(ticker)
        matching = [
            membership
            for membership in universe.memberships
            if membership.ticker == normalized_ticker
            and membership.valid_from <= row_date
            and (membership.valid_to is None or row_date < membership.valid_to)
            and membership.known_at <= row_date
        ]
        if matching:
            continue
        if normalized_ticker in known_tickers:
            nonmembership_rows += 1
        else:
            unmatched_rows += 1
            unmatched_tickers.add(normalized_ticker)

    active_with = sum(with_bars[_membership_key(item)] for item in active_intervals)
    inactive_with = sum(with_bars[_membership_key(item)] for item in inactive_intervals)
    removed_with = sum(with_bars[_membership_key(item)] for item in removed_intervals)
    active_missing = len(active_intervals) - active_with
    inactive_missing = len(inactive_intervals) - inactive_with
    removed_missing = len(removed_intervals) - removed_with
    ohlcv_key_sha256 = _ohlcv_key_fingerprint(tickers, data_dates)
    return MembershipCoverageAudit(
        as_of=evaluation_date.isoformat(),
        membership_sha256=universe.membership_fingerprint(),
        ohlcv_key_sha256=ohlcv_key_sha256,
        membership_count=len(universe.memberships),
        active_membership_count=len(active_intervals),
        inactive_membership_count=len(inactive_intervals),
        removed_or_delisted_membership_count=len(removed_intervals),
        coverage_start=coverage_start.isoformat() if coverage_start is not None else None,
        coverage_end=coverage_end.isoformat() if coverage_end is not None else None,
        ohlcv_row_count=len(ohlcv),
        complete_ohlcv_row_count=int(complete_mask.sum()),
        incomplete_ohlcv_row_count=int((~complete_mask).sum()),
        missing_ohlcv_by_column=missing_by_column,
        active_memberships_with_bars=active_with,
        active_memberships_missing_bars=active_missing,
        inactive_memberships_with_bars=inactive_with,
        inactive_memberships_missing_bars=inactive_missing,
        removed_or_delisted_with_bars=removed_with,
        removed_or_delisted_missing_bars=removed_missing,
        unavailable_data_membership_count=active_missing,
        nonmembership_row_count=nonmembership_rows,
        unmatched_identifier_count=len(unmatched_tickers),
        unmatched_identifier_row_count=unmatched_rows,
        unmatched_identifier_sha256=_string_set_fingerprint(unmatched_tickers),
        limitations=[
            "A missing bar is classified as data unavailability, not evidence of nonmembership.",
            "The audit reports provider coverage counts; it does not establish survivorship-bias absence.",
            "Rows outside the archive are unmatched identifiers and require an explicit archive decision.",
        ],
    )


def _missing_columns(frame: pd.DataFrame, mapping: MembershipColumnMapping) -> list[str]:
    mapped = {
        mapping.security_id,
        mapping.ticker,
        mapping.valid_from,
        mapping.known_at,
        mapping.valid_to,
        mapping.provider_symbol,
        mapping.market,
        mapping.exchange,
        mapping.change_reason,
    }
    return sorted(column for column in mapped if column is not None and column not in frame.columns)


def _parse_membership_row(
    row: pd.Series,
    mapping: MembershipColumnMapping,
    row_number: int,
    issues: list[MembershipImportIssue],
) -> PointInTimeSecurityMembership | None:
    security_id = _text(row[mapping.security_id])
    ticker = _text(row[mapping.ticker])
    if security_id is None or ticker is None:
        issues.append(
            MembershipImportIssue(
                code="missing_identifier",
                severity="error",
                row_number=row_number,
                field="security_id" if security_id is None else "ticker",
                message="security_id and ticker are required",
            )
        )
        return None
    valid_from = _date_or_issue(row[mapping.valid_from], "valid_from", row_number, issues)
    known_at = _date_or_issue(row[mapping.known_at], "known_at", row_number, issues)
    if valid_from is None or known_at is None:
        return None
    valid_to: date | None = None
    if mapping.valid_to is not None:
        raw_valid_to = _text(row[mapping.valid_to])
        if raw_valid_to is not None or not mapping.empty_valid_to_means_open:
            valid_to = _date_or_issue(raw_valid_to, "valid_to", row_number, issues)
            if raw_valid_to is not None and valid_to is None:
                return None
    if valid_to is not None and valid_to <= valid_from:
        issues.append(
            MembershipImportIssue(
                code="invalid_effective_date",
                severity="error",
                row_number=row_number,
                field="valid_to",
                message="valid_to must be later than valid_from",
            )
        )
        return None
    try:
        return PointInTimeSecurityMembership(
            security_id=security_id,
            ticker=ticker,
            provider_symbol=_optional_mapped_value(row, mapping.provider_symbol),
            market=_optional_mapped_value(row, mapping.market) or "",
            exchange=_optional_mapped_value(row, mapping.exchange) or "",
            valid_from=valid_from,
            valid_to=valid_to,
            known_at=known_at,
            change_reason=_optional_mapped_value(row, mapping.change_reason),
        )
    except ValueError as exc:
        issues.append(
            MembershipImportIssue(
                code="invalid_identity_mapping",
                severity="error",
                row_number=row_number,
                message="canonical identity row failed validation: " + str(exc),
            )
        )
        return None


def _date_or_issue(
    value: object,
    field: str,
    row_number: int,
    issues: list[MembershipImportIssue],
) -> date | None:
    normalized = _text(value)
    if normalized is None:
        issues.append(
            MembershipImportIssue(
                code="missing_effective_date" if field != "known_at" else "missing_known_at",
                severity="error",
                row_number=row_number,
                field=field,
                message=f"{field} is required",
            )
        )
        return None
    try:
        return _parse_date(normalized, field_name=field)
    except ValueError as exc:
        issues.append(
            MembershipImportIssue(
                code="invalid_effective_date" if field != "known_at" else "invalid_known_at",
                severity="error",
                row_number=row_number,
                field=field,
                message=str(exc),
            )
        )
        return None


def _identity_gap_issues(universe: PointInTimeUniverseV2) -> list[MembershipImportIssue]:
    by_identity: dict[str, list[PointInTimeSecurityMembership]] = {}
    for membership in universe.memberships:
        by_identity.setdefault(membership.security_id, []).append(membership)
    issues: list[MembershipImportIssue] = []
    for security_id, memberships in by_identity.items():
        ordered = sorted(memberships, key=lambda item: item.valid_from)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.valid_to is not None and current.valid_from > previous.valid_to:
                issues.append(
                    MembershipImportIssue(
                        code="identity_gap",
                        severity="warning",
                        message=(
                            f"security_id {security_id!r} has a non-contiguous effective interval; "
                            "this may represent removal/re-entry or unavailable archive coverage"
                        ),
                    )
                )
    return issues


def _import_manifest(
    config: MembershipImportConfig,
    universe: PointInTimeUniverseV2 | None,
    input_sha256: str,
) -> dict[str, object] | None:
    if universe is None:
        return None
    return {
        **universe.manifest(),
        "input_sha256": input_sha256,
        "retrieved_at": config.retrieved_at.isoformat(),
        "snapshot_date": config.snapshot_date.isoformat(),
        "mapping_version": config.mapping.mapping_version,
    }


def _optional_mapped_value(row: pd.Series, column: str | None) -> str | None:
    return None if column is None else _text(row[column])


def _text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_date(value: date | str, *, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{field_name} must be an ISO-compatible date")
    return parsed.date()


def _membership_key(membership: PointInTimeSecurityMembership) -> str:
    return "|".join(
        (
            membership.security_id,
            membership.ticker,
            membership.valid_from.isoformat(),
            membership.valid_to.isoformat() if membership.valid_to else "",
        )
    )


def _ohlcv_key_fingerprint(tickers: pd.Series, dates: pd.Series) -> str:
    keys = pd.DataFrame({"ticker": tickers.astype("string"), "date": dates.astype("string")})
    canonical = keys.sort_values(["ticker", "date"], kind="mergesort").to_csv(
        index=False,
        lineterminator="\n",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _string_set_fingerprint(values: set[str]) -> str:
    canonical = json.dumps(sorted(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
