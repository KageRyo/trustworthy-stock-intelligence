# Point-in-Time Universe Membership

Historical experiments must not use the current constituent list as if every
symbol belonged to the universe for every past date. The repository now accepts
an external membership CSV and filters OHLCV rows using the membership interval
for each row's evaluation date.

Intervals use half-open semantics:

```text
[valid_from, valid_to)
```

`valid_to` is exclusive; an empty value means the membership remains active.
Overlapping intervals for one ticker are rejected. Ticker symbols remain
strings, so leading zeroes and local suffixes are preserved.

## Input contract

The CSV must contain:

```text
ticker,valid_from,valid_to
AAA,2018-01-01,2020-02-01
BBB,2019-06-01,
```

The source identifier and usage/license constraint are required CLI arguments,
not inferred from the data file. Raw provider-derived membership files should
remain outside version control.

Validate and fingerprint a snapshot:

```bash
python -m scripts.validate_universe_membership \
  --input /path/to/membership.csv \
  --output /path/to/membership_manifest.json \
  --name sp100_point_in_time \
  --source "licensed constituent archive" \
  --source-license "research-only; redistribution prohibited"
```

The manifest records the interval semantics, date range, counts, source
constraints, and a canonical SHA-256 fingerprint of the membership rows.

## Using the benchmark filter

Pass the same membership CSV and metadata to the purged baseline experiment:

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --universe-membership /path/to/membership.csv \
  --universe-name sp100_point_in_time \
  --membership-source "licensed constituent archive" \
  --membership-source-license "research-only; redistribution prohibited" \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --purge-size 5 \
  --output /tmp/sp100_point_in_time_summary.json
```

The summary carries the membership manifest, making it possible to compare a
point-in-time run with the current-universe pilot without committing the raw
membership file. A legally usable historical source and a re-run of the
benchmark are still required before making a quantitative survivorship-bias
claim.
