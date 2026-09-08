from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
import pytest

from tsi.data.quality import MarketBarQualityError, audit_market_bars, enforce_market_bar_quality
from scripts.audit_market_bar_quality import main as audit_market_bar_quality_main


def _frame(*, timestamps: list[str], ticker: str = "2330", close: float = 102.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": timestamps,
            "ticker": [ticker] * len(timestamps),
            "open": [100.0] * len(timestamps),
            "high": [103.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [close] * len(timestamps),
            "adj_close": [close] * len(timestamps),
            "volume": [1000.0] * len(timestamps),
        }
    )


def test_five_minute_quality_audit_passes_taiwan_session_and_preserves_ticker_strings() -> None:
    audit = audit_market_bars(
        _frame(
            timestamps=[
                "2026-06-18T01:00:00Z",
                "2026-06-18T01:05:00Z",
                "2026-06-18T01:10:00Z",
            ]
        ),
        interval="5m",
        provider="yfinance",
        expected_tickers=["2330", "0050"],
        market_by_ticker={"2330": "twse"},
        generated_at=datetime(2026, 6, 18, tzinfo=UTC),
    )

    assert audit.status == "fail"
    assert audit.missing_tickers == ["0050"]
    summary = next(item for item in audit.ticker_summaries if item.ticker == "2330")
    assert summary.misaligned_rows == 0
    assert audit.generated_at == "2026-06-18T00:00:00+00:00"
    assert "date,ticker" not in audit.model_dump_json()


def test_quality_audit_detects_duplicate_gap_and_ohlcv_invariant() -> None:
    frame = _frame(
        timestamps=[
            "2026-06-18T01:00:00Z",
            "2026-06-18T01:00:00Z",
            "2026-06-18T01:10:00Z",
        ]
    )
    frame.loc[2, "low"] = 104.0

    audit = audit_market_bars(
        frame,
        interval="5m",
        provider="yfinance",
        market_by_ticker={"2330": "twse"},
    )

    assert audit.status == "fail"
    assert audit.fail_closed is True
    assert audit.issue_counts["duplicate_bar"] == 2
    assert audit.issue_counts["ohlcv_invariant"] == 1
    assert audit.issue_counts["bar_gap"] == 1
    assert audit.ticker_summaries[0].missing_bars == 1


def test_quality_audit_rejects_naive_intraday_timestamps_and_bad_values() -> None:
    frame = _frame(timestamps=["2026-06-18 01:00:00"])
    frame.loc[0, "volume"] = -1
    frame.loc[0, "open"] = float("inf")

    audit = audit_market_bars(
        frame,
        interval="5m",
        provider="yfinance",
        market_by_ticker={"2330": "twse"},
    )

    assert audit.status == "fail"
    assert audit.issue_counts["naive_timestamp"] == 1
    assert audit.issue_counts["non_finite_value"] == 1
    assert audit.issue_counts["negative_value"] == 1


def test_quality_audit_reports_provider_revisions_as_warning() -> None:
    current = _frame(timestamps=["2026-06-18T01:00:00Z"], close=102.0)
    previous = _frame(timestamps=["2026-06-18T01:00:00Z"], close=101.0)

    audit = audit_market_bars(
        current,
        interval="5m",
        provider="yfinance",
        market_by_ticker={"2330": "twse"},
        previous_frame=previous,
    )

    assert audit.status == "warn"
    assert audit.issue_counts["provider_revision"] == 1
    assert audit.ticker_summaries[0].revision_rows == 1


def test_enforce_market_bar_quality_raises_only_for_fail_closed_audits() -> None:
    warning = audit_market_bars(
        _frame(
            timestamps=[
                "2026-06-18T01:00:00Z",
                "2026-06-18T01:10:00Z",
            ]
        ),
        interval="5m",
        provider="yfinance",
        market_by_ticker={"2330": "twse"},
    )
    enforce_market_bar_quality(warning)

    failed = audit_market_bars(
        _frame(timestamps=["2026-06-18 01:00:00"]),
        interval="5m",
        provider="yfinance",
        market_by_ticker={"2330": "twse"},
    )
    with pytest.raises(MarketBarQualityError):
        enforce_market_bar_quality(failed)


def test_quality_cli_writes_redacted_report(tmp_path: Path) -> None:
    input_path = tmp_path / "bars.csv"
    output_path = tmp_path / "quality.json"
    _frame(
        timestamps=["2026-06-18T01:00:00Z", "2026-06-18T01:05:00Z"],
        ticker="0050",
    ).to_csv(input_path, index=False)

    audit_market_bar_quality_main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--interval",
            "5m",
            "--provider",
            "fixture",
            "--market",
            "twse",
            "--expected-tickers",
            "0050",
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["input_sha256"]
    assert "open" not in report
