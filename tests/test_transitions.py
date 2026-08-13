from __future__ import annotations

from datetime import UTC, datetime

from tsi.trust.transitions import WarningSnapshot, detect_warning_transition, detect_warning_transitions


OBSERVED = datetime(2026, 8, 13, 2, 0, tzinfo=UTC)


def snapshot(
    ticker: str = "NVDA",
    level: str = "no_alert",
    *,
    trust: float = 0.8,
    risk: float = 0.1,
    run_id: str = "run-1",
    reason_codes: list[str] | None = None,
) -> WarningSnapshot:
    return WarningSnapshot(
        ticker=ticker,
        warning_level=level,
        calibrated_risk_probability=risk,
        trust_score=trust,
        alert_threshold=0.2,
        watch_threshold=0.16,
        reason_codes=reason_codes or [],
        run_id=run_id,
        observed_at=OBSERVED,
    )


def test_new_watch_and_alert_transitions() -> None:
    assert detect_warning_transition(None, snapshot(level="watch")).transition_type == "new_watch"
    assert detect_warning_transition(None, snapshot(level="alert", trust=0.9)).transition_type == "new_alert"


def test_upgrade_downgrade_resolution_and_persistent_alert() -> None:
    assert detect_warning_transition(snapshot(), snapshot(level="watch", run_id="run-2")).transition_type == "new_watch"
    assert detect_warning_transition(snapshot(level="watch"), snapshot(level="alert", trust=0.9, run_id="run-2")).transition_type == "upgraded"
    assert detect_warning_transition(snapshot(level="alert", trust=0.9), snapshot(level="watch", run_id="run-2")).transition_type == "downgraded"
    assert detect_warning_transition(snapshot(level="watch"), snapshot(level="no_alert", run_id="run-2")).transition_type == "resolved"
    assert detect_warning_transition(snapshot(level="alert", trust=0.9), snapshot(level="alert", trust=0.9, risk=0.3, run_id="run-2")).transition_type == "persistent_alert"


def test_low_trust_takes_precedence_and_identical_snapshots_are_deduplicated() -> None:
    low_trust = snapshot(level="watch", trust=0.1, reason_codes=["trust_below_alert_threshold"])
    assert detect_warning_transition(None, low_trust).transition_type == "low_trust_warning"
    assert detect_warning_transition(low_trust, low_trust) is None


def test_batch_transitions_are_sorted_and_repeatable() -> None:
    current = [snapshot("ZZZ", "alert", trust=0.9), snapshot("AAA", "watch")]
    transitions = detect_warning_transitions({}, current)

    assert [item.ticker for item in transitions] == ["AAA", "ZZZ"]
    assert [item.deduplication_key for item in transitions] == ["AAA:run-1:new_watch", "ZZZ:run-1:new_alert"]
