# Experiment 016: Alert Threshold Policies

## Question

Through v0.5.0, serving chose the alert threshold by maximizing F1 on the calibration window and set
the watch threshold at 0.8 × the alert threshold. Experiment 015 removed the probability-derived
trust gate that had been hiding how permissive this was: on the S&P 100 pilot, F1 alerts cover about
32% of test rows at a false-discovery rate of about 0.84.

This experiment compares threshold policies that are chosen on the calibration window only:

- `f1`: the previous default.
- `target_precision:<p>`: the lowest threshold whose calibration precision reaches `p` with at least
  20 alerts. This maximizes recall at that precision.
- `alert_rate:<r>`: the lowest threshold whose calibration alert rate is at most `r`. This caps
  alert volume.

It is pilot research evidence, not investment advice or a trading-performance claim.

## Protocol

- The same S&P 100 Yahoo Finance/yfinance snapshot and protocol as Experiments 007 and 015:
  - OHLCV SHA-256 `6b1357c8…5ba6`.
  - 7 daily features; label is a drawdown of -5% or worse within 5 trading days.
  - `252 / 5 / 63 / 5 / 63` purged walk-forward folds.
  - Logistic regression with Platt calibration.
- 39 folds and 244,268 test rows; the test event rate is 10.2%.
- Metrics, all measured on test rows:
  - Pooled precision and recall.
  - Fold medians.
  - Episode recall: the share of drawdown episodes (consecutive positive rows per ticker) with at
    least one alert.
  - Alert days per ticker per month.
  - Coverage of watch-or-alert when watch = 0.8 × alert.
  - The share of folds where a policy's precision beats F1.

## Result

| Policy                  | Alert rate | Precision | Recall | Episode recall | Fold-median rate | Fold-median precision | Beats F1 (folds) | Alert days / ticker-month |
| ----------------------- | ---------: | --------: | -----: | -------------: | ---------------: | --------------------: | ---------------: | ------------------------: |
| `f1`                    |      0.322 |     0.165 |  0.519 |          0.525 |            0.260 |                 0.133 |                – |                      6.75 |
| `target_precision:0.2`  |      0.239 |     0.162 |  0.378 |          0.326 |            0.057 |                 0.154 |             0.72 |                      5.01 |
| `target_precision:0.25` |      0.129 |     0.205 |  0.259 |          0.209 |            0.033 |                 0.154 |             0.79 |                      2.70 |
| `target_precision:0.3`  |      0.089 |     0.221 |  0.192 |          0.159 |            0.019 |                 0.189 |             0.85 |                      1.87 |
| `alert_rate:0.02`       |      0.041 |     0.316 |  0.127 |          0.107 |            0.020 |                 0.202 |             0.89 |                      0.87 |
| `alert_rate:0.05`       |      0.079 |     0.250 |  0.195 |          0.187 |            0.056 |                 0.159 |             0.85 |                      1.67 |
| `alert_rate:0.1`        |      0.132 |     0.213 |  0.276 |          0.287 |            0.109 |                 0.152 |             0.77 |                      2.78 |
| `alert_rate:0.2`        |      0.232 |     0.178 |  0.404 |          0.431 |            0.212 |                 0.134 |             0.51 |                      4.88 |

Findings:

- **Precision targets do not transfer.** Calibration targets of 0.2, 0.25, and 0.3 realized test
  precision of 0.162, 0.205, and 0.221. Each target was met on only 54–69% of calibration windows. A
  precision promise would therefore be misleading.
- **Alert-rate caps are the honest knob.** They control volume and raise precision monotonically.
  `alert_rate:0.05` beats F1 precision in 85% of folds and cuts alert days per ticker-month from
  6.75 to 1.67.
- **Pooled precision is flattered by market-wide stress.** Calibration-chosen thresholds are
  absolute probabilities, so the realized alert rate rises in crises. In the fold starting
  2020-02-04, `alert_rate:0.05` alerted on 71% of rows at precision 0.44 and recall 0.78. That is
  the desired behavior, but the typical fold gain is more modest: fold-median precision is 0.159
  versus 0.133 for F1.
- **Fewer alerts cost recall.** Recall falls from 0.52 to 0.20 at `alert_rate:0.05`. Under F1, the
  old watch ratio (watch = 0.8 × alert) marked 60% of rows as watch or alert, which is too broad to
  be informative.

## Decision for serving

`scripts/predict_latest_baseline.py` now defaults to two calibration-window rate policies:

- `--alert-policy alert_rate:0.05`: alerts are the top 5% of calibration-window risk.
- `--watch-policy alert_rate:0.2`: watch covers the top 20%. In this experiment, watch-or-alert
  under `alert_rate:0.2` covers 23% of rows with recall 0.40 and episode recall 0.43.

The batch records `alert_policy` metadata (policy, target met, calibration alert rate, watch rate,
and precision). The Go API returns it in `/api/v1/analysis/{ticker}`, and the dashboard shows it in
正體中文 and English. Analysis now reads calibration-drift and alert-policy metadata from each record's
own batch, not from the latest batch.

Single-ticker on-demand runs have only about 63 calibration rows, so a 5% cap means about 3 alert
rows. When fewer than 20 calibration rows alert, the batch `note` records that the thresholds are
noisy, and the dashboard labels the policy as a small calibration sample.

The previous behavior remains available with `--alert-policy objective --watch-policy ratio`.

On the latest S&P 100 batch, the new defaults produce 9 alerts and 13 watches, down from 42 alerts
under F1.

## Reproduce

```bash
python -m scripts.evaluate_alert_policies \
  --input data/raw/sp100/ohlcv.csv \
  --output-dir experiments/016_alert_policy/runs/sp100_logistic_platt_policies
```

The run takes about 35 seconds on CPU and is deterministic. It writes `summary.json` and
`per_fold.csv`. Hashes are in [`run_manifest.json`](run_manifest.json).

## Limitations

- Current S&P 100 constituents only: survivorship bias (Issue #29). Taiwan markets were not
  evaluated.
- All results use one model family with 7 technical features. Better features (the next roadmap
  item) should shift the whole precision-recall frontier. Re-run this experiment after feature work.
- Episode recall counts any alert inside a drawdown label run. It does not measure lead time before
  the price low.
- Cross-sectional daily top-K alerting was not evaluated, because on-demand single-ticker serving
  cannot rank across tickers.
