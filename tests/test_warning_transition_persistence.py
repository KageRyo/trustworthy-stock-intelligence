from __future__ import annotations

from datetime import UTC, datetime

from tsi.data.postgres import _persist_warning_transitions
from tsi.serving.schema import PredictionBatch, PredictionRecord


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class TransitionConnection:
    def __init__(self, previous_row):
        self.previous_row = previous_row
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "SELECT pb.id" in query:
            return Cursor(self.previous_row)
        return Cursor()


def _batch(*, level: str, run_id: str) -> PredictionBatch:
    return PredictionBatch(
        run_id=run_id,
        data_as_of="2026-08-13",
        generated_at="2026-08-13T02:00:00+00:00",
        records=[
            PredictionRecord(
                date="2026-08-13",
                ticker="NVDA",
                model="logistic_regression_latest",
                model_bundle="bundle",
                risk_probability=0.3,
                calibrated_risk_probability=0.3 if level == "alert" else 0.18,
                calibration_method="platt",
                uncertainty_score=0.1,
                trust_score=0.9,
                alert_threshold=0.2,
                watch_threshold=0.16,
                warning_level=level,
                reason_codes=[],
            )
        ],
    )


def test_persist_warning_transitions_compares_latest_previous_snapshot() -> None:
    previous = (
        "batch-1",
        "run-1",
        datetime(2026, 8, 12, 2, 0, tzinfo=UTC),
        "watch",
        0.18,
        0.9,
        0.2,
        0.16,
        [],
    )
    connection = TransitionConnection(previous)

    transitions = _persist_warning_transitions(
        connection,
        _batch(level="alert", run_id="run-2"),
        "batch-2",
        {"NVDA": "ticker-id"},
    )

    assert len(transitions) == 1
    assert transitions[0].transition_type == "upgraded"
    assert any("INSERT INTO warning_transitions" in query for query, _ in connection.calls)


def test_persist_warning_transitions_ignores_identical_snapshot() -> None:
    previous = (
        "batch-1",
        "run-1",
        datetime(2026, 8, 12, 2, 0, tzinfo=UTC),
        "alert",
        0.3,
        0.9,
        0.2,
        0.16,
        [],
    )
    connection = TransitionConnection(previous)

    transitions = _persist_warning_transitions(
        connection,
        _batch(level="alert", run_id="run-2"),
        "batch-2",
        {"NVDA": "ticker-id"},
    )

    assert transitions == []
    assert all("INSERT INTO warning_transitions" not in query for query, _ in connection.calls)
