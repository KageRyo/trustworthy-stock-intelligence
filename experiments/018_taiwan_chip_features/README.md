# Experiment 018: Taiwan Institutional-Flow and Margin Features

## Question

Taiwan market commentary leans heavily on "chip" data: daily net buying by the three institutional
investor groups (foreign investors, investment trusts, and dealers) and margin and short balances.
TWSE publishes both for every listed stock after each close. Do they improve five-day drawdown-risk
discrimination beyond the served `technical_range` feature set from Experiment 017?

It is pilot research evidence, not investment advice or a trading-performance claim.

## Data

- **Chip history:** `scripts/backfill_twse_chips.py` fetched TWSE T86 (institutional net shares) and
  MI_MARGN (margin and short balances in lots) for every TWSE trading date from 2015-01-05 to
  2026-10-06:
  - 2,854 dates each, with no failures or missing dates.
  - 2,981,482 institutional rows and 3,042,004 margin rows.
  - Payloads are validated with Pydantic schemas and cached per date.
  - T86 renamed its foreign-investor columns on 2018-01-02. `foreign_net` sums the two newer foreign
    columns so its meaning does not change.
- **Calendar repair:** Yahoo Finance writes zero-volume placeholder bars on Taiwan typhoon closures,
  such as 2015-07-10, 2016-09-27, and 2026-07-10. TWSE has no chip data for those days. The backfill
  skips them, and the features treat them as no-trade days.
- **Samples:**

| Sample                | Role      | Tickers evaluated | Test rows | Event rate | Notes                                                                                  |
| --------------------- | --------- | ----------------: | --------: | ---------: | -------------------------------------------------------------------------------------- |
| `tw_large` (Exp. 017) | Discovery |                50 |   122,440 |      0.097 | The 3 TPEx stocks have no TWSE chip data and drop out.                                 |
| `tw_holdout` (new)    | Holdout   |               199 |   488,078 |      0.122 | Seed-18 sample of 200 TWSE common stocks listed by 2014. `2227` has no margin history. |

`tw_holdout` samples from the official TWSE company catalogue (OpenAPI `t187ap03_L`, captured
2026-10-06). It keeps 4-digit common-stock codes listed on or before 2014-12-31, excludes the
discovery tickers, and draws 200 of the remaining 747 with `numpy.random.default_rng(18)`. All 200
had full Yahoo Finance history.

## Features

All features are computed on each ticker's own trading calendar:

- **Flow features** (`technical_range_flows`):
  - Foreign net shares divided by traded shares, over 5 and 20 days.
  - Investment-trust net shares divided by traded shares, over 5 and 20 days.
  - Dealer net shares divided by traded shares, over 5 days.
- **Margin features** (`technical_range_margin`):
  - 5-day change in the margin balance, divided by traded shares.
  - 5-day change in the short balance, divided by traded shares.
  - Margin balance in days of average 20-day volume.
  - Short-to-margin ratio.
- `technical_range_chips` uses all 9.

Missing values:

- A TWSE stock that is absent from a table on a covered date counts as zero.
- A stock that never appears in a table, such as a TPEx stock, is missing.

Timing:

- Chip data for date `t` is published after the close.
- The primary runs shift every chip feature by one trading day (`--chip-lag 1`), so a row at `t`
  uses chip data through `t-1`.
- `--chip-lag 0` is a sensitivity check for after-publication batch scoring.

Protocol, same as Experiment 017:

- 5-day, -5% drawdown label.
- `252 / 5 / 63 / 5 / 63` purged walk-forward folds.
- Logistic regression with Platt calibration.
- `alert_rate:0.05` alerts and `alert_rate:0.2` watch.
- Paired 95% fold-bootstrap intervals over 39 folds, 4,000 resamples.
- Rows missing any compared column are dropped, so every set sees the same rows.

## Result

Discovery (`tw_large`, lag 1):

| Feature set              |    AUC | PR-AUC | Brier skill |    ECE | Alert precision | Alert recall | Fold-median alert precision | Watch recall |
| ------------------------ | -----: | -----: | ----------: | -----: | --------------: | -----------: | --------------------------: | -----------: |
| `technical_range`        | 0.7239 | 0.2078 |      0.0455 | 0.0496 |           0.253 |        0.180 |                       0.255 |        0.469 |
| `technical_range_chips`  | 0.7171 | 0.2030 |      0.0412 | 0.0502 |           0.249 |        0.166 |                       0.259 |        0.454 |
| `technical_range_flows`  | 0.7019 | 0.2020 |      0.0412 | 0.0500 |           0.246 |        0.172 |                       0.237 |        0.459 |
| `technical_range_margin` | 0.7261 | 0.2065 |      0.0448 | 0.0502 |           0.253 |        0.171 |                       0.245 |        0.460 |

Holdout (`tw_holdout`, lag 1):

| Feature set              |    AUC | PR-AUC | Brier skill |    ECE | Alert precision | Alert recall | Fold-median alert precision | Watch recall |
| ------------------------ | -----: | -----: | ----------: | -----: | --------------: | -----------: | --------------------------: | -----------: |
| `technical_range`        | 0.7323 | 0.2701 |      0.0764 | 0.0457 |           0.329 |        0.181 |                       0.348 |        0.472 |
| `technical_range_chips`  | 0.7315 | 0.2705 |      0.0763 | 0.0457 |           0.331 |        0.178 |                       0.335 |        0.469 |
| `technical_range_flows`  | 0.7312 | 0.2696 |      0.0757 | 0.0455 |           0.328 |        0.181 |                       0.342 |        0.469 |
| `technical_range_margin` | 0.7325 | 0.2710 |      0.0771 | 0.0457 |           0.332 |        0.179 |                       0.340 |        0.471 |

Paired deltas against `technical_range`:

| Sample    | Lag | Comparison               | ΔAUC                       | ΔPR-AUC                    | ΔAlert precision           | ΔAlert recall              | AUC fold wins |
| --------- | --: | ------------------------ | -------------------------- | -------------------------- | -------------------------- | -------------------------- | ------------: |
| Discovery |   1 | `technical_range_chips`  | -0.0068 [-0.0112, -0.0023] | -0.0048 [-0.0108, -0.0004] | -0.0090 [-0.0290, +0.0100] | -0.0124 [-0.0222, -0.0029] |          0.31 |
| Discovery |   1 | `technical_range_flows`  | -0.0220 [-0.0507, -0.0064] | -0.0058 [-0.0115, -0.0019] | -0.0025 [-0.0141, +0.0108] | -0.0027 [-0.0086, +0.0027] |          0.08 |
| Discovery |   1 | `technical_range_margin` | +0.0021 [-0.0014, +0.0059] | -0.0014 [-0.0073, +0.0030] | -0.0072 [-0.0260, +0.0107] | -0.0096 [-0.0197, +0.0008] |          0.54 |
| Discovery |   0 | `technical_range_chips`  | -0.0054 [-0.0098, -0.0004] | -0.0044 [-0.0104, +0.0002] | -0.0102 [-0.0305, +0.0090] | -0.0106 [-0.0212, -0.0003] |          0.26 |
| Holdout   |   1 | `technical_range_chips`  | -0.0008 [-0.0019, +0.0004] | +0.0004 [-0.0005, +0.0013] | +0.0030 [-0.0007, +0.0064] | -0.0029 [-0.0062, +0.0003] |          0.33 |
| Holdout   |   1 | `technical_range_flows`  | -0.0011 [-0.0021, -0.0001] | -0.0005 [-0.0010, -0.0000] | +0.0003 [-0.0012, +0.0019] | -0.0006 [-0.0017, +0.0004] |          0.26 |
| Holdout   |   1 | `technical_range_margin` | +0.0002 [-0.0004, +0.0009] | +0.0009 [+0.0002, +0.0016] | +0.0031 [-0.0001, +0.0061] | -0.0017 [-0.0051, +0.0015] |          0.56 |
| Holdout   |   0 | `technical_range_chips`  | -0.0006 [-0.0019, +0.0007] | +0.0007 [-0.0002, +0.0017] | +0.0044 [+0.0007, +0.0079] | -0.0022 [-0.0056, +0.0011] |          0.41 |

Every lag-0 comparison is in each run's `summary.json`.

## Findings

- **Chip features do not improve drawdown-risk discrimination.**
  - On the discovery sample, all 9 features lower AUC by 0.007, and the flows alone lower it by
    0.022, beating the baseline in only 8% of folds.
  - On the 199-stock holdout, no set moves AUC by more than 0.0011 or alert precision by more than
    0.0044. The intervals straddle zero or show effects too small to matter for alerts.
- **The flow coefficients have no stable direction.**
  - On discovery, the 5-day foreign flow has a mean coefficient of -0.08 with a fold standard
    deviation of 0.17, and the 20-day foreign flow is +0.08 ± 0.18.
  - The margin balance in days of volume is +0.22 on discovery but -0.07 on holdout.
  - Only the short-to-margin ratio keeps a consistent sign (about +0.07), and it adds nothing beyond
    `technical_range`.
- **Timing is not the cause.** Same-day (lag 0) and next-day (lag 1) chip data give the same
  conclusion, so the null result is not caused by the conservative publication lag.
- **Taiwan baseline discrimination is already higher than in the US.** `technical_range` reaches an
  AUC of 0.72 to 0.73 on both Taiwan samples, against 0.63 to 0.64 on S&P samples. Range and
  volatility features already capture much of the drawdown-risk signal that chip flows might carry.

## Decision for serving

Serving stays on `technical_range`. No PostgreSQL chip tables, scheduled chip ingestion, or
Taiwan-specific serving feature set are added.

The adapters, the resumable backfill, the leakage-safe chip features, and the registered feature
sets remain available for later research, for example:

- nonlinear models that can use interactions such as foreign selling during a price decline;
- market-relative labels;
- longer horizons, where flows may matter more than over 5 days.

## Reproduce

```bash
python -m scripts.capture_taiwan_universe \
  --members-output data/raw/taiwan_universe/members.csv \
  --manifest-output data/raw/taiwan_universe/manifest.json
# Draw tw_holdout as described in "Data", then download it with
# python -m scripts.download_tickers --market twse --dataset-name tw_holdout \
#   --output-dir data/raw/tw_holdout --tickers <the 200 sampled codes>
python -m scripts.backfill_twse_chips \
  --calendar data/raw/tw_large/ohlcv.csv --start 2015-01-01 --end 2026-10-07 --min-interval 2.0

SETS=technical_range,technical_range_chips,technical_range_flows,technical_range_margin
for sample in tw_large tw_holdout; do
  for lag in 1 0; do
    python -m scripts.evaluate_feature_sets --input data/raw/$sample/ohlcv.csv \
      --chip-archive data/raw/twse_chips --chip-lag $lag \
      --baseline-feature-set technical_range --feature-sets $SETS \
      --output-dir experiments/018_taiwan_chip_features/runs/${sample}_logistic_platt_chips_lag$lag
  done
done
```

- **Run times:** the backfill makes 5,708 requests and took about 4.3 hours at a 2-second minimum
  interval. Each discovery run takes about 15 seconds, and each holdout run about 2.5 minutes.
  Repeated lag-1 runs reproduced every output file byte for byte.
- **Files:** the sampled ticker list and its Yahoo coverage are in
  `data/raw/taiwan_universe/tw_holdout_sample.csv`. Input and output hashes are in
  [`run_manifest.json`](run_manifest.json).

## Limitations

- Both samples are current-listed TWSE stocks (survivorship bias, Issue #29). TPEx and emerging
  stocks are excluded because TPEx publishes chip data through separate endpoints.
- Only logistic regression with linear terms was tested. The negative result applies to this model
  family and this label.
- Chip features cover T86 and MI_MARGN only. Foreign ownership levels, securities lending, and
  broker-branch data were not tested.
- Yahoo Finance supplies OHLCV and volume. Its typhoon placeholder bars also affect the technical
  features (a zero return and zero volume ratio on those days) for every feature set.
- TWSE data is used for research; review TWSE terms before redistributing derived data.
