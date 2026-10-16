"""Fail-closed daily pooled-model refresh, with PostgreSQL as the training source.

This orchestrates the repository's local services: it trains through
``scripts/predict_latest_baseline.py`` and locks with POSIX ``fcntl``, so it runs from a
repository checkout on Linux or WSL, not from the installed package alone.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
import re
import shutil
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.data.download import DownloadFrameResult, download_ticker_frame, is_taiwan_local_ticker
from tsi.data.postgres import (
    read_market_bars_from_postgres,
    read_prediction_batch_id,
    write_download_to_postgres,
    write_prediction_batch_to_postgres,
)
from tsi.data.quality import audit_market_bars
from tsi.data.price_reconciliation import OfficialCloseCorrection, reconcile_tpex_closes
from tsi.serving.bundle import ServingModelBundle, load_serving_bundle, write_serving_bundle
from tsi.serving.schema import PredictionBatch

Market = Literal["us", "taiwan"]
RUN_ID_PATTERN = r"daily_(us|taiwan)_[0-9]{8}T[0-9]{6}_[a-f0-9]{12}"


class DailyRefreshConfig(BaseModel):
    """Paths and quality policy for one market; never contains credentials."""

    model_config = ConfigDict(extra="forbid")
    market: Market
    seed_input: Path
    bundle_root: Path
    runs_root: Path
    max_age_days: int = Field(default=7, ge=1, le=14)
    keep_runs: int = Field(default=5, ge=1, le=60)


class DailyRefreshReport(BaseModel):
    """Durable progress and provenance, including failures before database writes."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["daily_model_refresh.v1"] = "daily_model_refresh.v1"
    run_id: str
    market: Market
    status: Literal["running", "published", "failed", "publication_pending"] = "running"
    stage: str = "download"
    started_at: datetime
    finished_at: datetime | None = None
    feature_interval: Literal["1d"] = "1d"
    tickers: list[str] = Field(default_factory=list)
    data_as_of: str | None = None
    input_sha256: str | None = None
    bundle_sha256: str | None = None
    quality_status: str | None = None
    provider_price_repair: bool = False
    official_close_corrections: list[OfficialCloseCorrection] = Field(default_factory=list)
    error_type: str | None = None
    excluded_persisted_bars: int = Field(default=0, ge=0)
    pruned_runs: list[str] = Field(default_factory=list)
    retention_error_type: str | None = None


def completed_daily_end(market: Market, now: datetime) -> date:
    """Exclusive daily cutoff: include today only after a conservative 18:00 local cutoff."""
    local = now.astimezone(ZoneInfo("America/New_York" if market == "us" else "Asia/Taipei"))
    return local.date() + timedelta(days=int(local.time() >= time(18)))


@contextmanager
def refresh_lock(root: Path, market: Market) -> Iterator[None]:
    """Hold one market's nonblocking lock throughout refresh and publication."""
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    with (root / f".{market}.refresh.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Daily refresh for {market} is already running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _training_cli():
    """Load the repository training CLI lazily, so ingestion-only callers never import it."""
    try:
        from scripts.predict_latest_baseline import parse_args, run_prediction
    except ModuleNotFoundError as exc:
        if exc.name not in {"scripts", "scripts.predict_latest_baseline"}:
            raise
        raise RuntimeError(
            "Daily refresh runs from a repository checkout; the installed package does not "
            "include scripts/predict_latest_baseline.py"
        ) from exc
    return parse_args, run_prediction


def _save_report(report: DailyRefreshReport, run_dir: Path) -> None:
    temporary = run_dir / ".status.tmp"
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(run_dir / "status.json")


def _validate_frame(
    frame: pd.DataFrame, tickers: list[str], config: DailyRefreshConfig,
    end: date, now: datetime, run_dir: Path, name: str,
) -> str:
    audit = audit_market_bars(
        frame, interval="1d", provider="yfinance", expected_tickers=tickers,
        market_by_ticker={t: config.market for t in tickers},
    )
    (run_dir / f"{name}_quality.json").write_text(audit.model_dump_json(indent=2))
    if audit.fail_closed or audit.missing_tickers:
        raise ValueError("Daily data quality or universe coverage check failed")
    if set(frame.ticker.astype(str)) != set(tickers):
        raise ValueError("Daily snapshot ticker coverage mismatch")
    dates = pd.to_datetime(frame.date, utc=True)
    if dates.isna().any() or (dates.dt.date >= end).any():
        raise ValueError("Daily snapshot contains incomplete or future sessions")
    latest = dates.groupby(frame.ticker).max()
    if (latest.dt.date < (now.date() - timedelta(days=config.max_age_days))).any():
        raise ValueError("Daily snapshot contains stale tickers")
    return audit.status


def refresh_daily(
    config: DailyRefreshConfig, database_url: str, *, now: datetime | None = None,
) -> DailyRefreshReport:
    """Validate, persist, train and publish a daily model; retain active model on failure."""
    if not database_url.strip():
        raise ValueError("A database URL is required")
    _training_cli()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    with refresh_lock(config.bundle_root, config.market):
        recovered = _recover_pending(config, database_url)
        if recovered is not None and (
            completed_daily_end(config.market, recovered.started_at)
            >= completed_daily_end(config.market, now)
        ):
            return recovered
        run_id = f"daily_{config.market}_{now:%Y%m%dT%H%M%S}_{uuid4().hex[:12]}"
        run_dir = config.runs_root.resolve() / run_id
        run_dir.mkdir(parents=True)
        report = DailyRefreshReport(
            run_id=run_id, market=config.market, started_at=now, provider_price_repair=True,
        )
        _save_report(report, run_dir)
        try:
            _refresh(config, database_url, now, run_dir, report)
        except Exception as exc:
            report.status = (
                "publication_pending" if report.stage == "publish_bundle" else "failed"
            )
            report.error_type = type(exc).__name__
            report.finished_at = datetime.now(UTC)
            _apply_retention(config, report)
            _save_report(report, run_dir)
            raise
        report.status = "published"
        report.finished_at = datetime.now(UTC)
        _save_report(report, run_dir)
        _pending_path(config).unlink(missing_ok=True)
        _apply_retention(config, report)
        _save_report(report, run_dir)
        return report


def stale_runs(config: DailyRefreshConfig, current_run_id: str) -> list[Path]:
    """Select this market's run directories beyond the newest ``keep_runs``.

    The current run, the active bundle's run and a pending publication are never selected. Only
    real directories with generated run names count; links and other files are left alone.
    PostgreSQL keeps the durable batch and warning history.
    """
    root = config.runs_root.resolve()
    if not root.is_dir():
        return []
    protected = {current_run_id, *_referenced_runs(config)}
    runs = sorted(
        (
            path for path in root.iterdir()
            if path.name.startswith(f"daily_{config.market}_")
            and re.fullmatch(RUN_ID_PATTERN, path.name)
            and path.is_dir() and not path.is_symlink()
        ),
        key=lambda path: path.name, reverse=True,
    )
    return [path for path in runs[config.keep_runs:] if path.name not in protected]


def _referenced_runs(config: DailyRefreshConfig) -> set[str]:
    referenced = set()
    active_path = config.bundle_root / f"{config.market}.json"
    if active_path.exists():
        referenced.add(load_serving_bundle(Path(active_path.name), root=config.bundle_root).run_id)
    marker = _pending_path(config)
    if marker.exists():
        referenced.add(PendingPublication.model_validate_json(marker.read_text()).run_id)
    return referenced


def _apply_retention(config: DailyRefreshConfig, report: DailyRefreshReport) -> None:
    """Record pruned runs; a retention problem never changes the refresh outcome."""
    try:
        for path in stale_runs(config, report.run_id):
            shutil.rmtree(path)
            report.pruned_runs.append(path.name)
    except (OSError, ValueError) as exc:
        report.retention_error_type = type(exc).__name__


def _refresh(
    config: DailyRefreshConfig, database_url: str, now: datetime, run_dir: Path,
    report: DailyRefreshReport,
) -> None:
    parse_args, run_prediction = _training_cli()

    seed = read_ohlcv_csv(config.seed_input)
    tickers = sorted(seed.ticker.unique().tolist())
    if len(tickers) < 2 or any(not t or t == "NAN" for t in tickers):
        raise ValueError("A pooled model requires at least two valid ticker identifiers")
    if any(is_taiwan_local_ticker(t) != (config.market == "taiwan") for t in tickers):
        raise ValueError("Seed universe contains ticker identifiers from another market")
    report.tickers = tickers
    end = completed_daily_end(config.market, now)
    result = download_ticker_frame(
        tickers=tickers, start="2015-01-01", end=end.isoformat(), market="auto",
        interval="1d", batch_size=80, dataset_name=f"daily_{config.market}",
        repair_prices=True,
    )
    result.ohlcv.to_csv(run_dir / "download.csv", index=False)
    report.stage = "reconcile_official_prices"
    _save_report(report, run_dir)
    frame, report.official_close_corrections = reconcile_tpex_closes(result)
    result = DownloadFrameResult(
        dataset_name=result.dataset_name, tickers=result.tickers, ohlcv=frame,
        start=result.start, end=result.end, interval=result.interval,
        failed_batches=result.failed_batches, provider_health=result.provider_health,
    )
    report.stage = "validate_download"
    _save_report(report, run_dir)
    if result.failed_batches:
        raise ValueError("Provider reported failed batches")
    report.quality_status = _validate_frame(
        result.ohlcv, tickers, config, end, now, run_dir, "download",
    )
    report.stage = "persist_bars"
    _save_report(report, run_dir)
    write_download_to_postgres(database_url, result, universe_name=f"daily_{config.market}")
    report.stage = "read_persisted_bars"
    _save_report(report, run_dir)
    frame = pd.concat([
        read_market_bars_from_postgres(database_url, ticker, interval="1d", limit=10000)
        for ticker in tickers
    ], ignore_index=True)
    frame, report.excluded_persisted_bars = _stored_download(frame, result.ohlcv)
    report.quality_status = _validate_frame(frame, tickers, config, end, now, run_dir, "persisted")
    input_path = run_dir / "ohlcv.csv"
    frame.to_csv(input_path, index=False)
    report.input_sha256 = file_sha256(input_path)
    report.stage = "train_candidate"
    _save_report(report, run_dir)
    candidate_root = run_dir / "candidate"
    batch_path = run_dir / "warnings.json"
    args = parse_args([
        "--input", str(input_path), "--output", str(run_dir / "predictions.csv"),
        "--json-output", str(batch_path), "--run-id", report.run_id,
        "--model-bundle-root", str(candidate_root),
        "--model-bundle-output", f"{config.market}.json",
    ])
    run_prediction(args)
    report.stage = "validate_candidate"
    _save_report(report, run_dir)
    bundle = load_serving_bundle(Path(f"{config.market}.json"), root=candidate_root)
    batch = PredictionBatch.model_validate_json(batch_path.read_text())
    if sorted(record.ticker for record in batch.records) != tickers:
        raise ValueError("Prediction coverage mismatch")
    if bundle.feature_interval != "1d" or bundle.run_id != report.run_id:
        raise ValueError("Candidate model metadata mismatch")
    active_path = config.bundle_root / f"{config.market}.json"
    if active_path.exists():
        active = load_serving_bundle(Path(active_path.name), root=config.bundle_root)
        if _data_date(bundle) < _data_date(active):
            raise ValueError("Candidate model would move data_as_of backwards")
    report.data_as_of = bundle.data_as_of
    pending = PendingPublication(run_id=report.run_id)
    temporary = config.bundle_root / f".{config.market}.pending.tmp"
    temporary.write_text(pending.model_dump_json())
    temporary.replace(_pending_path(config))
    report.stage = "persist_predictions"
    _save_report(report, run_dir)
    write_prediction_batch_to_postgres(database_url, batch, feature_interval="1d")
    report.stage = "publish_bundle"
    _save_report(report, run_dir)
    write_serving_bundle(bundle, Path(active_path.name), root=config.bundle_root)
    report.bundle_sha256 = file_sha256(active_path)


def _stored_download(
    stored: pd.DataFrame, downloaded: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Keep exactly the validated download as read back from PostgreSQL.

    Daily storage uses UTC midnight. Stored bars the provider no longer returns, such as bars
    from earlier ingestion or unfinished sessions, are excluded and counted. A downloaded bar
    missing from storage fails closed.
    """
    stored = stored.assign(date=pd.to_datetime(stored.date, utc=True).dt.tz_localize(None))
    keys = pd.MultiIndex.from_arrays([stored.ticker.astype(str), stored.date.dt.date])
    wanted = pd.MultiIndex.from_arrays([
        downloaded.ticker.astype(str), pd.to_datetime(downloaded.date, utc=True).dt.date,
    ])
    if not wanted.isin(keys).all():
        raise ValueError("Persisted bars are missing rows from the validated download")
    keep = keys.isin(wanted)
    return stored[keep].sort_values(["ticker", "date"]), int((~keep).sum())


def _data_date(bundle: ServingModelBundle) -> date:
    return date.fromisoformat(bundle.data_as_of[:10])


class PendingPublication(BaseModel):
    """Only a generated run identifier may locate a recoverable candidate."""

    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=rf"^{RUN_ID_PATTERN}$")


def _pending_path(config: DailyRefreshConfig) -> Path:
    return config.bundle_root / f".{config.market}.pending.json"


def _recover_pending(
    config: DailyRefreshConfig, database_url: str,
) -> DailyRefreshReport | None:
    marker = _pending_path(config)
    if not marker.exists():
        return None
    pending = PendingPublication.model_validate_json(marker.read_text())
    if read_prediction_batch_id(database_url, pending.run_id) is None:
        marker.unlink()
        return None
    run_dir = config.runs_root.resolve() / pending.run_id
    report = DailyRefreshReport.model_validate_json((run_dir / "status.json").read_text())
    if report.market != config.market or report.run_id != pending.run_id:
        raise ValueError("Pending publication metadata mismatch")
    bundle = load_serving_bundle(Path(f"{config.market}.json"), root=run_dir / "candidate")
    if bundle.run_id != pending.run_id:
        raise ValueError("Pending bundle run mismatch")
    active_path = config.bundle_root / f"{config.market}.json"
    if active_path.exists():
        active = load_serving_bundle(Path(active_path.name), root=config.bundle_root)
        if _data_date(bundle) < _data_date(active):
            raise ValueError("Pending publication would move data_as_of backwards")
    write_serving_bundle(bundle, Path(active_path.name), root=config.bundle_root)
    report.status = "published"
    report.stage = "publish_bundle"
    report.error_type = None
    report.bundle_sha256 = file_sha256(active_path)
    report.finished_at = datetime.now(UTC)
    _save_report(report, run_dir)
    marker.unlink()
    return report
