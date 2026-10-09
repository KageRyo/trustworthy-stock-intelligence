# Experiment 015: Reliability Trust Independent of Risk Probability

## Question

Before this experiment, serving computed `uncertainty = binary_entropy(p)` and `trust = p * (1 - 0.5 * uncertainty)`. Both were functions of the calibrated risk probability `p` alone, so trust correlated 0.99 with risk. The trust score repeated the risk score, and the trust gate acted as a hidden second probability threshold.

This experiment tests replacements that do not depend on `p`, and checks whether they identify predictions that are less reliable. It is pilot research evidence, not investment advice or a trading-performance claim.

## Signals

All signals are fitted on each fold's train and calibration windows only.

| Signal                      | Definition                                                                                  |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `legacy_trust`              | Previous serving trust: `p * (1 - 0.5 * entropy(p))`                                        |
| `legacy_entropy_confidence` | `1 - entropy(p)`                                                                            |
| `disagreement_confidence`   | `1 -` percentile of 10-member date-block bootstrap ensemble disagreement (calibrated scale) |
| `novelty_confidence`        | `1 -` percentile of Ledoit-Wolf Mahalanobis distance to the training features               |
| `epistemic_trust`           | `data_quality * (1 - mean(disagreement percentile, novelty percentile))`                    |
| `random`                    | Uniform random ordering baseline                                                            |

The run also reports class-conditional (Mondrian) split-conformal sets at `alpha = 0.1`.

## Protocol

- The same S&P 100 Yahoo Finance/yfinance snapshot as Experiment 007 (OHLCV SHA-256 `6b1357c8…5ba6`), 101 tickers, 2015-01-02 onward.
- Same 7 daily features, 5-trading-day drawdown label at -5%, `252 / 5 / 63 / 5 / 63` purged walk-forward folds, logistic regression, Platt calibration, and an F1 alert threshold chosen on the calibration window.
- 39 folds, 244,268 test rows, test event rate 10.2%.
- Selective metrics keep the highest-confidence rows first at coverage 10%, 20%, …, 100%. Brier skill is measured against each retained subset's own event rate. Without that, a signal that only keeps calm, low-risk rows looks better just because their base rate is lower.

## Result

### Selective prediction (pooled over 39 folds)

| Signal                    | Brier AURC ↓ | Mean Brier skill ↑ | Mean retained AUC ↑ | Alert FDR, high conf. | Alert FDR, low conf. |
| ------------------------- | -----------: | -----------------: | ------------------: | --------------------: | -------------------: |
| random                    |       0.0921 |            -0.0014 |              0.6113 |                0.8362 |               0.8344 |
| legacy_trust              |       0.1157 |            -0.0167 |              0.5755 |                0.8340 |               0.8459 |
| legacy_entropy_confidence |       0.0688 |            -0.0029 |              0.5829 |                0.8460 |               0.8340 |
| disagreement_confidence   |       0.0703 |            -0.0238 |              0.5895 |                0.8478 |               0.8322 |
| novelty_confidence        |       0.0726 |            -0.0394 |              0.5730 |                0.8663 |               0.8268 |
| epistemic_trust           |       0.0706 |            -0.0366 |              0.5772 |                0.8597 |               0.8292 |

- The new signals succeed at decoupling. Pooled correlation with `p`: `epistemic_trust` is -0.19, while `legacy_trust` is 0.99.
- They do **not** find more-reliable predictions. Brier AURC improves only because high-confidence rows are calmer and have lower event rates. After adjusting for base rate, no signal beats random ordering on Brier skill. `epistemic_trust` beats random on 28% of folds.
- Alerts from high-epistemic-trust rows are *less* precise. In this setting, novel inputs are volatile regimes, and volatile regimes are when drawdowns are most predictable.

### Using trust to gate alerts

| Rule                                      | Alert rate | Alert FDR | Recall |
| ----------------------------------------- | ---------: | --------: | -----: |
| F1 threshold only                         |     0.3220 |    0.8353 | 0.5192 |
| Previous rule: also `legacy_trust >= 0.1` |     0.1699 |    0.8409 | 0.2648 |
| Also `epistemic_trust >= 0.1`             |     0.2193 |    0.8623 | 0.2957 |

- The previous gate halved alerts and recall and did not improve precision.
- An epistemic gate is worse. Alerts it blocks have FDR 0.778, and alerts it keeps have FDR 0.862.

### Abstaining on low-risk rows with high uncertainty

For rows below the watch threshold (watch threshold = 0.8 × alert threshold):

| Uncertainty threshold | Share of all rows | Event rate | Mean predicted `p` | Event rate of remaining no-alert rows |
| --------------------: | ----------------: | ---------: | -----------------: | ------------------------------------: |
|                   0.8 |            0.0170 |     0.0831 |             0.0502 |                                0.0593 |
|                   0.9 |            0.0032 |     0.0864 |             0.0526 |                                0.0601 |

High-uncertainty, low-risk rows are under-predicted: the observed event rate is 8.3%, against a predicted 5.0%. Reporting them as `abstain` instead of a confident `no_alert` is supported.

### Conformal sets

Class-conditional coverage at `alpha = 0.1` was 0.906 for drawdown rows and 0.875 for no-drawdown rows. 67% of test sets contain both labels. At 90% coverage, the 7-feature model cannot separate outcomes for most rows. The run reports conformal sets as reason codes only, because in the binary case they are a function of `p`.

## Decision for serving

`scripts/predict_latest_baseline.py` now defaults to `--trust-method reliability`:

- `uncertainty_score` is the epistemic uncertainty: the mean of the disagreement and novelty percentiles. It can move a below-watch row to `abstain`. It never blocks an alert.
- `trust_score` is data quality (labeled-history depth and staleness relative to the batch) times the existing calibration-drift multiplier. It does not depend on `p` or on epistemic uncertainty (`epistemic_trust_weight = 0`).
- The default alert trust threshold is 0.4. Under detected drift (multiplier 0.5), alerts need data quality of at least 0.8.
- New reason codes: `ensemble_disagreement_high`, `input_out_of_distribution`, `limited_data_quality`, `stale_ticker_data`, `reliability_unavailable`, and `conformal_set_*`.
- `--trust-method legacy` reproduces the previous behavior.

Expected impact: alert volume roughly doubles, from about 17% to about 32% of rows in this pilot, and recall rises from 0.26 to 0.52 at unchanged precision. The F1-selected threshold decides alert volume. A precision- or volume-targeted alert policy is the next step. Do not re-introduce a probability-derived trust gate.

## Reproduce

```bash
python -m scripts.evaluate_selective_trust \
  --input data/raw/sp100/ohlcv.csv \
  --output-dir experiments/015_reliability_trust/runs/sp100_logistic_platt_reliability
```

The run takes about 1 minute on CPU. It is deterministic for a fixed `--random-state` (default 42). The outputs are `summary.json` and `risk_coverage.csv`. Hashes are in [`run_manifest.json`](run_manifest.json).

## Limitations

- Current S&P 100 constituents only: survivorship bias (Issue #29). This is one pilot universe; Taiwan markets were not evaluated.
- These results are for one model family (logistic regression) with 7 technical features. Signals that fail here might still help a model with more information, and they should be re-tested after feature work.
- Conformal thresholds use the same calibration rows as the Platt calibrator, so coverage is approximate rather than a strict split-conformal guarantee.
- The data-quality component is constant across most S&P 100 rows because history is long and bars are complete. Its value shows up with short-history Taiwan listings and on-demand tickers, not in this benchmark.
