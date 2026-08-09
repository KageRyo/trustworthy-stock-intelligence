# Research Readiness and Data Boundaries

This document sets the evidence boundary for open research Issues #21, #23,
and #29. It prevents an incomplete pilot, a current constituent list, or a
different vendor snapshot from being presented as a like-for-like benchmark.
It is project guidance, not legal advice.

## Issue #21: Deep Model Benchmark

An Issue #21 quality comparison requires all of the following:

- an identical OHLCV input file, proven by `input_sha256` in both summaries;
- identical point-in-time membership manifests (or an identical explicit
  `not_supplied` state);
- the `252 / 5 / 63 / 5 / 63` purged schedule and the same label/feature
  protocol;
- contiguous fold IDs `0` through `38`, all 39 fold outputs, and identical
  `fold_id, ticker, date, risk_label` keys;
- raw, calibrated, and threshold-tuned metrics recomputed from the private
  prediction artifacts; and
- GPU execution for the deep model. A CPU fallback is only appropriate for
  tests or local debugging, not the reported deep-model result.

`scripts.train` and `scripts.train_deep` now emit both the input fingerprint
and the membership manifest. `scripts.audit_deep_alignment` rejects mismatched
snapshots, membership, rows, noncontiguous folds, missing probabilities, and
mixed threshold values within a fold. Its JSON output records aggregate and
per-fold ROC-AUC, PR-AUC, Brier, ECE, precision, recall, F1, false-positive
rate, false-discovery rate, and alert coverage.

The prior one-fold deep GPU smoke result remains an alignment check only. It is
not a quality result, and it cannot be upgraded without a fresh 39-fold run.

## Issue #23: Taiwan Universe Capture

Use the typed capture command to establish a dated current catalogue before
requesting historical OHLCV. Keep the CSV and any provider responses in a
private, untracked location; only the JSON manifest is suitable for a review
record after its contents and rights have been checked.

```bash
PYTHONPATH=src python -m scripts.capture_taiwan_universe \
  --members-output /secure/tsi/taiwan-current-members.csv \
  --manifest-output /secure/tsi/taiwan-current-manifest.json
```

It uses the official [TWSE OpenAPI](https://openapi.twse.com.tw/) listed-company
endpoint plus the [TPEx OpenAPI](https://www.tpex.org.tw/openapi/) mainboard
and emerging-company endpoints. The member catalogue preserves a separate
`market` and market-qualified provider symbol (`.TW`, `.TWO`, or `.EMERGING`),
so a code is never silently reclassified between listed, TPEx, and emerging
markets.

This is intentionally a *current* catalogue. It cannot establish historical
membership, delistings, suspensions, or whether a security was knowable on an
earlier date. A formal Taiwan evaluation must pair a dated membership/history
source with OHLCV rights adequate for the intended use. Before downloading or
redistributing provider data, recheck the project's
[data and model licence boundary](data_and_model_licenses.md), including the
[TWSE terms](https://www.twse.com.tw/en/terms/use.html) and
[TPEx terms](https://www.tpex.org.tw/en-us/gtsm_disclaimer.html).

## Issue #29: Point-in-Time S&P Membership

The current S&P 100 list cannot solve survivorship bias, even if its rows have
listing dates. The required source must provide historical effective dates,
additions/removals, security-identifier changes, and its usage constraints. An
S&P data licence or a user-supplied research-vendor archive is therefore a
prerequisite; use the current index webpage only for an operational current
catalogue, never historical membership.

After receiving a legally usable archive, validate it without committing its
raw rows:

```bash
PYTHONPATH=src python -m scripts.validate_universe_membership \
  --input /secure/tsi/sp100-membership.csv \
  --output /secure/tsi/sp100-membership-manifest.json \
  --name sp100_point_in_time \
  --source "licensed constituent archive" \
  --source-license "research-only; redistribution prohibited"
```

Run baseline and deep training with the same `--universe-membership`, metadata,
and OHLCV input. Then compare the point-in-time run with the documented
current-universe pilot. Until that comparison exists, all historical S&P 100
metrics retain a survivorship-bias limitation.
