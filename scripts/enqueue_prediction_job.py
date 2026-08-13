"""Enqueue one idempotent PostgreSQL-backed prediction job."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence

from tsi.data.prediction_jobs import PredictionJobRequest, enqueue_prediction_job
from tsi.observability import log_event


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--market", choices=["auto", "us", "twse", "tpex", "emerging"], default="auto")
    parser.add_argument("--feature-interval", choices=["1m", "5m", "1d"], default="1d")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--database-url",
        default=os.getenv("TSI_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to TSI_DATABASE_URL.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    database_url = str(args.database_url).strip()
    if not database_url:
        raise ValueError("--database-url or TSI_DATABASE_URL is required")
    request_values = {
        "ticker": args.ticker,
        "market": args.market,
        "feature_interval": args.feature_interval,
        "max_attempts": args.max_attempts,
    }
    if args.idempotency_key:
        request_values["idempotency_key"] = args.idempotency_key
    request = PredictionJobRequest(**request_values)
    job = enqueue_prediction_job(database_url, request)
    log_event(
        "prediction_job_enqueued",
        service="prediction_queue",
        ticker=job.ticker,
        market=job.market,
        feature_interval=job.feature_interval,
        status=job.status,
    )
    print(json.dumps(job.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
