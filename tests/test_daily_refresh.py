"""Daily refresh must publish only complete, persisted, validated candidates."""
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from tests.test_evaluate_selective_trust import _write_ohlcv
from tsi.data import daily_refresh as daily
from tsi.data.download import DownloadFrameResult, DownloadTicker
from tsi.serving.bundle import load_serving_bundle

NOW = datetime(2021, 1, 1, 12, tzinfo=UTC)


@pytest.fixture
def refresh_setup(tmp_path, monkeypatch):
    seed = tmp_path / "seed.csv"
    _write_ohlcv(seed)
    frame = pd.read_csv(seed, dtype={"ticker": str})
    frame["ticker"] = frame["ticker"].replace({"AAA": "0050", "BBB": "5240"})
    frame.to_csv(seed, index=False)
    result = DownloadFrameResult(
        dataset_name="daily_taiwan", tickers=[
            DownloadTicker(t, f"{t}.TW", "twse") for t in sorted(frame.ticker.unique())
        ], ohlcv=frame, start="2015-01-01", end="2021-01-02", interval="1d",
        failed_batches=[],
    )
    calls = []
    monkeypatch.setattr(daily, "download_ticker_frame", lambda **kw: result)
    monkeypatch.setattr(daily, "write_download_to_postgres", lambda *a, **kw: calls.append("bars"))
    monkeypatch.setattr(daily, "read_market_bars_from_postgres", lambda url, ticker, **kw:
                        result.ohlcv[result.ohlcv.ticker == ticker].copy())
    monkeypatch.setattr(daily, "write_prediction_batch_to_postgres",
                        lambda *a, **kw: calls.append("warnings"))
    config = daily.DailyRefreshConfig(
        market="taiwan", seed_input=seed, bundle_root=tmp_path / "bundles",
        runs_root=tmp_path / "runs",
    )
    return config, result, calls


def test_publish_persisted_daily_model_with_string_tickers(refresh_setup):
    config, _, calls = refresh_setup
    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)
    bundle = load_serving_bundle(Path("taiwan.json"), root=config.bundle_root)
    assert report.status == "published"
    assert bundle.run_id == report.run_id
    assert bundle.feature_interval == "1d"
    assert calls == ["bars", "warnings"]
    assert report.tickers == ["0050", "00981A", "2330", "5240"]
    assert len(report.bundle_sha256) == 64
    saved = daily.DailyRefreshReport.model_validate_json(
        (config.runs_root / report.run_id / "status.json").read_text()
    )
    assert saved == report


def test_db_failure_retains_previous_model_and_records_safe_error(refresh_setup, monkeypatch):
    config, _, _ = refresh_setup
    daily.refresh_daily(config, "postgresql://unused", now=NOW)
    previous = (config.bundle_root / "taiwan.json").read_bytes()

    def fail(*a, **kw):
        raise RuntimeError("password=never-log-this")

    monkeypatch.setattr(daily, "write_prediction_batch_to_postgres", fail)
    with pytest.raises(RuntimeError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert (config.bundle_root / "taiwan.json").read_bytes() == previous
    reports = [daily.DailyRefreshReport.model_validate_json(p.read_text())
               for p in config.runs_root.glob("*/status.json")]
    failed = next(r for r in reports if r.status == "failed")
    assert failed.stage == "persist_predictions"
    assert failed.error_type == "RuntimeError"
    assert "never-log-this" not in failed.model_dump_json()


@pytest.mark.parametrize("problem", ["missing", "stale", "invalid", "future"])
def test_reject_bad_provider_snapshot_before_persistence(refresh_setup, problem):
    config, result, calls = refresh_setup
    if problem == "missing":
        result.ohlcv.drop(result.ohlcv[result.ohlcv.ticker == "5240"].index, inplace=True)
    elif problem == "stale":
        result.ohlcv["date"] = "2010-01-01"
    elif problem == "future":
        result.ohlcv.loc[0, "date"] = "2021-01-02"
    else:
        result.ohlcv.loc[0, "high"] = 0
    with pytest.raises(ValueError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert calls == []
    assert not (config.bundle_root / "taiwan.json").exists()
    assert any(config.runs_root.glob("*/status.json"))


def test_concurrent_refresh_does_not_touch_active_run(refresh_setup):
    config, _, calls = refresh_setup
    with daily.refresh_lock(config.bundle_root, config.market):
        with pytest.raises(RuntimeError, match="already running"):
            daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert calls == []


def test_completed_session_cutoff_observes_market_timezone():
    now = datetime(2026, 10, 15, 6, tzinfo=UTC)
    assert daily.completed_daily_end("taiwan", now).isoformat() == "2026-10-15"
    assert daily.completed_daily_end("us", now).isoformat() == "2026-10-15"
    assert daily.completed_daily_end("taiwan", now.replace(hour=12)).isoformat() == "2026-10-16"


def test_database_required_before_any_provider_io(refresh_setup):
    config, _, calls = refresh_setup
    with pytest.raises(ValueError, match="database"):
        daily.refresh_daily(config, "", now=NOW)
    assert calls == []


def test_training_snapshot_comes_from_database(refresh_setup, monkeypatch):
    config, result, _ = refresh_setup
    stored = result.ohlcv.copy()
    price_columns = ["open", "high", "low", "close", "adj_close"]
    stored[price_columns] = stored[price_columns] * 2
    monkeypatch.setattr(daily, "read_market_bars_from_postgres", lambda url, ticker, **kw:
                        stored[stored.ticker == ticker].copy())
    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)
    snapshot = pd.read_csv(config.runs_root / report.run_id / "ohlcv.csv", dtype={"ticker": str})
    assert snapshot.close.max() == pytest.approx(stored.close.max())
    assert snapshot.close.max() > result.ohlcv.close.max()


def test_reject_wrong_market_universe(refresh_setup):
    config, _, calls = refresh_setup
    config.market = "us"
    with pytest.raises(ValueError, match="market"):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert calls == []


def test_recover_committed_candidate_without_refetch(refresh_setup, monkeypatch):
    config, _, _ = refresh_setup
    daily.refresh_daily(config, "postgresql://unused", now=NOW)
    previous = (config.bundle_root / "taiwan.json").read_bytes()
    publish = daily.write_serving_bundle

    def disk_failure(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(daily, "write_serving_bundle", disk_failure)
    with pytest.raises(OSError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert (config.bundle_root / "taiwan.json").read_bytes() == previous
    reports = [daily.DailyRefreshReport.model_validate_json(p.read_text())
               for p in config.runs_root.glob("*/status.json")]
    pending = next(r for r in reports if r.status == "publication_pending")
    monkeypatch.setattr(daily, "write_serving_bundle", publish)
    monkeypatch.setattr(daily, "read_prediction_batch_id", lambda *a: "persisted-batch")

    def no_network(**kw):
        raise AssertionError("Recovery must not refetch provider history")

    monkeypatch.setattr(daily, "download_ticker_frame", no_network)
    recovered = daily.refresh_daily(config, "postgresql://unused", now=NOW)
    assert recovered.status == "published"
    assert recovered.run_id == pending.run_id
    assert load_serving_bundle(Path("taiwan.json"), root=config.bundle_root).run_id == pending.run_id


def test_old_pending_publication_also_refreshes_new_market_cutoff(refresh_setup, monkeypatch):
    config, result, _ = refresh_setup
    publish = daily.write_serving_bundle

    def disk_failure(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(daily, "write_serving_bundle", disk_failure)
    with pytest.raises(OSError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    monkeypatch.setattr(daily, "write_serving_bundle", publish)
    monkeypatch.setattr(daily, "read_prediction_batch_id", lambda *a: "persisted-batch")
    downloads = []

    def download(**kw):
        downloads.append(kw["end"])
        return result

    monkeypatch.setattr(daily, "download_ticker_frame", download)
    report = daily.refresh_daily(config, "postgresql://unused", now=NOW.replace(day=2))
    assert report.status == "published"
    assert downloads == ["2021-01-03"]
    assert report.started_at == NOW.replace(day=2)
