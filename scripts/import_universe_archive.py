"""Import an external membership archive into a redacted v2 manifest."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, date, datetime
import json
from pathlib import Path

import pandas as pd

from tsi.data.universe_import import (
    MembershipColumnMapping,
    MembershipImportConfig,
    audit_membership_coverage,
    import_membership_archive,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Local licensed archive CSV.")
    parser.add_argument("--output", type=Path, required=True, help="Redacted manifest JSON.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-license", required=True)
    parser.add_argument("--retrieved-at", type=_parse_datetime, required=True)
    parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True)
    parser.add_argument("--mapping-version", required=True)
    parser.add_argument("--security-id-column", required=True)
    parser.add_argument("--ticker-column", required=True)
    parser.add_argument("--valid-from-column", required=True)
    parser.add_argument("--known-at-column", required=True)
    parser.add_argument("--valid-to-column", default=None)
    parser.add_argument("--provider-symbol-column", default=None)
    parser.add_argument("--market-column", default=None)
    parser.add_argument("--exchange-column", default=None)
    parser.add_argument("--change-reason-column", default=None)
    parser.add_argument(
        "--ohlcv", type=Path, default=None, help="Optional OHLCV CSV for coverage audit."
    )
    parser.add_argument("--coverage-output", type=Path, default=None)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    if (args.ohlcv is None) != (args.coverage_output is None):
        raise ValueError("--ohlcv and --coverage-output must be supplied together")
    config = MembershipImportConfig(
        name=args.name,
        source=args.source,
        source_license=args.source_license,
        retrieved_at=args.retrieved_at,
        snapshot_date=args.snapshot_date,
        mapping=MembershipColumnMapping(
            mapping_version=args.mapping_version,
            security_id=args.security_id_column,
            ticker=args.ticker_column,
            valid_from=args.valid_from_column,
            known_at=args.known_at_column,
            valid_to=args.valid_to_column,
            provider_symbol=args.provider_symbol_column,
            market=args.market_column,
            exchange=args.exchange_column,
            change_reason=args.change_reason_column,
        ),
    )
    imported = import_membership_archive(args.input, config)
    manifest = {"import_report": imported.report.model_dump(mode="json")}
    if args.ohlcv is not None:
        audit = audit_membership_coverage(
            imported.universe,
            pd.read_csv(args.ohlcv, dtype={"ticker": "string"}),
        )
        args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
        args.coverage_output.write_text(
            json.dumps(audit.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest["coverage_audit"] = audit.model_dump(mode="json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main() -> None:
    print(json.dumps(run(parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
