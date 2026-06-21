from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pytest

from scripts import analyze_ticker_on_demand as module
from tsi.data.download import DownloadFrameResult, DownloadTicker


def test_safe_path_part_keeps_taiwan_numeric_ticker() -> None:
    assert module.safe_path_part("2884") == "2884"


def test_run_on_demand_analysis_downloads_predicts_and_emits_schema(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_prediction_input = {}
    captured_market_writes = []

    def fake_download_ticker_frame(**kwargs):
        assert kwargs["tickers"] == ["2884"]
        assert kwargs["market"] == "auto"
        periods = 80 if kwargs["interval"] == "1d" else 20
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=periods, freq="D"),
                "ticker": ["2884"] * periods,
                "open": [10.0] * periods,
                "high": [11.0] * periods,
                "low": [9.0] * periods,
                "close": [10.5] * periods,
                "adj_close": [10.5] * periods,
                "volume": [1000] * periods,
            }
        )
        return DownloadFrameResult(
            dataset_name="on_demand_2884",
            tickers=[DownloadTicker(ticker="2884", query_symbol="2884.TW")],
            ohlcv=frame,
            start=kwargs["start"],
            end=kwargs["end"],
            interval=kwargs["interval"],
            failed_batches=[],
        )

    def fake_write_download_to_postgres(database_url, result, *, provider, universe_name):
        captured_market_writes.append(
            {
                "database_url": database_url,
                "interval": result.interval,
                "provider": provider,
                "universe_name": universe_name,
            }
        )

    def fake_run_prediction(args: argparse.Namespace) -> pd.DataFrame:
        captured_prediction_input["args"] = args
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text("date,ticker\n2026-03-21,2884\n", encoding="utf-8")
        Path(args.json_output).write_text("{}", encoding="utf-8")
        return pd.DataFrame({"date": ["2026-03-21"], "ticker": ["2884"]})

    monkeypatch.setattr(module, "download_ticker_frame", fake_download_ticker_frame)
    monkeypatch.setattr(module, "write_download_to_postgres", fake_write_download_to_postgres)
    monkeypatch.setattr(module, "run_prediction", fake_run_prediction)

    args = module.parse_args(
        [
            "--ticker",
            "2884",
            "--database-url",
            "postgresql://user:pass@localhost:5432/db",
            "--output-root",
            str(tmp_path / "artifacts"),
            "--raw-output-root",
            str(tmp_path / "raw"),
            "--run-id",
            "test_run",
        ]
    )
    summary = module.run_on_demand_analysis(args)

    assert summary.schema_version == "on_demand_analysis.v1"
    assert summary.ticker == "2884"
    assert summary.status == "success"
    assert summary.fresh_interval == "5m"
    assert summary.fresh_status == "success"
    assert summary.fresh_row_count == 20
    assert summary.row_count == 80
    assert summary.prediction_count == 1
    assert Path(summary.input_path).exists()
    assert captured_market_writes == [
        {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "interval": "5m",
            "provider": "yfinance",
            "universe_name": "on_demand",
        },
        {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "interval": "1d",
            "provider": "yfinance",
            "universe_name": "on_demand",
        },
    ]
    prediction_args = captured_prediction_input["args"]
    assert prediction_args.write_db is True
    assert prediction_args.database_url == "postgresql://user:pass@localhost:5432/db"
    assert prediction_args.run_id == "test_run"


def test_run_on_demand_analysis_writes_abstain_when_history_is_insufficient(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_batch = {}

    def fake_download_ticker_frame(**kwargs):
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2026-06-01", periods=12, freq="D"),
                "ticker": ["00981A"] * 12,
                "open": [30.0] * 12,
                "high": [31.0] * 12,
                "low": [29.0] * 12,
                "close": [30.5] * 12,
                "adj_close": [30.5] * 12,
                "volume": [1000] * 12,
            }
        )
        return DownloadFrameResult(
            dataset_name="on_demand_00981A",
            tickers=[DownloadTicker(ticker="00981A", query_symbol="00981A.TW")],
            ohlcv=frame,
            start=kwargs["start"],
            end=kwargs["end"],
            interval=kwargs["interval"],
            failed_batches=[],
        )

    def fake_run_prediction(_args: argparse.Namespace) -> pd.DataFrame:
        raise ValueError("Not enough labeled dates for the requested calibration_size")

    def fake_write_prediction_batch_to_postgres(database_url, batch, *, feature_interval):
        captured_batch["database_url"] = database_url
        captured_batch["batch"] = batch
        captured_batch["feature_interval"] = feature_interval

    monkeypatch.setattr(module, "download_ticker_frame", fake_download_ticker_frame)
    monkeypatch.setattr(module, "run_prediction", fake_run_prediction)
    monkeypatch.setattr(module, "write_download_to_postgres", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "write_prediction_batch_to_postgres",
        fake_write_prediction_batch_to_postgres,
    )

    args = module.parse_args(
        [
            "--ticker",
            "00981A",
            "--database-url",
            "postgresql://user:pass@localhost:5432/db",
            "--output-root",
            str(tmp_path / "artifacts"),
            "--raw-output-root",
            str(tmp_path / "raw"),
            "--fresh-interval",
            "none",
            "--run-id",
            "test_short_history",
        ]
    )
    summary = module.run_on_demand_analysis(args)

    assert summary.ticker == "00981A"
    assert summary.prediction_count == 1
    batch = captured_batch["batch"]
    assert batch.run_id == "test_short_history"
    assert batch.records[0].warning_level == "abstain"
    assert "insufficient_history" in batch.records[0].reason_codes
    assert Path(summary.warnings_path).exists()


def test_run_on_demand_analysis_rethrows_non_history_prediction_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_download_ticker_frame(**kwargs):
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=80, freq="D"),
                "ticker": ["2330"] * 80,
                "open": [10.0] * 80,
                "high": [11.0] * 80,
                "low": [9.0] * 80,
                "close": [10.5] * 80,
                "adj_close": [10.5] * 80,
                "volume": [1000] * 80,
            }
        )
        return DownloadFrameResult(
            dataset_name="on_demand_2330",
            tickers=[DownloadTicker(ticker="2330", query_symbol="2330.TW")],
            ohlcv=frame,
            start=kwargs["start"],
            end=kwargs["end"],
            interval=kwargs["interval"],
            failed_batches=[],
        )

    def fake_run_prediction(_args: argparse.Namespace) -> pd.DataFrame:
        raise ValueError("unexpected model failure")

    monkeypatch.setattr(module, "download_ticker_frame", fake_download_ticker_frame)
    monkeypatch.setattr(module, "run_prediction", fake_run_prediction)
    monkeypatch.setattr(module, "write_download_to_postgres", lambda *_args, **_kwargs: None)

    args = module.parse_args(
        [
            "--ticker",
            "2330",
            "--database-url",
            "postgresql://user:pass@localhost:5432/db",
            "--output-root",
            str(tmp_path / "artifacts"),
            "--raw-output-root",
            str(tmp_path / "raw"),
            "--fresh-interval",
            "none",
        ]
    )

    with pytest.raises(ValueError, match="unexpected model failure"):
        module.run_on_demand_analysis(args)
