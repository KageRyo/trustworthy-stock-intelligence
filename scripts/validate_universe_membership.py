"""Validate and fingerprint a point-in-time universe membership CSV."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from tsi.data.universe import load_point_in_time_universe


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Membership CSV path.")
    parser.add_argument("--output", type=Path, required=True, help="Manifest JSON path.")
    parser.add_argument("--name", required=True, help="Research universe name.")
    parser.add_argument("--source", required=True, help="Source URL or archive identifier.")
    parser.add_argument(
        "--source-license",
        required=True,
        help="Usage/redistribution constraint recorded with the manifest.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, object]:
    universe = load_point_in_time_universe(
        args.input,
        name=args.name,
        source=args.source,
        source_license=args.source_license,
    )
    manifest = universe.manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    print(json.dumps(run(parse_args()), indent=2))


if __name__ == "__main__":
    main()
