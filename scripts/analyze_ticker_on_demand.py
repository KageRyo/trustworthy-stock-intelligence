"""Download one ticker, run latest baseline analysis, and write it to PostgreSQL."""

from __future__ import annotations

import argparse
import os
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from scripts.predict_latest_baseline import parse_args as parse_prediction_args
from scripts.predict_latest_baseline import run_prediction
from tsi.data.download import download_ticker_frame
from tsi.data.postgres import write_download_to_postgres, write_prediction_batch_to_postgres
from tsi.serving.schema import build_prediction_batch, write_prediction_batch_json

SCHEMA_VERSION = "on_demand_analysis.v1"


class OnDemandAnalysisSummary(BaseModel):
    """Schema-first summary emitted by the on-demand analysis command."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["on_demand_analysis.v1"] = SCHEMA_VERSION
    status: Literal["success"] = "success"
    ticker: str
    run_id: str
    market: Literal["auto", "us", "twse", "tpex", "emerging"]
    interval: Literal["1d"]
    fresh_interval: Literal["5m"] | None = None
    fresh_status: Literal["success", "failed", "skipped"] = "skipped"
    fresh_row_count: int = Field(ge=0, default=0)
    fresh_error: str | None = None
    row_count: int = Field(ge=1)
    prediction_count: int = Field(ge=1)
    input_path: str
    predictions_path: str
    warnings_path: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True, help="Ticker symbol or Taiwan numeric stock code.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", ""),
        help="PostgreSQL URL. Defaults to TSI_DATABASE_URL.",
    )
    parser.add_argument(
        "--market",
        choices=["auto", "us", "twse", "tpex", "emerging"],
        default="auto",
        help="Provider ticker resolver. auto maps numeric tickers to TWSE symbols.",
    )
    parser.add_argument(
        "--interval",
        choices=["1d"],
        default="1d",
        help="Feature interval used by the current trusted baseline.",
    )
    parser.add_argument(
        "--fresh-interval",
        choices=["none", "5m"],
        default="5m",
        help="Optional fresh market-bar interval to store before daily risk prediction.",
    )
    parser.add_argument(
        "--fresh-start",
        default=None,
        help="Inclusive provider start date for fresh bars. Defaults to 7 days ago.",
    )
    parser.add_argument(
        "--start",
        default="2015-01-01",
        help="Inclusive provider start date for historical training data.",
    )
    parser.add_argument("--end", default=None, help="Exclusive provider end date.")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output-root", type=Path, default=Path("data/artifacts/on_demand"))
    parser.add_argument("--raw-output-root", type=Path, default=Path("data/raw/on_demand"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--train-size", type=int, default=None)
    parser.add_argument(
        "--calibration-method",
        choices=["none", "platt", "isotonic"],
        default="platt",
    )
    return parser.parse_args(argv)


def run_on_demand_analysis(args: argparse.Namespace) -> OnDemandAnalysisSummary:
    database_url = str(args.database_url).strip()
    if not database_url:
        raise ValueError("--database-url or TSI_DATABASE_URL is required")

    ticker = normalize_ticker(args.ticker)
    safe_ticker = safe_path_part(ticker)
    run_id = args.run_id or build_run_id(ticker)
    raw_dir = Path(args.raw_output_root) / safe_ticker
    artifact_dir = Path(args.output_root) / safe_ticker
    input_path = raw_dir / "ohlcv.csv"
    predictions_path = artifact_dir / "latest_predictions.csv"
    warnings_path = artifact_dir / "latest_warnings.json"
    fresh_status: Literal["success", "failed", "skipped"] = "skipped"
    fresh_row_count = 0
    fresh_error = None

    if args.fresh_interval != "none":
        try:
            fresh_result = download_ticker_frame(
                tickers=[ticker],
                start=args.fresh_start or default_fresh_start(),
                end=args.end,
                market=args.market,
                interval=args.fresh_interval,
                batch_size=args.batch_size,
                dataset_name=f"on_demand_{safe_ticker}_fresh",
            )
            write_download_to_postgres(
                database_url,
                fresh_result,
                provider="yfinance",
                universe_name="on_demand",
            )
            fresh_status = "success"
            fresh_row_count = len(fresh_result.ohlcv)
        except Exception as exc:  # noqa: BLE001
            fresh_status = "failed"
            fresh_error = str(exc)

    result = download_ticker_frame(
        tickers=[ticker],
        start=args.start,
        end=args.end,
        market=args.market,
        interval=args.interval,
        batch_size=args.batch_size,
        dataset_name=f"on_demand_{safe_ticker}",
    )
    if result.ohlcv.empty:
        raise ValueError(f"No OHLCV rows downloaded for ticker {ticker}")
    write_download_to_postgres(
        database_url,
        result,
        provider="yfinance",
        universe_name="on_demand",
    )

    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result.ohlcv.to_csv(input_path, index=False)

    prediction_args = [
        "--input",
        str(input_path),
        "--output",
        str(predictions_path),
        "--json-output",
        str(warnings_path),
        "--calibration-size",
        str(args.calibration_size),
        "--calibration-method",
        args.calibration_method,
        "--run-id",
        run_id,
        "--write-db",
        "--database-url",
        database_url,
        "--feature-interval",
        args.interval,
    ]
    if args.train_size is not None:
        prediction_args.extend(["--train-size", str(args.train_size)])

    try:
        predictions = run_prediction(parse_prediction_args(prediction_args))
    except ValueError as exc:
        if not is_insufficient_history_error(exc):
            raise
        predictions = write_insufficient_history_prediction(
            result.ohlcv,
            ticker=ticker,
            run_id=run_id,
            input_path=input_path,
            predictions_path=predictions_path,
            warnings_path=warnings_path,
            database_url=database_url,
            feature_interval=args.interval,
        )
    if predictions.empty:
        raise ValueError(f"No predictions generated for ticker {ticker}")

    return OnDemandAnalysisSummary(
        ticker=ticker,
        run_id=run_id,
        market=args.market,
        interval=args.interval,
        fresh_interval=None if args.fresh_interval == "none" else args.fresh_interval,
        fresh_status=fresh_status,
        fresh_row_count=fresh_row_count,
        fresh_error=fresh_error,
        row_count=len(result.ohlcv),
        prediction_count=len(predictions),
        input_path=str(input_path),
        predictions_path=str(predictions_path),
        warnings_path=str(warnings_path),
    )


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not ticker:
        raise ValueError("ticker must not be empty")
    return ticker


def safe_path_part(value: str) -> str:
    safe = re.sub(r"[^A-Z0-9_.-]+", "_", value.upper()).strip("._-")
    if not safe:
        raise ValueError("ticker cannot be converted to a safe path")
    return safe


def build_run_id(ticker: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"on_demand_{safe_path_part(ticker).lower()}_{timestamp}"


def default_fresh_start() -> str:
    return (datetime.now(UTC).date() - timedelta(days=7)).isoformat()


def is_insufficient_history_error(error: ValueError) -> bool:
    message = str(error)
    return any(
        marker in message
        for marker in (
            "Not enough labeled dates",
            "No latest feature rows were created",
            "train and calibration frames must not be empty",
        )
    )


def write_insufficient_history_prediction(
    ohlcv: pd.DataFrame,
    *,
    ticker: str,
    run_id: str,
    input_path: Path,
    predictions_path: Path,
    warnings_path: Path,
    database_url: str,
    feature_interval: str,
) -> pd.DataFrame:
    frame = ohlcv.copy()
    data_as_of = str(frame["date"].max())
    predictions = frame.iloc[[-1]][["date", "ticker"]].assign(
        model="insufficient_history_abstain",
        risk_probability=0.5,
        calibrated_risk_probability=0.5,
        calibration_method="none",
        uncertainty_score=1.0,
        trust_score=0.0,
        alert_threshold=1.0,
        watch_threshold=1.0,
        warning_level="abstain",
        model_bundle=f"insufficient_history:{input_path}",
        reason_codes=[
            [
                "insufficient_history",
                "trust_below_alert_threshold",
                "uncertainty_above_threshold",
                "warning_level_abstain",
            ]
        ],
    )
    predictions["ticker"] = ticker
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.drop(columns=["reason_codes"]).to_csv(predictions_path, index=False)
    batch = build_prediction_batch(predictions, run_id=run_id, data_as_of=data_as_of)
    write_prediction_batch_json(batch, warnings_path)
    write_prediction_batch_to_postgres(
        database_url,
        batch,
        feature_interval=feature_interval,
    )
    return predictions.drop(columns=["reason_codes"])


def main() -> None:
    summary = run_on_demand_analysis(parse_args())
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
