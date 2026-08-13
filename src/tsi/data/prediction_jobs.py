"""PostgreSQL-backed prediction job queue and worker primitives.

The queue deliberately lives beside the existing PostgreSQL serving helpers.
Workers claim one row with ``FOR UPDATE SKIP LOCKED`` and must complete or
fail that row before claiming another one.  A caller-provided idempotency key,
combined with the existing unique prediction-batch ``run_id``, makes retries
safe when a worker crashes after writing output but before acknowledging the
job.
"""

from __future__ import annotations

import os
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tsi.data.postgres import connect_database, read_market_bars_from_postgres

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
JobMarket = Literal["auto", "us", "twse", "tpex", "emerging"]
JobInterval = Literal["1m", "5m", "1d"]
JobFailureCode = Literal[
    "provider_unavailable",
    "insufficient_history",
    "prediction_failed",
    "stale_data",
    "unsupported_market",
    "unsupported_interval",
    "database_error",
    "worker_error",
    "unknown",
]

JOB_SCHEMA_VERSION = "prediction_job.v1"
_JOB_COLUMNS = """
    id, idempotency_key, ticker, market, feature_interval, status,
    attempt_count, max_attempts, available_at, enqueued_at, started_at,
    completed_at, worker_id, locked_at, prediction_batch_id, result_run_id,
    failure_code, failure_message, request_payload, created_at, updated_at
"""


class PredictionJobRequest(BaseModel):
    """Validated enqueue request shared by CLI, API, and worker adapters."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = JOB_SCHEMA_VERSION
    idempotency_key: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=200)
    ticker: str = Field(min_length=1, max_length=32)
    market: JobMarket = "auto"
    feature_interval: JobInterval = "1d"
    max_attempts: int = Field(default=3, ge=1, le=8)
    request_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identifiers(self) -> "PredictionJobRequest":
        if not self.ticker.strip():
            raise ValueError("ticker must not be empty")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        return self

    def normalized(self) -> "PredictionJobRequest":
        """Return a copy with identifier fields normalized as strings."""

        return self.model_copy(update={"ticker": self.ticker.strip().upper()})


class PredictionJob(BaseModel):
    """Persisted job row and its current lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = JOB_SCHEMA_VERSION
    id: str
    idempotency_key: str
    ticker: str
    market: JobMarket
    feature_interval: JobInterval
    status: JobStatus
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    available_at: datetime
    enqueued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None
    locked_at: datetime | None = None
    prediction_batch_id: str | None = None
    result_run_id: str | None = None
    failure_code: str = ""
    failure_message: str = ""
    request_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PredictionJobResult(BaseModel):
    """Output metadata written when a worker completes a job."""

    model_config = ConfigDict(extra="forbid")

    prediction_batch_id: str | None = None
    result_run_id: str


class WorkerRunSummary(BaseModel):
    """Deterministic worker tick summary suitable for logs and smoke tests."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "prediction_worker.v1"
    worker_id: str
    claimed_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    retried_count: int = Field(ge=0)
    idle: bool


class PredictionJobStateError(RuntimeError):
    """Raised when a worker tries to apply a transition it does not own."""


class PredictionJobFailure(RuntimeError):
    """Typed worker failure that can be persisted and optionally retried."""

    def __init__(self, code: JobFailureCode, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _utc(value: datetime | None = None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _job_from_row(row: tuple[Any, ...] | list[Any] | None) -> PredictionJob | None:
    if row is None:
        return None
    values = list(row)
    if len(values) != 21:
        raise ValueError(f"prediction job row must contain 21 columns, got {len(values)}")
    return PredictionJob(
        id=str(values[0]),
        idempotency_key=str(values[1]),
        ticker=str(values[2]),
        market=values[3],
        feature_interval=values[4],
        status=values[5],
        attempt_count=int(values[6]),
        max_attempts=int(values[7]),
        available_at=_utc(values[8]),
        enqueued_at=_utc(values[9]),
        started_at=_optional_utc(values[10]),
        completed_at=_optional_utc(values[11]),
        worker_id=values[12],
        locked_at=_optional_utc(values[13]),
        prediction_batch_id=str(values[14]) if values[14] is not None else None,
        result_run_id=str(values[15]) if values[15] is not None else None,
        failure_code=str(values[16] or ""),
        failure_message=str(values[17] or ""),
        request_payload=dict(values[18] or {}),
        created_at=_utc(values[19]),
        updated_at=_utc(values[20]),
    )


def _optional_utc(value: Any) -> datetime | None:
    return None if value is None else _utc(value)


def enqueue_prediction_job(
    database_url: str,
    request: PredictionJobRequest,
    *,
    now: datetime | None = None,
) -> PredictionJob:
    """Insert or return a job using the caller's idempotency key."""

    normalized = request.normalized()
    timestamp = _utc(now)
    with connect_database(database_url) as connection:
        with connection.transaction():
            cursor = connection.execute(
                f"""
                INSERT INTO prediction_jobs (
                    idempotency_key, ticker, market, feature_interval, status,
                    max_attempts, available_at, enqueued_at, request_payload,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, 'queued', %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (idempotency_key)
                DO UPDATE SET updated_at = prediction_jobs.updated_at
                RETURNING {_JOB_COLUMNS}
                """,
                (
                    normalized.idempotency_key,
                    normalized.ticker,
                    normalized.market,
                    normalized.feature_interval,
                    normalized.max_attempts,
                    timestamp,
                    timestamp,
                    _json_text(normalized.request_payload),
                    timestamp,
                    timestamp,
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    job = _job_from_row(row)
    if job is None:
        raise RuntimeError("prediction job insert returned no row")
    return job


def get_prediction_job(database_url: str, job_id: str) -> PredictionJob | None:
    """Read one job by UUID."""

    with connect_database(database_url) as connection:
        row = connection.execute(
            f"SELECT {_JOB_COLUMNS} FROM prediction_jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
    return _job_from_row(row)


def claim_next_prediction_job(
    database_url: str,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> PredictionJob | None:
    """Atomically claim the oldest available queued job for one worker."""

    normalized_worker = worker_id.strip()
    if not normalized_worker:
        raise ValueError("worker_id must not be empty")
    timestamp = _utc(now)
    with connect_database(database_url) as connection:
        with connection.transaction():
            cursor = connection.execute(
                f"""
                WITH candidate AS (
                    SELECT id
                    FROM prediction_jobs
                    WHERE status = 'queued' AND available_at <= %s
                    ORDER BY created_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE prediction_jobs AS job
                SET status = 'running',
                    attempt_count = job.attempt_count + 1,
                    started_at = %s,
                    worker_id = %s,
                    locked_at = %s,
                    updated_at = %s
                FROM candidate
                WHERE job.id = candidate.id
                RETURNING {_JOB_COLUMNS}
                """,
                (timestamp, timestamp, normalized_worker, timestamp, timestamp),
            )
            row = cursor.fetchone()
        connection.commit()
    return _job_from_row(row)


def complete_prediction_job(
    database_url: str,
    job_id: str,
    worker_id: str,
    result: PredictionJobResult,
    *,
    now: datetime | None = None,
) -> PredictionJob:
    """Mark an owned running job completed and attach output metadata."""

    timestamp = _utc(now)
    with connect_database(database_url) as connection:
        with connection.transaction():
            cursor = connection.execute(
                f"""
                UPDATE prediction_jobs
                SET status = 'completed', completed_at = %s, updated_at = %s,
                    worker_id = NULL, locked_at = NULL,
                    prediction_batch_id = %s, result_run_id = %s,
                    failure_code = '', failure_message = ''
                WHERE id = %s AND status = 'running' AND worker_id = %s
                RETURNING {_JOB_COLUMNS}
                """,
                (
                    timestamp,
                    timestamp,
                    result.prediction_batch_id,
                    result.result_run_id,
                    job_id,
                    worker_id,
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    job = _job_from_row(row)
    if job is None:
        raise PredictionJobStateError(f"job {job_id} is not running for worker {worker_id}")
    return job


def fail_prediction_job(
    database_url: str,
    job_id: str,
    worker_id: str,
    code: JobFailureCode,
    message: str,
    *,
    retryable: bool = True,
    retry_delay_seconds: float = 5.0,
    now: datetime | None = None,
) -> PredictionJob:
    """Persist a typed failure and requeue while attempts remain."""

    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds must be non-negative")
    timestamp = _utc(now)
    with connect_database(database_url) as connection:
        with connection.transaction():
            current = _job_from_row(
                connection.execute(
                    f"SELECT {_JOB_COLUMNS} FROM prediction_jobs WHERE id = %s FOR UPDATE",
                    (job_id,),
                ).fetchone()
            )
            if current is None or current.status != "running" or current.worker_id != worker_id:
                raise PredictionJobStateError(f"job {job_id} is not owned by worker {worker_id}")
            should_retry = retryable and current.attempt_count < current.max_attempts
            next_status: JobStatus = "queued" if should_retry else "failed"
            available_at = timestamp + timedelta(seconds=retry_delay_seconds) if should_retry else timestamp
            cursor = connection.execute(
                f"""
                UPDATE prediction_jobs
                SET status = %s, available_at = %s,
                    completed_at = CASE WHEN %s THEN NULL ELSE %s END,
                    worker_id = NULL, locked_at = NULL,
                    failure_code = %s, failure_message = %s, updated_at = %s
                WHERE id = %s AND status = 'running' AND worker_id = %s
                RETURNING {_JOB_COLUMNS}
                """,
                (
                    next_status,
                    available_at,
                    should_retry,
                    timestamp,
                    code,
                    message[:2000],
                    timestamp,
                    job_id,
                    worker_id,
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    result = _job_from_row(row)
    if result is None:
        raise PredictionJobStateError(f"job {job_id} changed before failure was recorded")
    return result


def recover_stale_prediction_jobs(
    database_url: str,
    *,
    lease_seconds: int = 900,
    now: datetime | None = None,
) -> int:
    """Requeue abandoned running jobs or terminally fail exhausted attempts."""

    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    timestamp = _utc(now)
    cutoff = timestamp - timedelta(seconds=lease_seconds)
    with connect_database(database_url) as connection:
        with connection.transaction():
            cursor = connection.execute(
                """
                UPDATE prediction_jobs
                SET status = CASE WHEN attempt_count < max_attempts THEN 'queued' ELSE 'failed' END,
                    available_at = %s,
                    completed_at = CASE WHEN attempt_count < max_attempts THEN NULL ELSE %s END,
                    worker_id = NULL, locked_at = NULL,
                    failure_code = CASE WHEN attempt_count < max_attempts THEN failure_code ELSE 'worker_error' END,
                    failure_message = CASE
                        WHEN attempt_count < max_attempts THEN failure_message
                        ELSE 'worker lease expired after maximum attempts'
                    END,
                    updated_at = %s
                WHERE status = 'running' AND locked_at < %s
                RETURNING id
                """,
                (timestamp, timestamp, timestamp, cutoff),
            )
            count = len(cursor.fetchall())
        connection.commit()
    return count


def classify_prediction_failure(error: Exception) -> tuple[JobFailureCode, bool]:
    """Map common worker exceptions to stable API-facing failure codes."""

    if isinstance(error, PredictionJobFailure):
        return error.code, error.retryable
    text = str(error).lower()
    if "insufficient" in text or "not enough" in text:
        return "insufficient_history", False
    if "stale" in text or "freshness" in text:
        return "stale_data", False
    if "provider" in text or "download" in text or "yfinance" in text:
        return "provider_unavailable", True
    if "unsupported" in text or "market" in text:
        return "unsupported_market", False
    return "prediction_failed", False


PredictionJobProcessor = Callable[[PredictionJob], PredictionJobResult]
SleepFunction = Callable[[float], None]


def run_prediction_worker(
    database_url: str,
    worker_id: str,
    processor: PredictionJobProcessor,
    *,
    poll_seconds: float = 5.0,
    lease_seconds: int = 900,
    retry_delay_seconds: float = 5.0,
    once: bool = False,
    max_jobs: int | None = None,
    sleep_fn: SleepFunction = time.sleep,
) -> WorkerRunSummary:
    """Run a graceful claim/process/ack loop, optionally for one tick."""

    if poll_seconds < 0:
        raise ValueError("poll_seconds must be non-negative")
    if max_jobs is not None and max_jobs < 1:
        raise ValueError("max_jobs must be positive when provided")
    recover_stale_prediction_jobs(database_url, lease_seconds=lease_seconds)
    claimed = completed = failed = retried = 0
    while max_jobs is None or claimed < max_jobs:
        job = claim_next_prediction_job(database_url, worker_id)
        if job is None:
            if once:
                break
            sleep_fn(poll_seconds)
            continue
        claimed += 1
        try:
            result = processor(job)
            complete_prediction_job(database_url, job.id, worker_id, result)
            completed += 1
        except Exception as error:  # worker failures become typed persisted state
            code, retryable = classify_prediction_failure(error)
            failed_job = fail_prediction_job(
                database_url,
                job.id,
                worker_id,
                code,
                str(error),
                retryable=retryable,
                retry_delay_seconds=retry_delay_seconds,
            )
            failed += 1
            if failed_job.status == "queued":
                retried += 1
        if once:
            break
    return WorkerRunSummary(
        worker_id=worker_id,
        claimed_count=claimed,
        completed_count=completed,
        failed_count=failed,
        retried_count=retried,
        idle=claimed == 0,
    )


def build_market_bar_prediction_processor(
    database_url: str,
    *,
    output_root: str = "data/artifacts/prediction_jobs",
) -> PredictionJobProcessor:
    """Build the local baseline processor from persisted market bars.

    The current trusted baseline is daily. Intraday jobs remain queueable, but
    fail explicitly until an interval-trained model is available.
    """

    def process(job: PredictionJob) -> PredictionJobResult:
        if job.feature_interval != "1d":
            raise PredictionJobFailure(
                "unsupported_interval",
                "the current baseline worker consumes 1d market bars only",
                retryable=False,
            )
        frame = read_market_bars_from_postgres(
            database_url,
            job.ticker,
            interval=job.feature_interval,
            provider="yfinance",
            limit=5000,
        )
        if frame.empty or frame["ticker"].nunique() == 0:
            raise PredictionJobFailure("insufficient_history", "no persisted market bars for prediction", retryable=False)
        if len(frame) < 80:
            raise PredictionJobFailure(
                "insufficient_history",
                f"only {len(frame)} persisted bars are available; at least 80 are required",
                retryable=False,
            )
        return _run_baseline_from_market_bars(job, frame, database_url, output_root)

    return process


def _run_baseline_from_market_bars(
    job: PredictionJob,
    frame: pd.DataFrame,
    database_url: str,
    output_root: str,
) -> PredictionJobResult:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from scripts.predict_latest_baseline import parse_args, run_prediction
    from tsi.data.postgres import read_prediction_batch_id

    with TemporaryDirectory(prefix=f"tsi-job-{job.id}-") as temporary:
        root = Path(temporary)
        input_path = root / "market_bars.csv"
        output_path = Path(output_root) / f"{job.id}.csv"
        json_path = Path(output_root) / f"{job.id}.json"
        frame.to_csv(input_path, index=False)
        run_prediction(
            parse_args(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--json-output",
                    str(json_path),
                    "--run-id",
                    job.idempotency_key,
                    "--write-db",
                    "--database-url",
                    database_url,
                    "--feature-interval",
                    job.feature_interval,
                ]
            )
        )
    return PredictionJobResult(
        prediction_batch_id=read_prediction_batch_id(database_url, job.idempotency_key),
        result_run_id=job.idempotency_key,
    )


def default_worker_id() -> str:
    """Return a stable-enough local worker identifier for logs and leases."""

    return f"{socket.gethostname()}:{os.getpid()}"


def _json_text(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), default=str)
