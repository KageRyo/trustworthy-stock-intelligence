"""Run the PostgreSQL-backed prediction job worker."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence

from tsi.data.prediction_jobs import (
    build_market_bar_prediction_processor,
    default_worker_id,
    run_prediction_worker,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to TSI_DATABASE_URL.",
    )
    parser.add_argument("--worker-id", default=None, help="Worker lease identifier.")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0)
    parser.add_argument("--max-jobs", type=int, default=None)
    parser.add_argument("--output-root", default="data/artifacts/prediction_jobs")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim at most one available job and exit when the queue is idle.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    database_url = str(args.database_url).strip()
    if not database_url:
        raise ValueError("--database-url or TSI_DATABASE_URL is required")
    worker_id = args.worker_id or default_worker_id()
    summary = run_prediction_worker(
        database_url,
        worker_id,
        build_market_bar_prediction_processor(database_url, output_root=args.output_root),
        poll_seconds=args.poll_seconds,
        lease_seconds=args.lease_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
        once=args.once,
        max_jobs=args.max_jobs,
    )
    print(json.dumps(summary.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
