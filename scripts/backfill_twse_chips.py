"""Backfill TWSE institutional-flow and margin-balance history into a local archive.

Trading dates come from an existing daily OHLCV file so holidays are never
requested. Raw payloads are cached per date under ``--archive-dir``; rerunning
the command resumes where it stopped. Normalized ``institutional.csv`` and
``margin.csv`` plus ``metadata.json`` are rebuilt from the archive at the end.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd

from scripts.walk_forward_experiment import resolve_output_dir
from tsi.data.csv import file_sha256
from tsi.data.twse_chips import (
    CHIP_KINDS,
    MI_MARGN_URL,
    T86_URL,
    backfill_chip_archive,
    load_chip_archive,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--calendar",
        type=Path,
        required=True,
        help="Daily OHLCV CSV whose dates define TWSE trading days.",
    )
    parser.add_argument("--start", default="2015-01-01", help="Inclusive start date.")
    parser.add_argument(
        "--end",
        default=None,
        help="Exclusive end date. Defaults to today, whose data may not be published yet.",
    )
    parser.add_argument("--archive-dir", type=Path, default=Path("data/raw/twse_chips"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.cwd(),
        help="Directory that --archive-dir must stay inside. Defaults to the working directory.",
    )
    parser.add_argument("--kinds", nargs="+", choices=list(CHIP_KINDS), default=list(CHIP_KINDS))
    parser.add_argument("--min-interval", type=float, default=2.5, help="Seconds between requests.")
    parser.add_argument("--build-only", action="store_true", help="Rebuild tables only.")
    return parser.parse_args(argv)


def trading_dates(calendar: Path, *, start: str, end: str | None) -> list[str]:
    """Return sorted ``YYYY-MM-DD`` dates in ``[start, end)`` from an OHLCV file.

    Dates on which every row has zero volume are skipped. Yahoo Finance writes
    such placeholder bars on Taiwan typhoon closures.
    """

    bars = pd.read_csv(calendar, usecols=["date", "volume"])
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    traded = bars.groupby("date")["volume"].max() > 0
    dates = pd.Series(traded.index[traded.to_numpy()])
    stop = pd.Timestamp(end) if end else pd.Timestamp(datetime.now(UTC).date())
    selected = dates[(dates >= pd.Timestamp(start)) & (dates < stop)]
    return sorted(selected.dt.strftime("%Y-%m-%d").unique())


def build_tables(archive_dir: Path, *, requested: list[str], failed: dict[str, str]) -> dict:
    """Write normalized CSV tables and metadata from the archive."""

    tables = load_chip_archive(archive_dir)
    institutional_path = archive_dir / "institutional.csv"
    margin_path = archive_dir / "margin.csv"
    tables.institutional.to_csv(institutional_path, index=False)
    tables.margin.to_csv(margin_path, index=False)
    metadata = {
        "dataset": "twse_chips",
        "source": {"institutional": T86_URL, "margin": MI_MARGN_URL},
        "built_at_utc": datetime.now(UTC).isoformat(),
        "requested_dates": len(requested),
        "requested_start": requested[0] if requested else None,
        "requested_end": requested[-1] if requested else None,
        "institutional_dates": len(tables.institutional_dates),
        "margin_dates": len(tables.margin_dates),
        "institutional_rows": int(len(tables.institutional)),
        "margin_rows": int(len(tables.margin)),
        "missing_institutional_dates": sorted(set(requested) - set(tables.institutional_dates)),
        "missing_margin_dates": sorted(set(requested) - set(tables.margin_dates)),
        "last_run_failures": failed,
        "units": {"institutional": "shares", "margin": "lots of 1,000 shares"},
        "institutional_sha256": file_sha256(institutional_path),
        "margin_sha256": file_sha256(margin_path),
        "research_note": (
            "TWSE public data for research use; review TWSE terms before redistribution. "
            "Institutional flows are published after the close of each trading date."
        ),
    }
    (archive_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> None:
    args = parse_args()
    archive_dir = resolve_output_dir(args.archive_dir, root=args.output_root)
    dates = trading_dates(args.calendar, start=args.start, end=args.end)
    failed: dict[str, str] = {}
    if not args.build_only:
        report = backfill_chip_archive(
            dates,
            archive_dir=archive_dir,
            kinds=args.kinds,
            min_interval_seconds=args.min_interval,
            log=lambda message: print(message, flush=True),
        )
        failed = report.failed
        print(
            f"fetched={report.fetched} cached={report.cached} failed={len(report.failed)} "
            f"no_data={report.no_data}"
        )
    metadata = build_tables(archive_dir, requested=dates, failed=failed)
    print(
        json.dumps(
            {
                key: metadata[key]
                for key in ("requested_dates", "institutional_dates", "margin_dates")
            }
        )
    )


if __name__ == "__main__":
    main()
