# Experiment 017: Range, Market-Relative, and Regime Feature Sets

## Question

Through v0.6.0, the baseline used 7 daily technical features (returns, moving-average gaps,
close-to-close volatility, and a volume ratio). At the serving `alert_rate:0.05` policy, test
precision was about 0.25 against a 10% event rate, and the fold-median precision was 0.16
(Experiment 016). Can new information sources raise the model's discrimination rather than only
moving thresholds?

This experiment adds two feature families and compares named feature sets on identical rows and
folds:

- **Range features** use only the ticker's own OHLC bars:
  - Parkinson and Garman-Klass volatility over 10 days.
  - ATR(14) as a share of price.
  - 20-day close-to-close volatility.
  - Drawdown from the 20-day high.
  - Open, high, and low are split-adjusted by `adj_close / close`.
- **Market-relative features** use reference series aligned with a backward as-of join:
  - _Relative_: excess return versus SPY over 5 and 20 days, excess return versus the ticker's
    Select Sector SPDR ETF over 5 and 20 days, and a 60-day beta.
  - _Regime_: SPY 5-day return, SPY drawdown from its 60-day high, VIX level, and VIX 5-day change.

It is pilot research evidence, not investment advice or a trading-performance claim.

## Protocol

- Same label and schedule as Experiments 015 and 016:
  - The label is a drawdown of -5% or worse within 5 trading days.
  - Folds are `252 / 5 / 63 / 5 / 63` purged walk-forward splits.
  - Logistic regression with Platt calibration.
- Each run drops rows that miss any column of any compared set before splitting. Every set therefore
  sees the same train, calibration, and test rows. The 60-day beta adds about 50 warm-up days per
  ticker compared with Experiment 016.
- Alert and watch thresholds use the serving policies (`alert_rate:0.05`, `alert_rate:0.2`), chosen
  on the calibration window only. Watch recall counts rows at watch or alert.
- Ranking and calibration metrics are fold means. Alert precision and recall are pooled over test
  rows. Paired 95% intervals come from a percentile bootstrap over the 39 temporal test folds (4,000
  resamples, seed 42).
- Three samples, each with 39 folds and no skipped folds:

| Sample                         | Role                  | Tickers | Test rows | Event rate | Reference series                   |
| ------------------------------ | --------------------- | ------: | --------: | ---------: | ---------------------------------- |
| S&P 100                        | Discovery             |     101 |   244,268 |      0.104 | SPY, ^VIX, 11 sector ETFs          |
| S&P 500 excluding S&P 100      | Ticker holdout        |     402 |   956,955 |      0.120 | SPY, ^VIX, 11 sector ETFs          |
| Taiwan large caps (`tw_large`) | Market transfer check |      53 |   129,819 |      0.104 | ^TWII only (no sector ETF, no VIX) |

- The S&P 100 and S&P 500 OHLCV snapshots are the 2026-05-08 files used since Experiment 007.
  `sp500_ex_sp100` removes the 101 S&P 100 tickers from the S&P 500 file.
- `tw_large` holds 50 large TWSE stocks and the three TPEx stocks from Experiment 014 (`3260`,
  `6147`, `8069`). Bars run from 2015-01-05 to 2026-10-07; the last bar is an intraday partial bar
  without a label.
- Taiwan stocks close before the US session on the same date. The Taiwan run therefore uses only
  ^TWII, which closes with the local session, and the VIX-dependent sets are not run there.

## Discovery and holdout results

S&P 100 (discovery):

| Feature set                |    AUC | PR-AUC | Brier skill |    ECE | Alert precision | Alert recall | Fold-median alert precision | Watch recall |
| -------------------------- | -----: | -----: | ----------: | -----: | --------------: | -----------: | --------------------------: | -----------: |
| `technical`                | 0.6152 | 0.1560 |      0.0080 | 0.0537 |           0.264 |        0.181 |                       0.168 |        0.389 |
| `technical_range`          | 0.6408 | 0.1731 |      0.0220 | 0.0511 |           0.284 |        0.209 |                       0.231 |        0.425 |
| `technical_market`         | 0.6082 | 0.1584 |     -0.0016 | 0.0618 |           0.226 |        0.112 |                       0.198 |        0.287 |
| `technical_range_market`   | 0.6202 | 0.1667 |      0.0050 | 0.0606 |           0.226 |        0.126 |                       0.203 |        0.316 |
| `technical_range_beta`     | 0.6507 | 0.1790 |      0.0243 | 0.0528 |           0.300 |        0.192 |                       0.249 |        0.417 |
| `technical_range_relative` | 0.6372 | 0.1750 |      0.0217 | 0.0517 |           0.294 |        0.194 |                       0.234 |        0.417 |
| `technical_range_regime`   | 0.6189 | 0.1659 |      0.0042 | 0.0600 |           0.210 |        0.132 |                       0.202 |        0.323 |

S&P 500 excluding S&P 100 (ticker holdout):

| Feature set                |    AUC | PR-AUC | Brier skill |    ECE | Alert precision | Alert recall | Fold-median alert precision | Watch recall |
| -------------------------- | -----: | -----: | ----------: | -----: | --------------: | -----------: | --------------------------: | -----------: |
| `technical`                | 0.6095 | 0.1735 |      0.0087 | 0.0550 |           0.297 |        0.167 |                       0.208 |        0.371 |
| `technical_range`          | 0.6324 | 0.1902 |      0.0205 | 0.0521 |           0.313 |        0.189 |                       0.246 |        0.403 |
| `technical_market`         | 0.5981 | 0.1732 |     -0.0010 | 0.0628 |           0.214 |        0.109 |                       0.216 |        0.282 |
| `technical_range_market`   | 0.6151 | 0.1848 |      0.0060 | 0.0613 |           0.224 |        0.123 |                       0.224 |        0.307 |
| `technical_range_beta`     | 0.6376 | 0.1949 |      0.0201 | 0.0540 |           0.318 |        0.179 |                       0.254 |        0.398 |
| `technical_range_relative` | 0.6267 | 0.1909 |      0.0181 | 0.0533 |           0.316 |        0.184 |                       0.245 |        0.396 |
| `technical_range_regime`   | 0.6116 | 0.1822 |      0.0061 | 0.0604 |           0.219 |        0.123 |                       0.228 |        0.309 |

Taiwan large caps:

| Feature set                |    AUC | PR-AUC | Brier skill |    ECE | Alert precision | Alert recall | Fold-median alert precision | Watch recall |
| -------------------------- | -----: | -----: | ----------: | -----: | --------------: | -----------: | --------------------------: | -----------: |
| `technical`                | 0.7092 | 0.2043 |      0.0306 | 0.0495 |           0.254 |        0.161 |                       0.245 |        0.440 |
| `technical_range`          | 0.7384 | 0.2211 |      0.0352 | 0.0510 |           0.271 |        0.178 |                       0.269 |        0.471 |
| `technical_range_beta`     | 0.7417 | 0.2221 |      0.0383 | 0.0521 |           0.274 |        0.174 |                       0.273 |        0.467 |
| `technical_range_relative` | 0.7408 | 0.2262 |      0.0497 | 0.0473 |           0.283 |        0.181 |                       0.262 |        0.484 |

Paired deltas with 95% fold-bootstrap intervals:

| Sample             | Comparison                                  | ΔAUC                    | ΔPR-AUC                 | ΔAlert precision        | ΔAlert recall           | ΔWatch recall           | AUC fold wins |
| ------------------ | ------------------------------------------- | ----------------------- | ----------------------- | ----------------------- | ----------------------- | ----------------------- | ------------: |
| S&P 100            | `technical_range` vs `technical`            | +0.026 [+0.016, +0.035] | +0.017 [+0.011, +0.023] | +0.028 [+0.013, +0.042] | +0.030 [+0.018, +0.043] | +0.037 [+0.018, +0.056] |          0.72 |
| S&P 500 ex S&P 100 | `technical_range` vs `technical`            | +0.023 [+0.015, +0.031] | +0.017 [+0.012, +0.021] | +0.011 [-0.026, +0.035] | +0.019 [+0.010, +0.029] | +0.034 [+0.018, +0.050] |          0.82 |
| Taiwan 53          | `technical_range` vs `technical`            | +0.029 [+0.019, +0.039] | +0.017 [+0.010, +0.023] | +0.035 [+0.012, +0.061] | +0.023 [-0.000, +0.047] | +0.047 [+0.020, +0.073] |          0.87 |
| S&P 100            | `technical_range_beta` vs `technical_range` | +0.010 [+0.004, +0.015] | +0.006 [+0.003, +0.009] | +0.007 [-0.004, +0.017] | -0.004 [-0.017, +0.008] | +0.007 [-0.013, +0.027] |          0.87 |
| S&P 500 ex S&P 100 | `technical_range_beta` vs `technical_range` | +0.005 [+0.001, +0.009] | +0.005 [+0.003, +0.006] | +0.009 [+0.002, +0.018] | +0.000 [-0.009, +0.009] | +0.004 [-0.009, +0.018] |          0.74 |
| Taiwan 53          | `technical_range_beta` vs `technical_range` | +0.003 [-0.000, +0.007] | +0.001 [-0.002, +0.004] | +0.003 [-0.005, +0.011] | -0.004 [-0.016, +0.009] | -0.006 [-0.019, +0.007] |          0.67 |
| S&P 100            | `technical_range_regime` vs `technical`     | +0.004 [-0.021, +0.026] | +0.010 [-0.005, +0.023] | +0.028 [+0.000, +0.056] | +0.004 [-0.043, +0.038] | -0.001 [-0.058, +0.048] |          0.56 |
| S&P 500 ex S&P 100 | `technical_range_regime` vs `technical`     | +0.002 [-0.022, +0.023] | +0.009 [-0.005, +0.020] | +0.017 [-0.012, +0.046] | -0.003 [-0.046, +0.030] | -0.009 [-0.065, +0.039] |          0.67 |

All paired comparisons, including every set against `technical`, are in each run's `summary.json`.

## Findings

- **Range features help in every sample.** Against `technical`, AUC rises by 0.023 to 0.029, PR-AUC
  by 0.017, and watch recall by 0.034 to 0.047. Alert recall rises by 0.019 to 0.030. Alert
  precision rises in all three samples, but the holdout interval includes zero.
- **Market regime features hurt.** Adding SPY return, SPY drawdown, VIX level, and VIX change to
  `technical_range` lowers AUC by about 0.02 and cuts alert recall from 0.21 to 0.13 on S&P 100.
  Their logistic coefficients change sign across folds (VIX level: mean -0.05, standard deviation
  0.83). A one-year training window sees one or two volatility regimes, so the model extrapolates
  these market-wide levels poorly into the next quarter. They also shift every ticker's probability
  together, which absolute calibration thresholds then turn into bursts of alerts.
- **Beta is the only market-relative feature with a consistent gain.** Beta was singled out after an
  ablation on S&P 100, so the S&P 500 holdout was the confirmatory test. There it still adds 0.005
  AUC and 0.009 alert precision with intervals above zero. In Taiwan, against ^TWII, the gain is
  smaller and not significant. Excess returns versus SPY and sector ETFs add nothing on top of
  `technical_range` in the US samples.

## Experiments 015 and 016 with `technical_range`

Both experiments were rerun on S&P 100 with `--feature-set technical_range`.

Experiment 016 (alert policies). `alert_rate:0.05` remains the best trade-off and stays the serving
default:

| Policy            | Precision     | Recall        | Fold-median precision | Beats F1 (folds) | Alert days / ticker-month |
| ----------------- | ------------- | ------------- | --------------------- | ---------------- | ------------------------- |
| `f1`              | 0.165 → 0.177 | 0.519 → 0.505 | 0.133 → 0.156         | –                | 6.75 → 6.13               |
| `alert_rate:0.02` | 0.316 → 0.338 | 0.127 → 0.147 | 0.202 → 0.256         | 0.89 → 0.89      | 0.87 → 0.94               |
| `alert_rate:0.05` | 0.250 → 0.279 | 0.195 → 0.220 | 0.159 → 0.232         | 0.85 → 0.92      | 1.67 → 1.70               |
| `alert_rate:0.1`  | 0.213 → 0.232 | 0.276 → 0.304 | 0.152 → 0.206         | 0.77 → 0.74      | 2.78 → 2.82               |
| `alert_rate:0.2`  | 0.178 → 0.191 | 0.404 → 0.434 | 0.134 → 0.174         | 0.51 → 0.44      | 4.88 → 4.88               |

Experiment 015 (trust and uncertainty). The design conclusions hold:

- Ensemble-disagreement, novelty, and epistemic-trust signals still have negative Brier skill as
  selective-prediction signals.
- Alerts that an epistemic trust gate at 0.05 would block are more precise than the alerts it keeps.
  The false-discovery rate is 0.73 for blocked alerts and 0.84 for kept alerts, so uncertainty still
  must not block alerts.
- Uncertainty abstention at 0.8 now covers 4.1% of rows, up from 1.7%. Those rows have a 10.2%
  drawdown rate, compared with 6.1% for no-alert rows, so marking them `abstain` instead of
  `no_alert` remains the safer label.
- Conformal ambiguity falls from 0.666 to 0.620.

## Decision for serving

`scripts/predict_latest_baseline.py` now defaults to `--feature-set technical_range`:

- It needs only the ticker's own OHLCV, so the US, TWSE, TPEx, and emerging on-demand paths need no
  new provider dependency.
- The batch `model_bundle` records the set as `baseline_latest:<feature_set>:<input>`.
- Feature attributions list the new columns by name.
- `--feature-set technical` restores the v0.6.0 features.

Market-relative sets are not offered to serving yet. A beta feature would require the batch job and
the on-demand bridge to fetch and validate SPY or ^TWII reference bars, with staleness checks, for
an AUC gain of 0.005 to 0.010 in the US and none shown in Taiwan. That is recorded as follow-up
work.

On the latest S&P 100 snapshot (2026-05-07 bars), the serving defaults produce:

- `technical`: 7 alerts, 17 watches, 10 abstains, and 67 no-alert rows.
- `technical_range`: 5 alerts, 14 watches, 8 abstains, and 74 no-alert rows.

## Reproduce

```bash
python -m scripts.download_market_reference \
  --tickers-file data/raw/sp100/tickers.csv --output-dir data/raw/market/us
python -m scripts.download_market_reference \
  --tickers-file data/raw/sp500/tickers.csv --output-dir data/raw/market/us_sp500
python -m scripts.download_tickers --dataset-name tw_large --output-dir data/raw/tw_large \
  --tickers 2330 2317 2454 2308 2382 2881 2882 2891 2303 3711 2412 2886 2884 1216 2885 3231 \
  2357 2892 2345 6669 2880 3034 2002 5880 2883 2890 2887 1101 2603 3008 2207 1303 1301 2395 \
  4938 2379 3037 2327 5871 2301 6505 2912 3045 4904 2609 2615 1326 2408 3017 2376 \
  3260.TWO 6147.TWO 8069.TWO
python -m scripts.download_market_reference --market taiwan \
  --tickers-file data/raw/tw_large/tickers.csv --output-dir data/raw/market/taiwan

SETS=technical,technical_range,technical_market,technical_range_market,technical_range_beta,technical_range_relative,technical_range_regime
python -m scripts.evaluate_feature_sets --input data/raw/sp100/ohlcv.csv \
  --market-reference data/raw/market/us --feature-sets $SETS \
  --extra-pairs technical_range_beta:technical_range \
  --output-dir experiments/017_feature_sets/runs/sp100_logistic_platt_feature_sets
python -m scripts.evaluate_feature_sets --input data/raw/sp500_ex_sp100/ohlcv.csv \
  --market-reference data/raw/market/us_sp500 --feature-sets $SETS \
  --extra-pairs technical_range_beta:technical_range \
  --output-dir experiments/017_feature_sets/runs/sp500_ex_sp100_logistic_platt_feature_sets
python -m scripts.evaluate_feature_sets --input data/raw/tw_large/ohlcv.csv \
  --market-reference data/raw/market/taiwan \
  --feature-sets technical,technical_range,technical_range_beta,technical_range_relative \
  --extra-pairs technical_range_beta:technical_range \
  --output-dir experiments/017_feature_sets/runs/tw_large_logistic_platt_feature_sets

python -m scripts.evaluate_alert_policies --input data/raw/sp100/ohlcv.csv \
  --feature-set technical_range \
  --output-dir experiments/017_feature_sets/runs/sp100_alert_policies_technical_range
python -m scripts.evaluate_selective_trust --input data/raw/sp100/ohlcv.csv \
  --feature-set technical_range \
  --output-dir experiments/017_feature_sets/runs/sp100_reliability_technical_range
```

`sp500_ex_sp100` is derived by dropping the tickers in `data/raw/sp100/tickers.csv` from
`data/raw/sp500/ohlcv.csv`. Its metadata file records both source hashes.

The S&P 100 comparison takes about 50 seconds on CPU, the S&P 500 holdout about 4.5 minutes, and the
Taiwan run about 10 seconds. A repeated Taiwan run reproduced all three output files byte for byte.
Input and output hashes are in [`run_manifest.json`](run_manifest.json).

## Limitations

- Current-constituent universes carry survivorship bias (Issue #29). The S&P 500 holdout is
  cross-sectional; it shares the S&P 100 calendar, so market-wide shocks are not independent between
  the two samples.
- The Taiwan sample is a hand-picked list of large caps, not point-in-time 0050 membership. It
  includes only three TPEx stocks and no emerging stocks. Its higher AUC than the US samples is not
  comparable across universes.
- Sector ETF assignments are a current Yahoo snapshot applied to all history. BK, FISV, and SATS had
  no Yahoo sector and fall back to SPY.
- Only logistic regression was tested. Tree models might use regime features without linear
  extrapolation, but Experiment 013 found them weaker on the technical set.
- Yahoo Finance/yfinance is used for pilot inputs only.
