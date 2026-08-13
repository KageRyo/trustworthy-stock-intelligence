"""Deterministic PostgreSQL-backed watchlist-to-warning smoke test.

The test is opt-in because it owns an isolated PostgreSQL database and starts
the Go API. CI enables it with ``TSI_E2E_DATABASE_URL``; ordinary local pytest
runs keep the fast unit-test default and report this test as skipped.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import pytest

from tsi.data.download import DownloadFrameResult, DownloadTicker
from tsi.data.postgres import (
    read_market_bars_from_postgres,
    read_watchlist_tickers,
    write_download_to_postgres,
    write_prediction_batch_to_postgres,
)
from tsi.data.prediction_jobs import (
    PredictionJobFailure,
    PredictionJobRequest,
    PredictionJobResult,
    enqueue_prediction_job,
    get_prediction_job,
    run_prediction_worker,
)
from tsi.data.provider_health import ProviderHealthSnapshot
from tsi.serving.schema import PredictionBatch, PredictionRecord


DATABASE_URL = os.getenv("TSI_E2E_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="set TSI_E2E_DATABASE_URL to run the PostgreSQL/API end-to-end test",
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_PORT = os.getenv("TSI_E2E_API_PORT", "18081")


def _psycopg() -> object:
    """Load the optional PostgreSQL driver only when the E2E test is enabled."""

    try:
        import psycopg
    except ModuleNotFoundError as error:
        pytest.skip(f"install the db extra for PostgreSQL E2E tests: {error}")
    return psycopg


def _apply_migrations(database_url: str) -> None:
    migration_dir = REPOSITORY_ROOT / "infra" / "postgres" / "init"
    with _psycopg().connect(database_url) as connection:
        for migration in sorted(migration_dir.glob("*.sql")):
            connection.execute(migration.read_text(encoding="utf-8"))
        connection.commit()


def _seed_watchlist(database_url: str) -> None:
    with _psycopg().connect(database_url) as connection:
        connection.execute(
            """
            INSERT INTO watchlists (name, description, is_default)
            VALUES (%s, %s, false)
            ON CONFLICT (name) DO NOTHING
            """,
            ("e2e", "deterministic CI watchlist"),
        )
        ticker_id = connection.execute(
            "SELECT id FROM tickers WHERE market = 'us' AND symbol = 'NVDA'"
        ).fetchone()
        watchlist_id = connection.execute(
            "SELECT id FROM watchlists WHERE name = 'e2e'"
        ).fetchone()
        assert ticker_id is not None
        assert watchlist_id is not None
        connection.execute(
            """
            INSERT INTO watchlist_tickers (watchlist_id, ticker_id, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (watchlist_id, ticker_id)
            DO UPDATE SET removed_at = NULL
            """,
            (watchlist_id[0], ticker_id[0], "fake-provider coverage"),
        )
        connection.commit()


def _fake_download_result(now: datetime) -> DownloadFrameResult:
    dates = pd.date_range(
        end=pd.Timestamp(now.date(), tz="UTC"),
        periods=90,
        freq="D",
    )
    closes = pd.Series(range(100, 190), dtype="float64")
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": "NVDA",
            "open": closes - 1,
            "high": closes + 2,
            "low": closes - 2,
            "close": closes,
            "adj_close": closes,
            "volume": 1_000_000,
        }
    )
    snapshot = ProviderHealthSnapshot(
        provider="fake",
        market="us",
        ticker="NVDA",
        query_symbol="NVDA",
        status="healthy",
        coverage="available",
        attempt_count=1,
        success_count=1,
        failure_count=0,
        consecutive_failures=0,
        last_success_at=now,
        observed_at=now,
    )
    return DownloadFrameResult(
        dataset_name="e2e-fake-provider",
        tickers=[DownloadTicker(ticker="NVDA", query_symbol="NVDA", market="us")],
        ohlcv=frame,
        start=str(dates[0].date()),
        end=str(dates[-1].date()),
        interval="1d",
        failed_batches=[],
        provider_health=[snapshot],
    )


def _prediction_batch(now: datetime) -> PredictionBatch:
    timestamp = now.isoformat()
    return PredictionBatch(
        schema_version="v1",
        run_id="e2e-run-1",
        data_as_of=timestamp,
        generated_at=timestamp,
        feature_interval="1d",
        records=[
            PredictionRecord(
                date=now.date().isoformat(),
                ticker="NVDA",
                model="e2e_model",
                model_bundle="e2e_bundle",
                risk_probability=0.4,
                calibrated_risk_probability=0.35,
                calibration_method="fixed",
                uncertainty_score=0.1,
                trust_score=0.8,
                alert_threshold=0.3,
                watch_threshold=0.15,
                warning_level="alert",
                reason_codes=[
                    "probability_above_alert_threshold",
                    "warning_level_alert",
                ],
            )
        ],
    )


def _wait_for_api(process: subprocess.Popen[str], base_url: str) -> None:
    deadline = time.monotonic() + 60
    last_error = "API did not become ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.communicate()[0]
            raise AssertionError(f"Go API exited before readiness: {output[-4000:]}")
        try:
            with urlopen(f"{base_url}/readyz", timeout=2) as response:
                if response.status == 200:
                    return
                last_error = f"readiness returned HTTP {response.status}"
        except (OSError, URLError) as error:
            last_error = str(error)
        time.sleep(0.5)
    raise AssertionError(last_error)


def test_watchlist_to_warning_pipeline(tmp_path: Path) -> None:
    """Persist fake bars, complete/fail jobs, then validate Go API payloads."""

    assert DATABASE_URL
    _apply_migrations(DATABASE_URL)
    now = datetime.now(UTC).replace(microsecond=0)
    ingestion = write_download_to_postgres(
        DATABASE_URL,
        _fake_download_result(now),
        provider="yfinance",
        universe_name="e2e",
    )
    assert ingestion.row_count == 90
    _seed_watchlist(DATABASE_URL)
    assert read_watchlist_tickers(DATABASE_URL, "e2e") == ["NVDA"]
    bars = read_market_bars_from_postgres(DATABASE_URL, "NVDA", interval="1d", limit=100)
    assert len(bars) == 90

    batch = _prediction_batch(now)

    def processor(job: object) -> PredictionJobResult:
        summary = write_prediction_batch_to_postgres(DATABASE_URL, batch, feature_interval="1d")
        return PredictionJobResult(
            prediction_batch_id=summary.prediction_batch_id,
            result_run_id=summary.run_id,
        )

    completed_job = enqueue_prediction_job(
        DATABASE_URL,
        PredictionJobRequest(
            idempotency_key="e2e-job-1",
            ticker="NVDA",
            market="us",
            feature_interval="1d",
        ),
    )
    summary = run_prediction_worker(
        DATABASE_URL,
        "e2e-worker",
        processor,
        once=True,
        max_jobs=1,
    )
    assert summary.completed_count == 1
    completed = get_prediction_job(DATABASE_URL, completed_job.id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.prediction_batch_id
    with _psycopg().connect(DATABASE_URL) as connection:
        warning_count = connection.execute("SELECT count(*) FROM warning_records").fetchone()[0]
    assert warning_count == 1

    failed_job = enqueue_prediction_job(
        DATABASE_URL,
        PredictionJobRequest(
            idempotency_key="e2e-job-failure",
            ticker="MISSING",
            market="us",
            feature_interval="1d",
        ),
    )

    def failing_processor(job: object) -> PredictionJobResult:
        raise PredictionJobFailure(
            "insufficient_history",
            "deterministic fake provider returned no bars",
            retryable=False,
        )

    failed_summary = run_prediction_worker(
        DATABASE_URL,
        "e2e-failure-worker",
        failing_processor,
        once=True,
        max_jobs=1,
    )
    assert failed_summary.failed_count == 1
    failed = get_prediction_job(DATABASE_URL, failed_job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure_code == "insufficient_history"

    api_binary = os.getenv("TSI_E2E_API_BINARY", "").strip()
    command = [api_binary] if api_binary else ["go", "run", "./cmd/server"]
    api_environment = os.environ.copy()
    api_environment.update(
        {
            "TSI_DATABASE_URL": DATABASE_URL,
            "TSI_API_ADDR": f":{API_PORT}",
            "TSI_CORS_ALLOWED_ORIGINS": "*",
        }
    )
    process = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT / "services" / "api-gateway-go",
        env=api_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{API_PORT}"
    try:
        _wait_for_api(process, base_url)
        with urlopen(f"{base_url}/api/v1/analysis/NVDA", timeout=5) as response:
            analysis = json.load(response)
        assert analysis["schema_version"] == "analysis.v1"
        assert analysis["ticker"] == "NVDA"
        assert analysis["warning"]["level"] == "alert"
        assert analysis["data_freshness"]["freshness"]["schema_version"] == "freshness.v1"

        with urlopen(f"{base_url}/api/v1/watchlists/e2e", timeout=5) as response:
            watchlist = json.load(response)
        assert watchlist["schema_version"] == "watchlist.v1"
        assert watchlist["tickers"][0]["ticker"] == "NVDA"
        assert watchlist["tickers"][0]["latest_warning"]["warning_level"] == "alert"

        payload_path = os.getenv("TSI_E2E_ANALYSIS_PATH", "").strip()
        if payload_path:
            Path(payload_path).write_text(json.dumps(analysis), encoding="utf-8")
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
