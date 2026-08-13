from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tsi.data.freshness import FreshnessPolicy, FreshnessThreshold, assess_freshness, parse_data_as_of


def test_freshness_policy_has_explicit_interval_and_market_thresholds() -> None:
    policy = FreshnessPolicy()

    assert policy.threshold_for(market="us", interval="5m").fresh_within_seconds == 600
    assert policy.threshold_for(market="twse", interval="1d").stale_within_seconds == 5 * 86400


def test_freshness_assessment_classifies_fresh_cutoff() -> None:
    evaluated_at = datetime(2026, 6, 19, 1, 0, tzinfo=UTC)
    assessment = assess_freshness(
        "2026-06-19T00:55:00Z",
        market="us",
        interval="5m",
        evaluated_at=evaluated_at,
    )

    assert assessment.state == "fresh"
    assert assessment.action == "allow"
    assert assessment.reason_code == "freshness_fresh"
    assert assessment.age_seconds == 300


def test_freshness_assessment_downgrades_stale_cutoff() -> None:
    evaluated_at = datetime(2026, 6, 19, 0, 30, tzinfo=UTC)
    assessment = assess_freshness(
        "2026-06-19T00:00:00Z",
        market="twse",
        interval="5m",
        evaluated_at=evaluated_at,
    )

    assert assessment.state == "stale"
    assert assessment.action == "downgrade"
    assert assessment.warning_level_override == "abstain"
    assert assessment.reason_code == "freshness_stale"


def test_freshness_assessment_blocks_missing_future_and_unusable_cutoffs() -> None:
    evaluated_at = datetime(2026, 6, 19, 0, 0, tzinfo=UTC)
    missing = assess_freshness(None, evaluated_at=evaluated_at)
    future = assess_freshness("2026-06-20T00:00:00Z", evaluated_at=evaluated_at)
    old = assess_freshness(
        date(2026, 6, 1),
        market="us",
        interval="1d",
        evaluated_at=evaluated_at,
    )

    assert missing.reason_code == "freshness_missing_data_as_of"
    assert future.reason_code == "freshness_future_data_as_of"
    assert old.state == "unusable"
    assert old.action == "block"


def test_parse_data_as_of_normalizes_date_and_datetime() -> None:
    assert parse_data_as_of(date(2026, 6, 19)) == datetime(2026, 6, 19, 23, 59, 59, 999999, tzinfo=UTC)
    assert parse_data_as_of("2026-06-19T00:00:00+08:00") == datetime(2026, 6, 18, 16, tzinfo=UTC)
    assert parse_data_as_of("  ") is None


def test_freshness_threshold_rejects_inverted_limits() -> None:
    with pytest.raises(ValueError, match="stale_within_seconds"):
        FreshnessThreshold(fresh_within_seconds=10, stale_within_seconds=9)
