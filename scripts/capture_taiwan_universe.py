"""Capture the official current Taiwan company catalogues outside version control."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from tsi.data.taiwan_universe import capture_current_taiwan_universe, write_snapshot


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--members-output",
        type=Path,
        required=True,
        help="Local provider-derived CSV path; keep it outside version control.",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        required=True,
        help="JSON manifest path. It contains only hashes, counts, endpoints, and limitations.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    snapshot = capture_current_taiwan_universe()
    return write_snapshot(
        snapshot,
        members_output=args.members_output,
        manifest_output=args.manifest_output,
    )


def main() -> None:
    print(json.dumps(run(parse_args()), indent=2))


if __name__ == "__main__":
    main()
