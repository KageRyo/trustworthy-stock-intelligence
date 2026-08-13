from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tsi.data.provider_health import (
    ProviderHealthSnapshot,
    RetryPolicy,
    classify_provider_health,
    make_provider_health_snapshot,
    run_with_retry,
)


def test_retry_policy_uses_bounded_exponential_backoff() -> None:
    policy = RetryPolicy(max_attempts=4, initial_backoff_seconds=0.25, max_backoff_seconds=0.75)

    assert [policy.delay_seconds(index) for index in range(1, 5)] == [0.25, 0.5, 0.75, 0.75]


def test_retry_policy_rejects_inverted_backoff_bounds() -> None:
    with pytest.raises(ValueError, match="max_backoff_seconds"):
        RetryPolicy(initial_backoff_seconds=2.0, max_backoff_seconds=1.0)


def test_run_with_retry_retries_exceptions_and_records_errors() -> None:
    attempts = 0
    sleeps: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("provider timeout")
        return "ok"

    outcome = run_with_retry(
        operation,
        policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.1, max_backoff_seconds=0.5),
        sleep=sleeps.append,
    )

    assert outcome.succeeded is True
    assert outcome.value == "ok"
    assert outcome.attempts == 3
    assert len(outcome.errors) == 2
    assert sleeps == [0.1, 0.2]


def test_run_with_retry_retries_empty_provider_responses() -> None:
    responses = iter([[], [], ["bar"]])
    sleeps: list[float] = []

    outcome = run_with_retry(
        lambda: next(responses),
        policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.0),
        is_success=bool,
        sleep=sleeps.append,
    )

    assert outcome.succeeded is True
    assert outcome.value == ["bar"]
    assert outcome.attempts == 3
    assert outcome.errors == ("provider returned no usable data",) * 2
    assert sleeps == [0.0, 0.0]


def test_provider_health_snapshot_is_schema_first_and_typed() -> None:
    observed_at = datetime(2026, 6, 18, 1, 5, tzinfo=UTC)
    snapshot = make_provider_health_snapshot(
        provider="yfinance",
        market="us",
        ticker="NVDA",
        query_symbol="NVDA",
        outcome=run_with_retry(lambda: {"close": 1}),
        coverage="available",
        latency_ms=42.5,
        observed_at=observed_at,
    )

    assert isinstance(snapshot, ProviderHealthSnapshot)
    assert snapshot.schema_version == "provider_health.v1"
    assert snapshot.status == "healthy"
    assert snapshot.coverage == "available"
    assert snapshot.last_success_at == observed_at
    assert snapshot.model_dump(mode="json")["last_latency_ms"] == 42.5


def test_provider_health_classification_blocks_never_successful_provider() -> None:
    assert classify_provider_health(succeeded=False, consecutive_failures=1, success_count=0) == (
        "unavailable"
    )
    assert classify_provider_health(succeeded=False, consecutive_failures=1, success_count=2) == (
        "degraded"
    )
