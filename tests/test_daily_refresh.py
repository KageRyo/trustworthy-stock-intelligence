"""Daily refresh must publish only complete, persisted, validated candidates."""
from datetime import UTC, datetime
import json
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


def test_published_model_provenance_is_relative_to_the_checkout(refresh_setup, monkeypatch):
    config, _, _ = refresh_setup
    monkeypatch.chdir(config.runs_root.parent)

    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    batch = (config.runs_root / report.run_id / "warnings.json").read_text()
    bundle = load_serving_bundle(Path("taiwan.json"), root=config.bundle_root)
    assert f'"baseline_latest:technical_range:runs/{report.run_id}/ohlcv.csv"' in batch
    assert str(config.runs_root.parent) not in batch
    assert bundle.source_input == f"runs/{report.run_id}/ohlcv.csv"


def _old_run(config, market, stamp):
    run = config.runs_root / f"daily_{market}_{stamp}_{'0' * 12}"
    run.mkdir(parents=True)
    (run / "download.csv").write_text("evidence")
    return run


def _saved_report(config, run_id):
    return daily.DailyRefreshReport.model_validate_json(
        (config.runs_root / run_id / "status.json").read_text()
    )


def test_refresh_keeps_only_the_newest_runs_of_its_market(refresh_setup):
    config, _, _ = refresh_setup
    config.keep_runs = 2
    older = _old_run(config, "taiwan", "20201230T120000")
    newer = _old_run(config, "taiwan", "20201231T120000")
    other_market = _old_run(config, "us", "20201201T120000")
    notes = config.runs_root / "taiwan_provider_diagnostic.csv"
    notes.write_text("kept")

    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    assert not older.exists()
    assert newer.exists() and other_market.exists() and notes.exists()
    assert report.pruned_runs == [older.name]
    assert _saved_report(config, report.run_id).pruned_runs == [older.name]


def test_failed_refresh_keeps_the_run_of_the_active_bundle(refresh_setup):
    config, result, _ = refresh_setup
    config.keep_runs = 1
    active = daily.refresh_daily(config, "postgresql://unused", now=NOW)
    abandoned = _old_run(config, "taiwan", "20210101T130000")
    result.ohlcv["date"] = "2010-01-01"

    with pytest.raises(ValueError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW.replace(day=2))

    remaining = sorted(path.name for path in config.runs_root.iterdir())
    assert len(remaining) == 2
    assert active.run_id in remaining
    failed = _saved_report(config, remaining[1])
    assert failed.status == "failed"
    assert failed.pruned_runs == [abandoned.name]


def test_retention_failure_does_not_fail_a_published_refresh(refresh_setup, monkeypatch):
    config, _, _ = refresh_setup
    config.keep_runs = 1
    older = _old_run(config, "taiwan", "20201230T120000")

    def deny(path):
        raise PermissionError("denied")

    monkeypatch.setattr(daily.shutil, "rmtree", deny)
    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    assert report.status == "published"
    assert report.retention_error_type == "PermissionError"
    assert report.pruned_runs == []
    assert older.exists()


def test_retention_never_removes_a_pending_publication(refresh_setup):
    config, _, _ = refresh_setup
    config.keep_runs = 1
    pending = _old_run(config, "taiwan", "20201230T120000")
    current = _old_run(config, "taiwan", "20201231T120000")
    config.bundle_root.mkdir(parents=True)
    daily._pending_path(config).write_text(
        daily.PendingPublication(run_id=pending.name).model_dump_json()
    )

    assert daily.stale_runs(config, current.name) == []


def test_retention_ignores_links_that_look_like_runs(refresh_setup, tmp_path):
    config, _, _ = refresh_setup
    config.keep_runs = 1
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not a run")
    config.runs_root.mkdir(parents=True)
    link = config.runs_root / f"daily_taiwan_20201230T120000_{'0' * 12}"
    link.symlink_to(outside, target_is_directory=True)

    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    assert report.pruned_runs == []
    assert link.is_symlink()
    assert (outside / "keep.txt").exists()


def test_recovery_compares_data_dates_like_a_fresh_publication(refresh_setup, monkeypatch):
    config, _, _ = refresh_setup
    daily.refresh_daily(config, "postgresql://unused", now=NOW)
    publish = daily.write_serving_bundle

    def disk_failure(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(daily, "write_serving_bundle", disk_failure)
    with pytest.raises(OSError):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)
    active_path = config.bundle_root / "taiwan.json"
    active = json.loads(active_path.read_text())
    active["data_as_of"] += "T00:00:00+00:00"
    active_path.write_text(json.dumps(active))
    monkeypatch.setattr(daily, "write_serving_bundle", publish)
    monkeypatch.setattr(daily, "read_prediction_batch_id", lambda *a: "persisted-batch")

    recovered = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    assert recovered.status == "published"


def _stored(monkeypatch, stored):
    monkeypatch.setattr(daily, "read_market_bars_from_postgres", lambda url, ticker, **kw:
                        stored[stored.ticker == ticker].copy())


def test_training_excludes_stored_bars_the_download_no_longer_has(refresh_setup, monkeypatch):
    config, result, _ = refresh_setup
    phantom = result.ohlcv[result.ohlcv.ticker == "2330"].iloc[[0]].assign(date="2020-06-13")
    _stored(monkeypatch, pd.concat([result.ohlcv, phantom], ignore_index=True))

    report = daily.refresh_daily(config, "postgresql://unused", now=NOW)

    snapshot = pd.read_csv(config.runs_root / report.run_id / "ohlcv.csv", dtype={"ticker": str})
    assert len(snapshot) == len(result.ohlcv)
    assert not snapshot.date.astype(str).str.startswith("2020-06-13").any()
    assert report.excluded_persisted_bars == 1


def test_reject_persisted_bars_that_lose_downloaded_rows(refresh_setup, monkeypatch):
    config, result, calls = refresh_setup
    _stored(monkeypatch, result.ohlcv.drop(index=result.ohlcv.index[5]))

    with pytest.raises(ValueError, match="Persisted"):
        daily.refresh_daily(config, "postgresql://unused", now=NOW)

    assert calls == ["bars"]
    assert not (config.bundle_root / "taiwan.json").exists()
