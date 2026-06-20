from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from scripts import analyze_ticker_on_demand as module
from tsi.data.download import DownloadFrameResult, DownloadTicker


def test_safe_path_part_keeps_taiwan_numeric_ticker() -> None:
    assert module.safe_path_part("2884") == "2884"


def test_run_on_demand_analysis_downloads_predicts_and_emits_schema(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_prediction_input = {}
    captured_market_write = {}

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
        captured_market_write["database_url"] = database_url
        captured_market_write["interval"] = result.interval
        captured_market_write["provider"] = provider
        captured_market_write["universe_name"] = universe_name

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
    assert captured_market_write == {
        "database_url": "postgresql://user:pass@localhost:5432/db",
        "interval": "5m",
        "provider": "yfinance",
        "universe_name": "on_demand",
    }
    prediction_args = captured_prediction_input["args"]
    assert prediction_args.write_db is True
    assert prediction_args.database_url == "postgresql://user:pass@localhost:5432/db"
    assert prediction_args.run_id == "test_run"
