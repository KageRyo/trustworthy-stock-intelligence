"""Audit a normalized OHLCV CSV and write a redacted quality report."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from tsi.data.quality import audit_market_bars


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Normalized OHLCV CSV to audit.")
    parser.add_argument("--output", type=Path, required=True, help="Redacted JSON report path.")
    parser.add_argument("--previous-input", type=Path, default=None, help="Prior CSV for revision checks.")
    parser.add_argument("--interval", choices=["1m", "5m", "1d"], default="5m")
    parser.add_argument("--provider", default="unknown", help="Provider label recorded in the report.")
    parser.add_argument(
        "--market",
        choices=["unknown", "us", "twse", "tpex", "emerging", "taiwan"],
        default="unknown",
        help="Session rule when the CSV has no market column.",
    )
    parser.add_argument(
        "--expected-tickers",
        nargs="*",
        default=[],
        help="Expected ticker identifiers; symbols remain strings, including leading zeros.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return a non-zero exit code for warning-only gaps or revisions.",
    )
    return parser.parse_args(argv)


def _read_frame(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"input CSV does not exist: {path}")
    return pd.read_csv(path, dtype={"ticker": "string"})


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    frame = _read_frame(args.input)
    market_by_ticker = {}
    if "market" in frame.columns:
        market_by_ticker = dict(
            zip(
                frame["ticker"].astype("string"),
                frame["market"].astype("string"),
                strict=False,
            )
        )
    else:
        market_by_ticker = {
            str(ticker).strip().upper(): args.market for ticker in frame["ticker"].dropna().unique()
        }

    previous_frame = _read_frame(args.previous_input) if args.previous_input is not None else None
    audit = audit_market_bars(
        frame,
        interval=args.interval,
        provider=args.provider,
        expected_tickers=args.expected_tickers,
        market_by_ticker=market_by_ticker,
        previous_frame=previous_frame,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(audit.model_dump_json(indent=2))
    if audit.status == "fail" or (args.fail_on_warning and audit.status == "warn"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
