"""Refresh one market's pooled daily model and PostgreSQL warnings."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from tsi.data.daily_refresh import DailyRefreshConfig, refresh_daily


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True, choices=["us", "taiwan"])
    parser.add_argument("--seed-input", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path("data/artifacts/daily_refresh"))
    parser.add_argument("--bundle-root", type=Path, default=Path(
        os.getenv("TSI_MODEL_BUNDLE_DIR", "data/artifacts/model_bundles")))
    args = parser.parse_args()
    env_name = "TSI_US_BUNDLE_INPUT" if args.market == "us" else "TSI_TAIWAN_BUNDLE_INPUT"
    default_seed = "data/raw/sp100/ohlcv.csv" if args.market == "us" else "data/raw/tw_large/ohlcv.csv"
    config = DailyRefreshConfig(
        market=args.market, seed_input=args.seed_input or Path(os.getenv(env_name, default_seed)),
        bundle_root=args.bundle_root, runs_root=args.runs_root,
    )
    try:
        report = refresh_daily(config, os.getenv("TSI_DATABASE_URL", ""))
    except Exception as exc:
        # Third-party exceptions may contain DSNs. Durable reports carry the stage and type.
        parser.exit(65 if isinstance(exc, ValueError) else 1, f"Daily refresh failed: {type(exc).__name__}; inspect run status.json\n")
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
