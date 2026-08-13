"""Provider retry, health, and coverage schemas.

The downloader is intentionally provider-agnostic at this boundary.  It emits
typed observations for each provider/ticker attempt; persistence and serving
layers can then retain those observations across requests without passing raw
provider payloads across the application boundary.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProviderHealthStatus = Literal["healthy", "degraded", "unavailable"]
ProviderCoverageStatus = Literal["available", "partial", "unavailable", "unknown"]

T = TypeVar("T")


class RetryPolicy(BaseModel):
    """Bounded exponential-backoff policy for one provider operation."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=3, ge=1, le=8)
    initial_backoff_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    max_backoff_seconds: float = Field(default=5.0, ge=0.0, le=300.0)

    @model_validator(mode="after")
    def validate_backoff_bounds(self) -> "RetryPolicy":
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("max_backoff_seconds must be at least initial_backoff_seconds")
        return self

    def delay_seconds(self, retry_number: int) -> float:
        """Return the delay before the next attempt (retry number starts at one)."""

        if retry_number < 1:
            raise ValueError("retry_number must be at least 1")
        return min(
            self.max_backoff_seconds,
            self.initial_backoff_seconds * (2 ** (retry_number - 1)),
        )


@dataclass(frozen=True)
class RetryOutcome(Generic[T]):
    """Result of a bounded retry loop, including failures for observability."""

    value: T | None
    attempts: int
    succeeded: bool
    errors: tuple[str, ...]


def run_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    is_success: Callable[[T], bool] | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> RetryOutcome[T]:
    """Run one provider operation with bounded retry and injectable sleeping.

    ``is_success`` allows adapters to treat an empty, schema-valid response as
    an unsuccessful provider attempt.  The default retries every exception;
    callers can narrow that behavior for non-transient provider errors.
    """

    retry_policy = policy or RetryPolicy()
    success_predicate = is_success or (lambda _value: True)
    retry_predicate = should_retry or (lambda _error: True)
    errors: list[str] = []
    value: T | None = None

    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            value = operation()
            if success_predicate(value):
                return RetryOutcome(value, attempt, True, tuple(errors))
            errors.append("provider returned no usable data")
        except Exception as exc:  # provider adapters must isolate ordinary failures
            errors.append(f"{type(exc).__name__}: {exc}")
            if not retry_predicate(exc):
                break
        if attempt < retry_policy.max_attempts:
            sleep(retry_policy.delay_seconds(attempt))

    return RetryOutcome(value, retry_policy.max_attempts if value is not None else len(errors), False, tuple(errors))


class ProviderHealthSnapshot(BaseModel):
    """Schema-first health and per-ticker coverage observation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "provider_health.v1"
    provider: str = Field(min_length=1)
    market: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    query_symbol: str = Field(min_length=1)
    status: ProviderHealthStatus
    coverage: ProviderCoverageStatus
    attempt_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    consecutive_failures: int = Field(ge=0)
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_latency_ms: float | None = Field(default=None, ge=0.0)
    last_error_code: str = ""
    last_error_message: str = ""
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def classify_provider_health(
    *,
    succeeded: bool,
    consecutive_failures: int,
    success_count: int,
) -> ProviderHealthStatus:
    """Classify health without hiding a provider that has never succeeded."""

    if not succeeded and success_count == 0:
        return "unavailable"
    if not succeeded and consecutive_failures >= 3:
        return "unavailable"
    if not succeeded or consecutive_failures > 0:
        return "degraded"
    return "healthy"


def make_provider_health_snapshot(
    *,
    provider: str,
    market: str,
    ticker: str,
    query_symbol: str,
    outcome: RetryOutcome[object],
    coverage: ProviderCoverageStatus,
    latency_ms: float | None,
    observed_at: datetime | None = None,
    error_code: str = "",
) -> ProviderHealthSnapshot:
    """Build a normalized observation from one provider retry outcome."""

    now = observed_at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    elif now.utcoffset() is None:
        now = now.replace(tzinfo=UTC)
    attempt_count = max(outcome.attempts, 1)
    success_count = attempt_count if outcome.succeeded else 0
    failure_count = 0 if outcome.succeeded else attempt_count
    consecutive_failures = 0 if outcome.succeeded else attempt_count
    succeeded = outcome.succeeded and coverage in {"available", "partial"}
    if not succeeded:
        success_count = 0
        failure_count = attempt_count
    status = classify_provider_health(
        succeeded=succeeded,
        consecutive_failures=consecutive_failures,
        success_count=success_count,
    )
    last_error_message = " | ".join(outcome.errors[-3:])
    return ProviderHealthSnapshot(
        provider=provider,
        market=market,
        ticker=ticker,
        query_symbol=query_symbol,
        status=status,
        coverage=coverage,
        attempt_count=attempt_count,
        success_count=success_count,
        failure_count=failure_count,
        consecutive_failures=consecutive_failures,
        last_success_at=now if succeeded else None,
        last_failure_at=None if succeeded else now,
        last_latency_ms=latency_ms,
        last_error_code=error_code if not succeeded else "",
        last_error_message=last_error_message if not succeeded else "",
        observed_at=now,
    )
