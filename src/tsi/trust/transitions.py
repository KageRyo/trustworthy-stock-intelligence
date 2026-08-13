"""Deterministic warning-state transition detection.

Transitions are derived from adjacent persisted snapshots for one ticker. The
detector intentionally returns at most one primary event per current snapshot;
repeated identical snapshots return ``None`` so polling cannot create a stream
of duplicate events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WarningLevel = Literal["alert", "watch", "abstain", "no_alert"]
TransitionType = Literal[
    "new_watch",
    "new_alert",
    "upgraded",
    "downgraded",
    "resolved",
    "persistent_alert",
    "low_trust_warning",
]


class WarningSnapshot(BaseModel):
    """Minimal warning state needed to compare two observations."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    warning_level: WarningLevel
    calibrated_risk_probability: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    alert_threshold: float = Field(ge=0.0, le=1.0)
    watch_threshold: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    run_id: str = ""
    batch_id: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WarningTransition(BaseModel):
    """One schema-first primary warning transition event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "warning_transition.v1"
    ticker: str
    transition_type: TransitionType
    previous_warning_level: WarningLevel | None = None
    current_warning_level: WarningLevel
    previous_run_id: str | None = None
    current_run_id: str = ""
    previous_batch_id: str | None = None
    current_batch_id: str | None = None
    detected_at: datetime
    deduplication_key: str


def detect_warning_transition(
    previous: WarningSnapshot | None,
    current: WarningSnapshot,
) -> WarningTransition | None:
    """Return the deterministic primary transition for ``current``.

    ``None`` means there is no meaningful transition, including an identical
    repeated snapshot. A current low-trust/abstain state takes precedence over
    a generic upgrade so it remains visible to serving consumers.
    """

    if previous is not None and previous.ticker != current.ticker:
        raise ValueError("previous and current snapshots must use the same ticker")
    if previous is not None and _state_signature(previous) == _state_signature(current):
        return None

    transition_type: TransitionType | None
    if _is_low_trust(current):
        transition_type = "low_trust_warning"
    elif previous is None:
        transition_type = {
            "watch": "new_watch",
            "alert": "new_alert",
        }.get(current.warning_level)
    elif current.warning_level == "alert":
        transition_type = "persistent_alert" if previous.warning_level == "alert" else "upgraded"
    elif current.warning_level == "watch":
        if previous.warning_level == "alert":
            transition_type = "downgraded"
        elif previous.warning_level == "watch":
            transition_type = None
        else:
            transition_type = "new_watch"
    elif current.warning_level == "no_alert":
        transition_type = (
            "resolved" if previous.warning_level in {"alert", "watch"} else None
        )
    else:
        transition_type = None

    if transition_type is None:
        return None
    previous_run_id = previous.run_id if previous is not None else None
    previous_batch_id = previous.batch_id if previous is not None else None
    current_run_id = current.run_id
    deduplication_key = ":".join(
        [current.ticker, current_run_id or current.observed_at.isoformat(), transition_type]
    )
    return WarningTransition(
        ticker=current.ticker,
        transition_type=transition_type,
        previous_warning_level=previous.warning_level if previous is not None else None,
        current_warning_level=current.warning_level,
        previous_run_id=previous_run_id,
        current_run_id=current_run_id,
        previous_batch_id=previous_batch_id,
        current_batch_id=current.batch_id,
        detected_at=current.observed_at,
        deduplication_key=deduplication_key,
    )


def detect_warning_transitions(
    previous_by_ticker: dict[str, WarningSnapshot],
    current: list[WarningSnapshot],
) -> list[WarningTransition]:
    """Compare a batch in stable ticker order and return primary events."""

    transitions: list[WarningTransition] = []
    for snapshot in sorted(current, key=lambda item: item.ticker):
        transition = detect_warning_transition(previous_by_ticker.get(snapshot.ticker), snapshot)
        if transition is not None:
            transitions.append(transition)
    return transitions


def _state_signature(snapshot: WarningSnapshot) -> tuple[object, ...]:
    return (
        snapshot.warning_level,
        snapshot.calibrated_risk_probability,
        snapshot.trust_score,
        snapshot.alert_threshold,
        snapshot.watch_threshold,
        tuple(snapshot.reason_codes),
    )


def _is_low_trust(snapshot: WarningSnapshot) -> bool:
    return (
        snapshot.warning_level == "abstain"
        or snapshot.trust_score < snapshot.alert_threshold
        or "trust_below_alert_threshold" in snapshot.reason_codes
        or "uncertainty_above_threshold" in snapshot.reason_codes
        or "calibration_drift_abstain" in snapshot.reason_codes
    )
