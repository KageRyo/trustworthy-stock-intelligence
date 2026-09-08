"""Schema-first quality audits for normalized market bars.

The audit is deliberately separate from model inference.  It checks whether a
provider snapshot is safe to persist and records aggregate evidence without
embedding raw OHLCV rows in the report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from hashlib import sha256
from math import isclose, isfinite
import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

QUALITY_SCHEMA_VERSION = "market_bar_quality.v1"
QUALITY_COLUMNS = ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
QUALITY_INTERVALS = {"1m": 60, "5m": 300, "1d": None}
QualityStatus = Literal["pass", "warn", "fail"]
QualitySeverity = Literal["warning", "error"]
QualityInterval = Literal["1m", "5m", "1d"]


class MarketBarQualityIssue(BaseModel):
    """One aggregate issue class found in a market-bar snapshot."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: QualitySeverity
    count: int = Field(ge=1)
    ticker: str | None = None
    message: str = Field(min_length=1)


class TickerQualitySummary(BaseModel):
    """Aggregate quality counters for one ticker."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    market: str
    row_count: int = Field(ge=0)
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    observed_session_days: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    invalid_timestamp_rows: int = Field(ge=0)
    naive_timestamp_rows: int = Field(ge=0)
    out_of_order_rows: int = Field(ge=0)
    misaligned_rows: int = Field(ge=0)
    out_of_session_rows: int = Field(ge=0)
    gap_segments: int = Field(ge=0)
    missing_bars: int = Field(ge=0)
    non_finite_rows: int = Field(ge=0)
    missing_adj_close_rows: int = Field(ge=0)
    negative_value_rows: int = Field(ge=0)
    invariant_violation_rows: int = Field(ge=0)
    revision_rows: int = Field(ge=0)


class MarketBarQualityAudit(BaseModel):
    """Redacted, typed quality report for a market-bar snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = QUALITY_SCHEMA_VERSION
    provider: str = Field(min_length=1)
    interval: QualityInterval
    generated_at: str
    input_sha256: str = Field(min_length=64, max_length=64)
    raw_row_count: int = Field(ge=0)
    valid_timestamp_row_count: int = Field(ge=0)
    expected_tickers: list[str]
    observed_tickers: list[str]
    missing_tickers: list[str]
    issue_counts: dict[str, int]
    issues: list[MarketBarQualityIssue]
    ticker_summaries: list[TickerQualitySummary]
    status: QualityStatus
    fail_closed: bool


class MarketBarQualityError(RuntimeError):
    """Raised when a market-bar snapshot fails a fail-closed quality audit."""

    def __init__(self, audit: MarketBarQualityAudit) -> None:
        self.audit = audit
        super().__init__(
            f"market-bar quality audit failed for {audit.interval}: "
            f"{', '.join(sorted(audit.issue_counts)) or 'unknown issue'}"
        )


_SESSION_RULES: dict[str, tuple[str, time, time]] = {
    "us": ("America/New_York", time(9, 30), time(16, 0)),
    "twse": ("Asia/Taipei", time(9, 0), time(13, 30)),
    "tpex": ("Asia/Taipei", time(9, 0), time(13, 30)),
    "emerging": ("Asia/Taipei", time(9, 0), time(13, 30)),
    "taiwan": ("Asia/Taipei", time(9, 0), time(13, 30)),
}
_TZ_SUFFIX = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$", re.IGNORECASE)
_NUMERIC_COLUMNS = ("open", "high", "low", "close", "adj_close", "volume")
_REQUIRED_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")


def _normalized_ticker(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip().upper()


def _is_missing(value: object) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _is_naive_timestamp(value: object) -> bool:
    if _is_missing(value):
        return False
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.tzinfo is None or value.utcoffset() is None
    if isinstance(value, date):
        return True
    return not bool(_TZ_SUFFIX.search(str(value).strip()))


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace(
        [float("inf"), float("-inf")], float("nan")
    )


def _session_for(market: str) -> tuple[str, time, time] | None:
    return _SESSION_RULES.get(market.strip().lower())


def _timestamp_text(value: object) -> str | None:
    if _is_missing(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    return timestamp.isoformat()


def _canonical_input_sha256(frame: pd.DataFrame, parsed: pd.Series, tickers: pd.Series) -> str:
    canonical = frame.loc[:, QUALITY_COLUMNS].copy()
    canonical["date"] = parsed.map(_timestamp_text)
    canonical["ticker"] = tickers
    canonical = canonical.sort_values(["ticker", "date"], kind="mergesort")
    payload = canonical.to_csv(index=False, lineterminator="\n", na_rep="").encode("utf-8")
    return sha256(payload).hexdigest()


def _same_value(left: object, right: object) -> bool:
    if _is_missing(left) and _is_missing(right):
        return True
    try:
        return isfinite(float(left)) and isfinite(float(right)) and isclose(
            float(left), float(right), rel_tol=1e-12, abs_tol=1e-12
        )
    except (TypeError, ValueError):
        return str(left) == str(right)


def _snapshot_values(frame: pd.DataFrame) -> dict[tuple[str, str], tuple[object, ...]]:
    parsed = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    tickers = frame["ticker"].map(_normalized_ticker)
    values: dict[tuple[str, str], tuple[object, ...]] = {}
    for index, timestamp in parsed.items():
        ticker = tickers.loc[index]
        if not ticker or pd.isna(timestamp):
            continue
        key = (ticker, _timestamp_text(timestamp) or "")
        values[key] = tuple(frame.loc[index, column] for column in _NUMERIC_COLUMNS)
    return values


def _session_metadata(timestamp: pd.Timestamp, market: str, interval_seconds: int) -> tuple[date, bool, bool]:
    rule = _session_for(market)
    if rule is None:
        local = timestamp.tz_convert(UTC)
        seconds = local.hour * 3600 + local.minute * 60 + local.second
        return local.date(), True, seconds % interval_seconds == 0 and local.microsecond == 0

    timezone, session_start, session_end = rule
    local = timestamp.tz_convert(timezone)
    local_time = local.timetz().replace(tzinfo=None)
    in_session = session_start <= local_time <= session_end and local.weekday() < 5
    session_seconds = (
        local.hour * 3600
        + local.minute * 60
        + local.second
        - (session_start.hour * 3600 + session_start.minute * 60 + session_start.second)
    )
    aligned = (
        in_session
        and session_seconds % interval_seconds == 0
        and local.microsecond == 0
    )
    return local.date(), in_session, aligned


def audit_market_bars(
    frame: pd.DataFrame,
    *,
    interval: QualityInterval,
    provider: str,
    expected_tickers: Sequence[str] | None = None,
    market_by_ticker: Mapping[str, str] | None = None,
    previous_frame: pd.DataFrame | None = None,
    generated_at: datetime | None = None,
) -> MarketBarQualityAudit:
    """Audit a normalized OHLCV frame without returning raw market rows.

    Known US and Taiwan markets receive session-boundary and timestamp-grid
    checks.  Unknown markets still receive UTC spacing, numeric, duplicate,
    and timestamp checks.  A gap or provider revision is a warning because it
    may reflect a legitimate session boundary; malformed bars and ambiguous
    keys are errors and fail closed.
    """

    if interval not in QUALITY_INTERVALS:
        raise ValueError("interval must be one of 1m, 5m, 1d")
    missing_columns = sorted(set(QUALITY_COLUMNS).difference(frame.columns))
    if missing_columns:
        raise ValueError(f"market-bar frame is missing columns: {', '.join(missing_columns)}")
    if not provider.strip():
        raise ValueError("provider must not be empty")

    working = frame.loc[:, QUALITY_COLUMNS].copy()
    working["__ticker"] = working["ticker"].map(_normalized_ticker)
    working["__timestamp"] = pd.to_datetime(working["date"], utc=True, errors="coerce")
    working["__naive_timestamp"] = (
        working["date"].map(_is_naive_timestamp) if interval != "1d" else False
    )
    for column in _NUMERIC_COLUMNS:
        working[f"__{column}"] = _to_numeric(working[column])

    market_lookup = {
        _normalized_ticker(ticker): str(market).strip().lower()
        for ticker, market in (market_by_ticker or {}).items()
    }
    expected = sorted({_normalized_ticker(ticker) for ticker in (expected_tickers or []) if _normalized_ticker(ticker)})
    observed = sorted(
        {
            ticker
            for ticker in working["__ticker"]
            if ticker and not bool(pd.isna(working.loc[working["__ticker"] == ticker, "__timestamp"]).all())
        }
    )
    missing_tickers = sorted(set(expected).difference(observed))

    issues: list[MarketBarQualityIssue] = []
    issue_counts: dict[str, int] = {}

    def add_issue(
        code: str,
        severity: QualitySeverity,
        count: int,
        message: str,
        ticker: str | None = None,
    ) -> None:
        if count <= 0:
            return
        issues.append(
            MarketBarQualityIssue(
                code=code,
                severity=severity,
                count=count,
                ticker=ticker or None,
                message=message,
            )
        )
        issue_counts[code] = issue_counts.get(code, 0) + count

    if frame.empty:
        add_issue(
            "empty_snapshot",
            "error",
            1,
            "market-bar snapshot contains no rows",
        )

    if missing_tickers:
        add_issue(
            "missing_ticker",
            "error",
            len(missing_tickers),
            "expected ticker has no valid market-bar rows",
        )

    valid_timestamp_mask = working["__timestamp"].notna()
    valid_ticker_mask = working["__ticker"].ne("")
    valid_key_frame = working.loc[valid_timestamp_mask & valid_ticker_mask, ["__ticker", "__timestamp"]]
    duplicate_mask = valid_key_frame.duplicated(["__ticker", "__timestamp"], keep=False)
    duplicate_rows_by_ticker = (
        valid_key_frame.loc[duplicate_mask, "__ticker"].value_counts().to_dict()
    )
    total_duplicate_rows = int(duplicate_mask.sum())
    if total_duplicate_rows:
        add_issue(
            "duplicate_bar",
            "error",
            total_duplicate_rows,
            "ticker and timestamp identify more than one bar",
        )

    required_numeric_columns = [f"__{column}" for column in _REQUIRED_NUMERIC_COLUMNS]
    required_numeric_missing = working[required_numeric_columns].isna().any(axis=1)
    missing_adj_close = working["__adj_close"].isna()
    if int(missing_adj_close.sum()):
        add_issue(
            "missing_adj_close",
            "warning",
            int(missing_adj_close.sum()),
            "adjusted close is unavailable for a market-bar row",
        )

    negative_mask = working[required_numeric_columns].lt(0).any(axis=1).fillna(False)
    if int(negative_mask.sum()):
        add_issue(
            "negative_value",
            "error",
            int(negative_mask.sum()),
            "price or volume is negative",
        )

    complete_numeric = ~required_numeric_missing
    high = working["__high"]
    low = working["__low"]
    open_price = working["__open"]
    close = working["__close"]
    invariant_mask = complete_numeric & (
        high.lt(low)
        | high.lt(open_price)
        | high.lt(close)
        | low.gt(open_price)
        | low.gt(close)
    )
    if int(invariant_mask.sum()):
        add_issue(
            "ohlcv_invariant",
            "error",
            int(invariant_mask.sum()),
            "high/low bounds do not contain open and close",
        )

    if int(required_numeric_missing.sum()):
        add_issue(
            "non_finite_value",
            "error",
            int(required_numeric_missing.sum()),
            "required OHLCV value is missing or non-finite",
        )

    if int((~valid_timestamp_mask).sum()):
        add_issue(
            "invalid_timestamp",
            "error",
            int((~valid_timestamp_mask).sum()),
            "timestamp cannot be parsed as a UTC instant",
        )
    if int((~valid_ticker_mask).sum()):
        add_issue(
            "missing_ticker",
            "error",
            int((~valid_ticker_mask).sum()),
            "ticker identifier is empty or missing",
        )

    revisions_by_ticker: dict[str, int] = {}
    if previous_frame is not None:
        previous_columns = sorted(set(QUALITY_COLUMNS).difference(previous_frame.columns))
        if previous_columns:
            raise ValueError(
                "previous market-bar frame is missing columns: "
                + ", ".join(previous_columns)
            )
        previous_values = _snapshot_values(previous_frame)
        current_values = _snapshot_values(working.loc[:, QUALITY_COLUMNS])
        for key in sorted(set(previous_values).intersection(current_values)):
            if any(
                not _same_value(left, right)
                for left, right in zip(previous_values[key], current_values[key], strict=True)
            ):
                revisions_by_ticker[key[0]] = revisions_by_ticker.get(key[0], 0) + 1
        revision_count = sum(revisions_by_ticker.values())
        if revision_count:
            add_issue(
                "provider_revision",
                "warning",
                revision_count,
                "an existing ticker/timestamp has changed OHLCV values",
            )

    interval_seconds = QUALITY_INTERVALS[interval]
    summaries: list[TickerQualitySummary] = []
    for ticker in sorted(set(observed).union(expected)):
        ticker_mask = working["__ticker"].eq(ticker)
        ticker_frame = working.loc[ticker_mask].copy()
        market = market_lookup.get(ticker, "unknown") or "unknown"
        valid = ticker_frame.loc[ticker_frame["__timestamp"].notna()].copy()
        valid = valid.sort_values("__timestamp", kind="mergesort")
        timestamps = valid["__timestamp"]
        out_of_order = int(
            ticker_frame.loc[ticker_frame["__timestamp"].notna(), "__timestamp"].diff().dt.total_seconds().lt(0).sum()
        )
        ticker_duplicate_rows = int(duplicate_rows_by_ticker.get(ticker, 0))
        ticker_invalid_timestamp = int(ticker_frame["__timestamp"].isna().sum())
        ticker_naive_timestamp = int(
            ticker_frame.loc[ticker_frame["__timestamp"].notna(), "__naive_timestamp"].sum()
        )
        ticker_non_finite = int(ticker_frame[required_numeric_columns].isna().any(axis=1).sum())
        ticker_missing_adj_close = int(ticker_frame["__adj_close"].isna().sum())
        ticker_negative = int(negative_mask.loc[ticker_mask].sum())
        ticker_invariant = int(invariant_mask.loc[ticker_mask].sum())
        ticker_revisions = revisions_by_ticker.get(ticker, 0)

        misaligned = 0
        out_of_session = 0
        gap_segments = 0
        missing_bars = 0
        session_days: set[date] = set()
        if interval_seconds is not None:
            session_dates: list[date] = []
            in_session_flags: list[bool] = []
            aligned_flags: list[bool] = []
            for timestamp in timestamps:
                session_date, in_session, aligned = _session_metadata(
                    timestamp, market, interval_seconds
                )
                session_dates.append(session_date)
                in_session_flags.append(in_session)
                aligned_flags.append(aligned)
                session_days.add(session_date)
            misaligned = sum(not value for value in aligned_flags)
            out_of_session = sum(not value for value in in_session_flags)
            for previous_index in range(1, len(timestamps)):
                previous_timestamp = timestamps.iloc[previous_index - 1]
                current_timestamp = timestamps.iloc[previous_index]
                if (
                    session_dates[previous_index] == session_dates[previous_index - 1]
                    and in_session_flags[previous_index]
                    and in_session_flags[previous_index - 1]
                ):
                    delta_seconds = (current_timestamp - previous_timestamp).total_seconds()
                    if delta_seconds > interval_seconds:
                        gap_segments += 1
                        if delta_seconds % interval_seconds == 0:
                            missing_bars += max(0, int(delta_seconds // interval_seconds) - 1)
        else:
            session_days = set(timestamps.dt.date.tolist())

        if ticker_naive_timestamp:
            add_issue(
                "naive_timestamp",
                "error",
                ticker_naive_timestamp,
                "intraday timestamp has no explicit timezone",
                ticker,
            )
        if out_of_order:
            add_issue(
                "out_of_order",
                "warning",
                out_of_order,
                "rows are not ordered by ticker timestamp",
                ticker,
            )
        if misaligned:
            add_issue(
                "misaligned_timestamp",
                "error",
                misaligned,
                "timestamp is not aligned to the interval grid",
                ticker,
            )
        if out_of_session:
            add_issue(
                "out_of_session",
                "error",
                out_of_session,
                "timestamp is outside the configured market session",
                ticker,
            )
        if gap_segments:
            add_issue(
                "bar_gap",
                "warning",
                gap_segments,
                "consecutive in-session bars are separated by one or more intervals",
                ticker,
            )

        summaries.append(
            TickerQualitySummary(
                ticker=ticker,
                market=market,
                row_count=int(len(ticker_frame)),
                first_timestamp=_timestamp_text(timestamps.iloc[0]) if len(timestamps) else None,
                last_timestamp=_timestamp_text(timestamps.iloc[-1]) if len(timestamps) else None,
                observed_session_days=len(session_days),
                duplicate_rows=ticker_duplicate_rows,
                invalid_timestamp_rows=ticker_invalid_timestamp,
                naive_timestamp_rows=ticker_naive_timestamp,
                out_of_order_rows=out_of_order,
                misaligned_rows=misaligned,
                out_of_session_rows=out_of_session,
                gap_segments=gap_segments,
                missing_bars=missing_bars,
                non_finite_rows=ticker_non_finite,
                missing_adj_close_rows=ticker_missing_adj_close,
                negative_value_rows=ticker_negative,
                invariant_violation_rows=ticker_invariant,
                revision_rows=ticker_revisions,
            )
        )

    status: QualityStatus
    if any(issue.severity == "error" for issue in issues):
        status = "fail"
    elif issues:
        status = "warn"
    else:
        status = "pass"
    generated = generated_at or datetime.now(UTC)
    if generated.tzinfo is None or generated.utcoffset() is None:
        generated = generated.replace(tzinfo=UTC)
    else:
        generated = generated.astimezone(UTC)

    return MarketBarQualityAudit(
        provider=provider.strip(),
        interval=interval,
        generated_at=generated.isoformat(),
        input_sha256=_canonical_input_sha256(frame, working["__timestamp"], working["__ticker"]),
        raw_row_count=int(len(frame)),
        valid_timestamp_row_count=int(valid_timestamp_mask.sum()),
        expected_tickers=expected,
        observed_tickers=observed,
        missing_tickers=missing_tickers,
        issue_counts=dict(sorted(issue_counts.items())),
        issues=issues,
        ticker_summaries=summaries,
        status=status,
        fail_closed=status == "fail",
    )


def enforce_market_bar_quality(audit: MarketBarQualityAudit | None) -> None:
    """Raise for a failed audit while allowing warning-only snapshots."""

    if audit is not None and audit.fail_closed:
        raise MarketBarQualityError(audit)
