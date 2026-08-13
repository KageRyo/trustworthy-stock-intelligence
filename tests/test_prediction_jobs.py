from __future__ import annotations

from datetime import UTC, datetime

from tsi.data import prediction_jobs as jobs
from tsi.data.postgres import read_market_bars_from_postgres


NOW = datetime(2026, 8, 13, 2, 0, tzinfo=UTC)


def _row(
    *,
    status: str = "queued",
    attempt_count: int = 0,
    worker_id: str | None = None,
    failure_code: str = "",
) -> tuple[object, ...]:
    return (
        "job-1",
        "request-1",
        "NVDA",
        "auto",
        "1d",
        status,
        attempt_count,
        3,
        NOW,
        NOW,
        NOW if status == "running" else None,
        NOW if status in {"completed", "failed"} else None,
        worker_id,
        NOW if status == "running" else None,
        "batch-1" if status == "completed" else None,
        "request-1" if status == "completed" else None,
        failure_code,
        "failure" if failure_code else "",
        {"source": "test"},
        NOW,
        NOW,
    )


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeTransaction:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self, cursors):
        self.cursors = list(cursors)
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def transaction(self):
        return FakeTransaction()

    def execute(self, query, params=()):
        self.queries.append((query, params))
        return self.cursors.pop(0)

    def commit(self):
        self.commits += 1


def test_enqueue_is_idempotent_and_normalizes_ticker(monkeypatch) -> None:
    connection = FakeConnection([FakeCursor(row=_row())])
    monkeypatch.setattr(jobs, "connect_database", lambda _url: connection)

    job = jobs.enqueue_prediction_job(
        "postgresql://test",
        jobs.PredictionJobRequest(
            idempotency_key="request-1",
            ticker=" nvda ",
            request_payload={"source": "api"},
        ),
        now=NOW,
    )

    assert job.status == "queued"
    assert job.ticker == "NVDA"
    assert connection.commits == 1
    query, params = connection.queries[0]
    assert "ON CONFLICT (idempotency_key)" in query
    assert params[1] == "NVDA"
    assert '"source":"api"' in params[7]


def test_claim_uses_skip_locked_and_marks_job_running(monkeypatch) -> None:
    connection = FakeConnection([FakeCursor(row=_row(status="running", attempt_count=1, worker_id="worker-a"))])
    monkeypatch.setattr(jobs, "connect_database", lambda _url: connection)

    job = jobs.claim_next_prediction_job("postgresql://test", "worker-a", now=NOW)

    assert job is not None
    assert job.status == "running"
    assert job.attempt_count == 1
    assert job.worker_id == "worker-a"
    assert "FOR UPDATE SKIP LOCKED" in connection.queries[0][0]


def test_complete_requires_owned_running_job(monkeypatch) -> None:
    connection = FakeConnection([FakeCursor(row=_row(status="completed"))])
    monkeypatch.setattr(jobs, "connect_database", lambda _url: connection)

    completed = jobs.complete_prediction_job(
        "postgresql://test",
        "job-1",
        "worker-a",
        jobs.PredictionJobResult(result_run_id="request-1", prediction_batch_id="batch-1"),
        now=NOW,
    )

    assert completed.status == "completed"
    assert completed.prediction_batch_id == "batch-1"
    assert "status = 'running'" in connection.queries[0][0]
    assert "worker_id = %s" in connection.queries[0][0]


def test_fail_requeues_retryable_job_and_terminally_fails_exhausted_job(monkeypatch) -> None:
    retry_connection = FakeConnection(
        [
            FakeCursor(row=_row(status="running", attempt_count=1, worker_id="worker-a")),
            FakeCursor(row=_row(status="queued", attempt_count=1, failure_code="provider_unavailable")),
        ]
    )
    monkeypatch.setattr(jobs, "connect_database", lambda _url: retry_connection)

    retried = jobs.fail_prediction_job(
        "postgresql://test",
        "job-1",
        "worker-a",
        "provider_unavailable",
        "temporary provider outage",
        now=NOW,
    )

    assert retried.status == "queued"
    assert retried.failure_code == "provider_unavailable"
    assert "CASE WHEN %s THEN NULL ELSE %s END" in retry_connection.queries[1][0]

    terminal_connection = FakeConnection(
        [
            FakeCursor(row=_row(status="running", attempt_count=3, worker_id="worker-a")),
            FakeCursor(row=_row(status="failed", attempt_count=3, failure_code="insufficient_history")),
        ]
    )
    monkeypatch.setattr(jobs, "connect_database", lambda _url: terminal_connection)
    failed = jobs.fail_prediction_job(
        "postgresql://test",
        "job-1",
        "worker-a",
        "insufficient_history",
        "not enough bars",
        now=NOW,
    )

    assert failed.status == "failed"


def test_worker_completes_a_job_and_handles_idle(monkeypatch) -> None:
    job = jobs._job_from_row(_row(status="running", attempt_count=1, worker_id="worker-a"))
    assert job is not None
    calls: list[str] = []
    claimed = iter([job, None])
    monkeypatch.setattr(jobs, "recover_stale_prediction_jobs", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(jobs, "claim_next_prediction_job", lambda *_args, **_kwargs: next(claimed))
    monkeypatch.setattr(
        jobs,
        "complete_prediction_job",
        lambda *_args, **_kwargs: calls.append("completed") or job,
    )

    summary = jobs.run_prediction_worker(
        "postgresql://test",
        "worker-a",
        lambda _job: jobs.PredictionJobResult(result_run_id="request-1"),
        once=False,
        max_jobs=1,
    )

    assert summary.claimed_count == 1
    assert summary.completed_count == 1
    assert summary.failed_count == 0
    assert calls == ["completed"]


def test_worker_persists_typed_failure_and_retry_count(monkeypatch) -> None:
    job = jobs._job_from_row(_row(status="running", attempt_count=1, worker_id="worker-a"))
    assert job is not None
    failed_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(jobs, "recover_stale_prediction_jobs", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(jobs, "claim_next_prediction_job", lambda *_args, **_kwargs: job)

    def fake_fail(*_args, **kwargs):
        failed_calls.append((_args[3], kwargs.get("retryable", False)))
        return job.model_copy(update={"status": "queued", "failure_code": "provider_unavailable"})

    monkeypatch.setattr(jobs, "fail_prediction_job", fake_fail)

    def failing_processor(_job):
        raise jobs.PredictionJobFailure("provider_unavailable", "temporary")

    summary = jobs.run_prediction_worker(
        "postgresql://test",
        "worker-a",
        failing_processor,
        once=True,
    )

    assert summary.failed_count == 1
    assert summary.retried_count == 1
    assert failed_calls == [("provider_unavailable", True)]


def test_market_bar_reader_returns_ascending_normalized_frame(monkeypatch) -> None:
    connection = FakeConnection(
        [
            FakeCursor(
                rows=[
                    (NOW, "NVDA", 102, 103, 101, 102.5, 102.5, 1000),
                    (NOW.replace(hour=1), "NVDA", 100, 101, 99, 100.5, 100.5, 900),
                ]
            )
        ]
    )
    monkeypatch.setattr("tsi.data.postgres.connect_database", lambda _url: connection)

    frame = read_market_bars_from_postgres("postgresql://test", "NVDA")

    assert frame["date"].tolist() == [NOW.replace(hour=1), NOW]
    assert frame["ticker"].tolist() == ["NVDA", "NVDA"]
    assert list(frame.columns) == ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def test_failure_classifier_maps_stable_codes() -> None:
    assert jobs.classify_prediction_failure(ValueError("insufficient history")) == (
        "insufficient_history",
        False,
    )
    assert jobs.classify_prediction_failure(RuntimeError("provider timeout")) == (
        "provider_unavailable",
        True,
    )
    assert jobs.classify_prediction_failure(
        jobs.PredictionJobFailure("stale_data", "stale", retryable=False)
    ) == ("stale_data", False)
