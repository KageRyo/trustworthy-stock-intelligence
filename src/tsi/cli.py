"""Small, deterministic command-line entry point for the Python package."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tsi import __version__
from tsi.data.csv import read_ohlcv_csv
from tsi.evaluation.metrics import classification_metrics


class CsvSummary(BaseModel):
    """Schema-first summary emitted by ``tsi inspect-csv``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["dataset_summary.v1"] = "dataset_summary.v1"
    path: str
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    columns: list[str]
    ticker_count: int | None = Field(default=None, ge=0)
    tickers: list[str] = Field(default_factory=list)
    date_start: str | None = None
    date_end: str | None = None


class EvaluationSummary(BaseModel):
    """Schema-first summary emitted by ``tsi evaluate``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation_summary.v1"] = "evaluation_summary.v1"
    path: str
    label_column: str
    probability_column: str
    threshold: float = Field(ge=0.0, le=1.0)
    metrics: dict[str, float | None]


def build_parser() -> argparse.ArgumentParser:
    """Build the package CLI parser."""

    parser = argparse.ArgumentParser(
        prog="tsi",
        description="Inspect local stock-risk artifacts and evaluate warning probabilities.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    version_parser = commands.add_parser("version", help="Print the installed package version.")
    version_parser.set_defaults(handler=_run_version)

    inspect_parser = commands.add_parser(
        "inspect-csv",
        help="Summarize an OHLCV or prediction CSV without downloading provider data.",
    )
    inspect_parser.add_argument("path", type=Path)
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    inspect_parser.set_defaults(handler=_run_inspect_csv)

    evaluate_parser = commands.add_parser(
        "evaluate",
        help="Evaluate binary labels and predicted probabilities from a CSV.",
    )
    evaluate_parser.add_argument("path", type=Path)
    evaluate_parser.add_argument("--label-column", default="risk_label")
    evaluate_parser.add_argument(
        "--probability-column",
        default="calibrated_risk_probability",
    )
    evaluate_parser.add_argument("--threshold", type=float, default=0.5)
    evaluate_parser.add_argument("--json", action="store_true", dest="as_json")
    evaluate_parser.set_defaults(handler=_run_evaluate)
    return parser


def build_csv_summary(path: Path | str) -> CsvSummary:
    """Load and summarize a CSV while preserving ticker symbols as strings."""

    csv_path = Path(path)
    frame = read_ohlcv_csv(csv_path)
    tickers: list[str] = []
    if "ticker" in frame.columns:
        tickers = sorted(
            {
                str(value).strip()
                for value in frame["ticker"].dropna().tolist()
                if str(value).strip() and str(value).strip() != "<NA>"
            }
        )

    date_start: str | None = None
    date_end: str | None = None
    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
        if not dates.empty:
            date_start = dates.min().isoformat()
            date_end = dates.max().isoformat()

    return CsvSummary(
        path=str(csv_path),
        row_count=len(frame),
        column_count=len(frame.columns),
        columns=[str(column) for column in frame.columns],
        ticker_count=len(tickers) if "ticker" in frame.columns else None,
        tickers=tickers,
        date_start=date_start,
        date_end=date_end,
    )


def build_evaluation_summary(
    path: Path | str,
    *,
    label_column: str = "risk_label",
    probability_column: str = "calibrated_risk_probability",
    threshold: float = 0.5,
) -> EvaluationSummary:
    """Evaluate labels and probabilities from a local CSV artifact."""

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    csv_path = Path(path)
    frame = read_ohlcv_csv(csv_path)
    missing = [column for column in (label_column, probability_column) if column not in frame]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    labels = pd.to_numeric(frame[label_column], errors="raise").to_numpy(dtype=float)
    probabilities = pd.to_numeric(frame[probability_column], errors="raise").to_numpy(dtype=float)
    if not np.all(np.isfinite(labels)) or not np.all(np.isin(labels, [0.0, 1.0])):
        raise ValueError(f"{label_column} must contain only finite binary values")
    if not np.all(np.isfinite(probabilities)) or np.any((probabilities < 0.0) | (probabilities > 1.0)):
        raise ValueError(f"{probability_column} must contain finite probabilities in [0, 1]")

    raw_metrics = classification_metrics(
        labels.astype(int),
        probabilities,
        threshold=threshold,
    )
    metrics = {
        name: (None if not np.isfinite(value) else float(value))
        for name, value in raw_metrics.items()
    }
    return EvaluationSummary(
        path=str(csv_path),
        label_column=label_column,
        probability_column=probability_column,
        threshold=threshold,
        metrics=metrics,
    )


def _run_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _run_inspect_csv(args: argparse.Namespace) -> int:
    summary = build_csv_summary(args.path)
    _print_summary(summary, as_json=args.as_json)
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    summary = build_evaluation_summary(
        args.path,
        label_column=args.label_column,
        probability_column=args.probability_column,
        threshold=args.threshold,
    )
    _print_summary(summary, as_json=args.as_json)
    return 0


def _print_summary(summary: CsvSummary | EvaluationSummary, *, as_json: bool) -> None:
    if as_json:
        print(summary.model_dump_json(indent=2))
        return
    if isinstance(summary, CsvSummary):
        print(f"rows: {summary.row_count}")
        print(f"columns: {summary.column_count}")
        print(f"tickers: {summary.ticker_count if summary.ticker_count is not None else 'n/a'}")
        print(f"date range: {summary.date_start or 'n/a'} -> {summary.date_end or 'n/a'}")
        return
    print(f"evaluated: {summary.path}")
    for name, value in summary.metrics.items():
        rendered = "n/a" if value is None else f"{value:.6f}"
        print(f"{name}: {rendered}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``tsi`` command and return a process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
