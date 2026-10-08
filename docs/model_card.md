# Model Card: Daily Drawdown-Risk Baseline

This card describes the model the system serves today. It covers what the model predicts, how it is
built, how well it does, and where it should not be trusted. Numbers come from the linked
experiments; the [decision records](decisions/README.md) explain why each choice was made.

## Summary

| Item         | Served configuration                                                                                                       |
| ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Task         | Probability that a stock's price falls 5% or more below today's close within the next 5 trading days                       |
| Interval     | Daily bars only. Five-minute bars are ingested for freshness but not modeled.                                              |
| Markets      | US stocks; Taiwan TWSE, TPEx, and emerging stocks; Taiwan ETFs                                                             |
| Features     | `technical_range`: 12 features from the ticker's own OHLCV ([ADR 0004](decisions/0004-range-volatility-features.md))       |
| Model        | Logistic regression with median imputation, standardization, and balanced class weights                                    |
| Calibration  | Platt scaling on the latest 63 labeled dates                                                                               |
| Thresholds   | Alert: top 5% of calibration-window risk. Watch: top 20% ([ADR 0003](decisions/0003-alert-rate-threshold-policy.md))       |
| Trust        | Data quality × calibration-drift multiplier, independent of risk ([ADR 0002](decisions/0002-trust-independent-of-risk.md)) |
| Model bundle | Recorded per batch as `baseline_latest:<feature_set>:<input>`                                                              |

## Intended use

- **Intended:** human-in-the-loop review of short-horizon drawdown risk for a watchlist. Every
  warning carries its probability, threshold policy, trust, uncertainty, reason codes, and data
  freshness, so a person can judge it.
- **Not intended:**
  - investment advice;
  - automated trading;
  - position sizing;
  - price prediction;
  - claims about a whole market.

## Data

- **Source:** daily OHLCV from Yahoo Finance through yfinance, with official TWSE, TPEx, and TPEx
  emerging fallbacks for Taiwan codes. Yahoo data is used for pilot research only; see
  [data and model licenses](concepts/data_and_model_licenses.md).
- **History:** on-demand analysis downloads each ticker from 2015-01-01. Batch runs use the supplied
  OHLCV file.
- **Known data issues:**
  - Yahoo writes zero-volume placeholder bars on Taiwan typhoon closures. The technical features
    still see a zero return and zero volume ratio on those days.
  - Universes are current constituents, which brings survivorship bias (Issue #29).

## Label

`risk_label = 1` when the minimum adjusted close over trading days `t+1` to `t+5` is at least 5%
below the adjusted close on day `t` ([risk labeling](reference/risk_labeling.md)). The pilot event
rate is about 10% on S&P 100 and Taiwan large caps, and about 12% on broader samples.

## Features

All 12 features use only bars up to and including `t`. Open, high, and low are split-adjusted by
`adj_close / close`.

| Group     | Features                                                                                                  |
| --------- | --------------------------------------------------------------------------------------------------------- |
| Technical | `return_1d`, `return_5d`, `sma_5_gap`, `sma_10_gap`, `volatility_5d`, `volatility_10d`, `volume_ratio_5d` |
| Range     | `parkinson_vol_10d`, `garman_klass_vol_10d`, `atr_14_pct`, `volatility_20d`, `drawdown_from_20d_high`     |

Tested and not served:

- market-relative returns and regime features (Experiment 017);
- 60-day beta, which needs a serving reference-data path (Experiment 017);
- Taiwan institutional-flow and margin features (Experiment 018,
  [ADR 0005](decisions/0005-no-taiwan-chip-features.md)).

## Training and serving

1. **Features and labels.** Build features and future-drawdown labels, then drop rows whose label
   window is incomplete.
1. **Windows.** Split labeled dates into three windows:
   - train: all earlier dates;
   - calibration: the latest 63 dates;
   - drift: a later 21-date window used only to assess calibration drift.
1. **Fit.** Fit the logistic model on train rows and Platt calibration on calibration rows. Choose
   the alert and watch thresholds from calibration-window alert rates.
1. **Score.** Score the latest feature-complete row per ticker.
1. **Uncertainty.** A 10-member bootstrap ensemble measures disagreement, and a novelty distance
   measures how far the input sits from training data. Both are ranked against the calibration
   window. Uncertainty above 0.8 moves below-watch rows to `abstain` and never blocks an alert.
1. **Trust.** Trust is data quality times the drift multiplier:
   - data quality is labeled history relative to 252 rows, halved for stale bars;
   - degraded calibration lowers the drift multiplier, and severe drift forces `abstain`.
1. **Alerts.** An alert needs trust of at least 0.4.
1. **Freshness.** At read time the Go API measures freshness from the market's session close for
   daily bars. Data older than 36 hours is downgraded, and data older than 5 days is blocked
   ([analysis API](reference/api/analysis_api.md)).

Single-ticker on-demand runs have only about 63 calibration rows, so a 5% cap means about 3 alert
rows. The batch `note` and the dashboard flag these thresholds as a small calibration sample.

## Performance

Purged walk-forward evaluation uses the `252 / 5 / 63 / 5 / 63` schedule, 39 folds, and paired
fold-bootstrap intervals ([experiment protocol](research/experiment_protocol.md)).

Ranking and calibration, `technical_range`
([Experiment 017](../experiments/017_feature_sets/README.md)):

| Sample                              | Tickers |   AUC | PR-AUC |   ECE | AUC change vs. 7 technical features |
| ----------------------------------- | ------: | ----: | -----: | ----: | ----------------------------------- |
| S&P 100                             |     101 | 0.641 |  0.173 | 0.051 | +0.026 [0.016, 0.035]               |
| S&P 500 excluding S&P 100 (holdout) |     402 | 0.632 |  0.190 | 0.052 | +0.023 [0.015, 0.031]               |
| Taiwan large caps                   |      53 | 0.738 |  0.221 | 0.051 | +0.029 [0.019, 0.039]               |

Served thresholds on S&P 100 with `technical_range` (rerun of Experiment 016, recorded in Experiment
017):

| Policy            | Alert rate | Precision | Recall | Fold-median precision | Alert days per ticker-month |
| ----------------- | ---------: | --------: | -----: | --------------------: | --------------------------: |
| `alert_rate:0.05` |      0.081 |     0.279 |  0.220 |                 0.232 |                        1.70 |
| F1 (for contrast) |      0.292 |     0.177 |  0.505 |                 0.156 |                        6.13 |

Precision of about 0.28 against a 10% base rate means most alerts are still false alarms. The watch
tier (top 20%) recalls 0.37 of drawdown rows.

## Explanations

Each prediction lists up to five feature attributions. An attribution is the logistic coefficient
times the standardized feature value, a model-specific and non-causal diagnostic. Reason codes cover
thresholds, trust, uncertainty, drift, data quality, and conformal sets. Freshness has its own
reason code. The dashboard translates all of these into English and 正體中文.

## Limitations and risks

- **Data:**
  - Results come from current-constituent pilots on Yahoo data. They are not externally validated
    and carry survivorship and provider-revision risk.
  - Taiwan evidence covers listed large caps and a 199-stock TWSE sample. TPEx and emerging coverage
    is thin.
- **Regimes:** regime shifts break calibration. In Experiment 007, calibration failed in the
  COVID-19 fold. Drift detection lowers trust but cannot prevent misses.
- **Reliability signals:** ensemble and novelty uncertainty did not identify less reliable
  predictions in Experiment 015, so trust deliberately ignores them for alerts.
- **On-demand calibration:** on-demand single-ticker models train on one ticker's history, and their
  thresholds rest on about 3 calibration alerts.
- **Scope:** the evaluation measures risk probability, not trading performance, and does not account
  for transaction costs.

## Reproduce and audit

- Evidence: Experiments [007](../experiments/007_research_evidence/README.md) (protocol),
  [013](../experiments/013_aligned_model_family_benchmark/README.md) (model family),
  [015](../experiments/015_reliability_trust/README.md) (trust),
  [016](../experiments/016_alert_policy/README.md) (thresholds),
  [017](../experiments/017_feature_sets/README.md) (features), and
  [018](../experiments/018_taiwan_chip_features/README.md) (Taiwan chip data).
- Serving code: `scripts/predict_latest_baseline.py`, `src/tsi/features/sets.py`, and
  `src/tsi/trust/reliability.py`.
- Every batch stores its run ID, `data_as_of`, `generated_at`, feature interval, model bundle,
  calibration-drift metadata, and alert-policy metadata in PostgreSQL.
