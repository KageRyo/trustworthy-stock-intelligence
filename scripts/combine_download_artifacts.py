"""Combine compatible explicit-ticker download artifacts for a research run."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from tsi.data.download import combine_download_artifacts, result_to_json


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        action="append",
        type=Path,
        required=True,
        help="One component directory produced by scripts.download_tickers; repeat for each market.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-name", required=True)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    result = combine_download_artifacts(
        args.input_dir,
        args.output_dir,
        dataset_name=args.dataset_name,
    )
    print(result_to_json(result))


if __name__ == "__main__":
    main()
