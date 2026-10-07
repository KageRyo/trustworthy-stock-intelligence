"""Tests for market reference series download and loading."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tsi.data.download import DownloadFrameResult, DownloadTicker
from tsi.data.market_reference import (
    TAIWAN_MARKET_SYMBOL,
    US_MARKET_SYMBOL,
    US_VOLATILITY_SYMBOL,
    download_market_reference,
    fetch_ticker_sectors,
    load_market_reference,
    sector_etf_for,
)


def _info_fetcher(payloads: dict[str, dict[str, object]]):
    def fetch(symbol: str) -> dict[str, object]:
        if symbol not in payloads:
            raise RuntimeError(f"no info for {symbol}")
        return payloads[symbol]

    return fetch


def _frame_downloader(calls: list[list[str]]):
    def download(tickers: list[str], start: str, end: str | None, **_kwargs: object):
        calls.append(list(tickers))
        rows = [
            {
                "date": date,
                "ticker": ticker,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.0,
                "adj_close": 10.0,
                "volume": 0.0 if ticker.startswith("^") else 100.0,
            }
            for ticker in tickers
            for date in ("2024-01-02", "2024-01-03")
        ]
        return DownloadFrameResult(
            dataset_name="market_reference",
            tickers=[DownloadTicker(ticker=t, query_symbol=t, market="us") for t in tickers],
            ohlcv=pd.DataFrame(rows),
            start=start,
            end=end,
            interval="1d",
            failed_batches=[],
        )

    return download


def test_sector_etf_uses_stable_yahoo_sector_keys() -> None:
    assert sector_etf_for("technology") == "XLK"
    assert sector_etf_for("communication-services") == "XLC"
    assert sector_etf_for("basic-materials") == "XLB"
    assert sector_etf_for("unknown-sector") is None
    assert sector_etf_for(None) is None


def test_fetch_ticker_sectors_validates_payloads_and_keeps_failures() -> None:
    records = fetch_ticker_sectors(
        ["AAPL", "BRK-B", "MISSING", "NOSECTOR"],
        info_fetcher=_info_fetcher(
            {
                "AAPL": {"sector": "Technology", "sectorKey": "technology", "extra": 1},
                "BRK-B": {"sector": "Financial Services", "sectorKey": "financial-services"},
                "NOSECTOR": {"longName": "Index Fund"},
            }
        ),
    )

    by_ticker = {record.ticker: record for record in records}
    assert by_ticker["AAPL"].sector_etf == "XLK"
    assert by_ticker["BRK-B"].sector_etf == "XLF"
    assert by_ticker["MISSING"].sector_etf is None
    assert by_ticker["MISSING"].error == "no info for MISSING"
    assert by_ticker["NOSECTOR"].sector_key is None
    assert by_ticker["NOSECTOR"].error == ""


def test_fetch_ticker_sectors_rejects_taiwan_codes() -> None:
    fetcher = _info_fetcher({})

    with pytest.raises(ValueError, match="US tickers"):
        fetch_ticker_sectors(["2330"], info_fetcher=fetcher)


def test_download_market_reference_writes_artifacts(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    result = download_market_reference(
        ["AAPL", "MSFT", "JPM", "ODD"],
        output_dir=tmp_path,
        start="2024-01-01",
        info_fetcher=_info_fetcher(
            {
                "AAPL": {"sectorKey": "technology"},
                "MSFT": {"sectorKey": "technology"},
                "JPM": {"sectorKey": "financial-services"},
                "ODD": {"sectorKey": "conglomerates"},
            }
        ),
        frame_downloader=_frame_downloader(calls),
    )

    assert calls == [[US_MARKET_SYMBOL, US_VOLATILITY_SYMBOL, "XLF", "XLK"]]
    assert result.symbols == [US_MARKET_SYMBOL, US_VOLATILITY_SYMBOL, "XLF", "XLK"]
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["market_symbol"] == "SPY"
    assert metadata["volatility_symbol"] == "^VIX"
    assert metadata["unmapped_tickers"] == ["ODD"]
    assert len(metadata["ohlcv_sha256"]) == 64
    assert len(metadata["sector_map_sha256"]) == 64

    reference = load_market_reference(tmp_path)
    assert reference.market_symbol == "SPY"
    assert reference.volatility_symbol == "^VIX"
    assert reference.sector_etf_by_ticker == {"AAPL": "XLK", "MSFT": "XLK", "JPM": "XLF"}
    assert set(reference.ohlcv["ticker"]) == {"SPY", "^VIX", "XLF", "XLK"}


def test_taiwan_reference_uses_taiex_without_sector_lookup(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    download_market_reference(
        ["2330", "00981A", "5240"],
        output_dir=tmp_path,
        start="2024-01-01",
        market="taiwan",
        info_fetcher=_info_fetcher({}),
        frame_downloader=_frame_downloader(calls),
    )

    assert calls == [[TAIWAN_MARKET_SYMBOL]]
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["market"] == "taiwan"
    assert metadata["unmapped_tickers"] == ["2330", "00981A", "5240"]
    reference = load_market_reference(tmp_path)
    assert reference.market_symbol == "^TWII"
    assert reference.volatility_symbol is None
    assert reference.sector_etf_by_ticker == {}


def test_load_market_reference_keeps_ticker_strings(tmp_path: Path) -> None:
    pd.DataFrame(
        {"date": ["2024-01-02"], "ticker": ["0050"], "adj_close": [1.0], "close": [1.0]}
    ).to_csv(tmp_path / "ohlcv.csv", index=False)
    pd.DataFrame(
        {"ticker": ["00981A"], "sector": [""], "sector_key": [""], "sector_etf": ["0050"]}
    ).to_csv(tmp_path / "sector_map.csv", index=False)
    (tmp_path / "metadata.json").write_text(
        json.dumps({"market_symbol": "0050", "volatility_symbol": None})
    )

    reference = load_market_reference(tmp_path)

    assert reference.ohlcv["ticker"].tolist() == ["0050"]
    assert reference.sector_etf_by_ticker == {"00981A": "0050"}
    assert reference.volatility_symbol is None


def test_cli_reads_tickers_file_as_strings(tmp_path: Path) -> None:
    from scripts.download_market_reference import parse_args, resolve_tickers

    tickers_file = tmp_path / "tickers.csv"
    tickers_file.write_text("ticker\nAAPL\n BRK-B \n")

    args = parse_args(["--tickers-file", str(tickers_file), "--output-dir", str(tmp_path)])

    assert resolve_tickers(args) == ["AAPL", "BRK-B"]
    assert args.start == "2015-01-01"


def test_cli_rejects_output_dir_outside_root(tmp_path: Path) -> None:
    from scripts.download_market_reference import parse_args
    from scripts.walk_forward_experiment import resolve_output_dir

    args = parse_args(
        ["--tickers", "AAPL", "--output-dir", "../escape", "--output-root", str(tmp_path)]
    )

    assert args.output_root == tmp_path
    with pytest.raises(ValueError, match="must stay inside"):
        resolve_output_dir(args.output_dir, root=args.output_root)
