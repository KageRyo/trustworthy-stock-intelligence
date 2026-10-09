# 0009: On-Demand Analysis Scores New Tickers with a Stored Pooled Model

- Status: Accepted
- Date: 2026-10-09
- Evidence: [Experiment 020](../../experiments/020_serving_replay/README.md)

## Context

On-demand analysis covers tickers that have no stored warning. It used to download the ticker and fit the serving model on that ticker's history alone. Experiment 020 replayed that scheme: single-ticker models had no ranking signal within a 63-date window (AUC about 0.50), and their Platt slope was non-positive about half the time. A model fitted on all tickers of a reference universe ranked a ticker's own history better, including tickers it never saw: 0.616 against 0.549 on 400 S&P 500 tickers and 0.694 against 0.656 on 194 TWSE holdout tickers.

## Decision

- A batch run with `--model-bundle-output` writes its fitted serving state as a `serving_model_bundle.v1` JSON file: logistic parameters, calibrator, alert and watch thresholds, calibration-drift result, and reliability references. Pydantic validates it, and loading it fits nothing and unpickles nothing.
- `make model-bundles` builds `us.json` and `taiwan.json` from multi-ticker reference universes. A single-ticker input cannot be stored.
- On-demand analysis picks the bundle by the ticker's resolved market (`us`, or `twse`, `tpex`, and `emerging` for Taiwan) from `TSI_MODEL_BUNDLE_DIR` and scores the ticker with it (`logistic_regression_pooled`). Only data quality comes from the ticker itself.
- Without a bundle for the market, on-demand analysis still fits the ticker alone, and every row carries `single_ticker_model`.
- A bundle whose data ends more than 30 days before the scored row adds `model_bundle_stale`.

## Consequences

- Scoring a universe ticker alone with the bundle reproduces its batch row within 1e-12, with identical warning levels and reason codes.
- On-demand latency drops because nothing is fitted; local runs took about 3.5 seconds, mostly the download.
- A bundle is as old as its batch run. Until bundles are rebuilt on a schedule, a stale bundle is flagged rather than refreshed.
- The Taiwan bundle is fitted on 53 large caps, so small TPEx and emerging stocks are scored outside its training range.

## Revisit when

- Bundles are rebuilt by a scheduled job after ingestion, which would let the staleness limit tighten.
- On-demand analysis moves to the `prediction_jobs` queue.
- A broader Taiwan reference universe is available for the Taiwan bundle.
