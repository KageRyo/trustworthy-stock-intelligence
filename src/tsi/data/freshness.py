"""Deterministic market-data freshness policy.

Freshness is a serving safety boundary, not a provider availability claim.  A
prediction keeps its original data cutoff while this module reports whether
that cutoff is still usable for the requested feature interval and market.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FreshnessState = Literal["fresh", "stale", "unusable"]
FreshnessAction = Literal["allow", "downgrade", "abstain", "block"]
FreshnessInterval = Literal["1m", "5m", "1d"]

FRESHNESS_SCHEMA_VERSION = "freshness.v1"


class FreshnessThreshold(BaseModel):
    """Age limits in seconds for one interval/market pair."""

    model_config = ConfigDict(extra="forbid")

    fresh_within_seconds: int = Field(ge=0)
    stale_within_seconds: int = Field(ge=0)

    def model_post_init(self, __context: object) -> None:
        if self.stale_within_seconds < self.fresh_within_seconds:
            raise ValueError("stale_within_seconds must be at least fresh_within_seconds")


def _default_thresholds() -> dict[str, FreshnessThreshold]:
    intraday = {
        "1m": FreshnessThreshold(fresh_within_seconds=120, stale_within_seconds=900),
        "5m": FreshnessThreshold(fresh_within_seconds=600, stale_within_seconds=3600),
    }
    daily = FreshnessThreshold(fresh_within_seconds=36 * 3600, stale_within_seconds=5 * 86400)
    thresholds: dict[str, FreshnessThreshold] = {"default:1d": daily}
    for market in ("default", "us", "twse", "tpex", "emerging", "taiwan", "unknown"):
        for interval, threshold in intraday.items():
            thresholds[f"{market}:{interval}"] = threshold
        thresholds[f"{market}:1d"] = daily
    return thresholds


class FreshnessPolicy(BaseModel):
    """Versioned threshold table with explicit market/interval fallbacks."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = FRESHNESS_SCHEMA_VERSION
    thresholds: dict[str, FreshnessThreshold] = Field(default_factory=_default_thresholds)

    def threshold_for(self, *, market: str, interval: str) -> FreshnessThreshold:
        normalized_market = market.strip().lower() or "unknown"
        normalized_interval = interval.strip().lower()
        if normalized_interval not in {"1m", "5m", "1d"}:
            raise ValueError("interval must be one of 1m, 5m, 1d")
        return self.thresholds.get(
            f"{normalized_market}:{normalized_interval}",
            self.thresholds.get(f"default:{normalized_interval}", self.thresholds["default:1d"]),
        )


FreshnessReasonCode = Literal[
    "freshness_fresh",
    "freshness_stale",
    "freshness_unusable",
    "freshness_missing_data_as_of",
    "freshness_future_data_as_of",
]


class FreshnessAssessment(BaseModel):
    """Schema-first freshness state propagated to serving clients."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = FRESHNESS_SCHEMA_VERSION
    market: str
    interval: FreshnessInterval
    data_as_of: str
    evaluated_at: str
    age_seconds: float | None = Field(default=None, ge=0.0)
    fresh_within_seconds: int = Field(ge=0)
    stale_within_seconds: int = Field(ge=0)
    state: FreshnessState
    action: FreshnessAction
    reason_code: FreshnessReasonCode
    warning_level_override: Literal["abstain"] | None = None
    message: str


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_data_as_of(value: str | datetime | date | None) -> datetime | None:
    """Parse a cutoff, treating date-only values as the end of that UTC day."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, date):
        return datetime.combine(value, time.max, tzinfo=UTC)
    normalized = value.strip()
    if not normalized:
        return None
    try:
        if len(normalized) == 10:
            return datetime.combine(date.fromisoformat(normalized), time.max, tzinfo=UTC)
        return _as_utc(datetime.fromisoformat(normalized.replace("Z", "+00:00")))
    except ValueError as exc:
        raise ValueError("data_as_of must be an ISO date or datetime") from exc


def assess_freshness(
    data_as_of: str | datetime | date | None,
    *,
    market: str = "unknown",
    interval: FreshnessInterval = "1d",
    evaluated_at: datetime | None = None,
    policy: FreshnessPolicy | None = None,
) -> FreshnessAssessment:
    """Classify a cutoff as fresh, stale, or unusable deterministically."""

    freshness_policy = policy or FreshnessPolicy()
    evaluated = _as_utc(evaluated_at or datetime.now(UTC))
    threshold = freshness_policy.threshold_for(market=market, interval=interval)
    evaluated_text = evaluated.isoformat()
    normalized_market = market.strip().lower() or "unknown"
    parsed = parse_data_as_of(data_as_of)
    data_text = "" if data_as_of is None else str(data_as_of)

    if parsed is None:
        return FreshnessAssessment(
            market=normalized_market,
            interval=interval,
            data_as_of=data_text,
            evaluated_at=evaluated_text,
            fresh_within_seconds=threshold.fresh_within_seconds,
            stale_within_seconds=threshold.stale_within_seconds,
            state="unusable",
            action="block",
            reason_code="freshness_missing_data_as_of",
            warning_level_override="abstain",
            message="The prediction has no data cutoff and must not be served as actionable.",
        )

    age_seconds = (evaluated - parsed).total_seconds()
    if age_seconds < 0:
        return FreshnessAssessment(
            market=normalized_market,
            interval=interval,
            data_as_of=data_text,
            evaluated_at=evaluated_text,
            age_seconds=0.0,
            fresh_within_seconds=threshold.fresh_within_seconds,
            stale_within_seconds=threshold.stale_within_seconds,
            state="unusable",
            action="block",
            reason_code="freshness_future_data_as_of",
            warning_level_override="abstain",
            message="The prediction cutoff is in the future and must not be served.",
        )
    if age_seconds <= threshold.fresh_within_seconds:
        state: FreshnessState = "fresh"
        action: FreshnessAction = "allow"
        reason_code: FreshnessReasonCode = "freshness_fresh"
        warning_override = None
        message = "The prediction cutoff is within the configured freshness window."
    elif age_seconds <= threshold.stale_within_seconds:
        state = "stale"
        action = "downgrade"
        reason_code = "freshness_stale"
        warning_override = "abstain"
        message = "The prediction is retained for context but is too old for a full-confidence warning."
    else:
        state = "unusable"
        action = "block"
        reason_code = "freshness_unusable"
        warning_override = "abstain"
        message = "The prediction is beyond the usable freshness window and must be treated as abstain."
    return FreshnessAssessment(
        market=normalized_market,
        interval=interval,
        data_as_of=data_text,
        evaluated_at=evaluated_text,
        age_seconds=age_seconds,
        fresh_within_seconds=threshold.fresh_within_seconds,
        stale_within_seconds=threshold.stale_within_seconds,
        state=state,
        action=action,
        reason_code=reason_code,
        warning_level_override=warning_override,
        message=message,
    )
