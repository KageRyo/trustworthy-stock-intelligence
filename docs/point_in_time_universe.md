# Point-in-Time Universe Membership

Historical experiments must not use the current constituent list as if every symbol belonged to the
universe for every past date. The repository now accepts an external membership CSV and filters
OHLCV rows using the membership interval for each row's evaluation date.

Intervals use half-open semantics:

```text
[valid_from, valid_to)
```

`valid_to` is exclusive; an empty value means the membership remains active. Overlapping intervals
for one ticker are rejected. Ticker symbols remain strings, so leading zeroes and local suffixes are
preserved.

## Input contract

The CSV must contain:

```text
ticker,valid_from,valid_to
AAA,2018-01-01,2020-02-01
BBB,2019-06-01,
```

The source identifier and usage/license constraint are required CLI arguments, not inferred from the
data file. Raw provider-derived membership files should remain outside version control.

## Versioned stable-identity schema

Schema `point_in_time_universe.v2` separates a stable `security_id` from the historical `ticker` and
optional `provider_symbol`. It also records `known_at`, so a later rename or correction cannot be
used before the date on which the fact was knowable:

```text
security_id,ticker,provider_symbol,market,exchange,valid_from,valid_to,known_at,change_reason
security-123,AAA,AAA.US,us,,2018-01-01,2021-01-01,2018-01-01,initial_listing
security-123,AAB,AAB.US,us,,2021-01-01,,2021-02-01,rename
```

v2 rejects overlapping identity intervals and overlapping ticker/provider-symbol mappings for
different identities. Non-overlapping ticker reuse is allowed. Empty `valid_to` is open-ended, and
identifiers remain strings so values such as `00878` are preserved. The manifest fingerprints the
identity, symbol, effective-date, and knowability metadata without embedding raw rows.

Validate v2 explicitly:

```bash
python -m scripts.validate_universe_membership \
  --input /path/to/membership-v2.csv \
  --output /path/to/membership-v2-manifest.json \
  --schema-version v2 \
  --name sp100_point_in_time \
  --source "licensed constituent archive" \
  --source-license "research-only; redistribution prohibited"
```

The v1 loader remains available for existing experiments. `migrate_v1_to_v2` is an explicit
compatibility bridge that derives `legacy:<ticker>` identities and uses `valid_from` as a
conservative `known_at`; it is not a historical identity repair and does not close Issue #29.
Training entrypoints accept `--universe-schema-version v1|v2`, and the v2 importer in
`tsi.data.universe_import` additionally records mapping version, retrieval time, snapshot date, and
input SHA-256 for arbitrary external column layouts.

The import command writes only a redacted manifest; the licensed input remains local:

```bash
python -m scripts.import_universe_archive \
  --input /path/to/vendor_archive.csv \
  --output /tmp/membership-import-manifest.json \
  --name sp100_point_in_time \
  --source "licensed constituent archive" \
  --source-license "research-only; redistribution prohibited" \
  --retrieved-at 2026-08-01T12:00:00Z \
  --snapshot-date 2026-07-31 \
  --mapping-version vendor-2026-08 \
  --security-id-column entity_id \
  --ticker-column local_symbol \
  --valid-from-column effective_start \
  --valid-to-column effective_end \
  --known-at-column announced_on
```

Validate and fingerprint a snapshot:

```bash
python -m scripts.validate_universe_membership \
  --input /path/to/membership.csv \
  --output /path/to/membership_manifest.json \
  --name sp100_point_in_time \
  --source "licensed constituent archive" \
  --source-license "research-only; redistribution prohibited"
```

The manifest records the interval semantics, date range, counts, source constraints, and a canonical
SHA-256 fingerprint of the membership rows.

## Using the benchmark filter

Pass the same membership CSV and metadata to the purged baseline experiment:

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --universe-membership /path/to/membership.csv \
  --universe-schema-version v1 \
  --universe-name sp100_point_in_time \
  --membership-source "licensed constituent archive" \
  --membership-source-license "research-only; redistribution prohibited" \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --purge-size 5 \
  --output /tmp/sp100_point_in_time_summary.json
```

The summary carries the membership manifest, making it possible to compare a point-in-time run with
the current-universe pilot without committing the raw membership file. A legally usable historical
source and a re-run of the benchmark are still required before making a quantitative
survivorship-bias claim.

For the paired current-vs-PIT report, use `python -m scripts.compare_universe_benchmarks` after both
runs have identical fold schedules, date windows, labels/features, calibration, threshold, and model
configuration. The report emits only aggregate row/member deltas, fingerprints, paired fold-level
uncertainty intervals, and coverage audit counts. It fails closed on protocol mismatch and does not
claim that unavailable delisted data are equivalent to nonmembership.

The engineering sequence is tracked in
[Issue #91](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/91),
[Issue #92](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/92), and
[Issue #93](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/93). The parent
[Issue #29](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/29) remains open until
a licensed historical constituent source, inactive/delisted OHLCV coverage, and a completed paired
benchmark are available.

Use the same membership input and metadata for the deep trainer. This is required before comparing
deep and baseline metrics:

```bash
PYTHONPATH=src python -m scripts.train_deep \
  --input data/raw/sp100/ohlcv.csv \
  --universe-membership /path/to/membership.csv \
  --universe-schema-version v1 \
  --universe-name sp100_point_in_time \
  --membership-source "licensed constituent archive" \
  --membership-source-license "research-only; redistribution prohibited" \
  --train-size 252 --calibration-size 63 --test-size 63 --purge-size 5 \
  --device cuda
```
