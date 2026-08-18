# Experiment 009: Taiwan Purged Baseline Pilot

## Status

This is a reproducible, six-ticker Taiwan pilot and a partial implementation of Issue #23. It is not
a full Taiwan-universe study, formal external validation, investment advice, or a
trading-performance claim.

## Dataset snapshot

The snapshot was downloaded on `2026-08-08T19:31:55.083553+00:00` with the explicit ticker list in
[`configs/dataset/taiwan_pilot.yaml`](../../configs/dataset/taiwan_pilot.yaml). The downloader
preserved the display symbols as strings and resolved all six symbols to TWSE-style Yahoo Finance
queries.

| Field                              | Value                                                              |
| ---------------------------------- | ------------------------------------------------------------------ |
| Provider                           | Yahoo Finance via `yfinance`                                       |
| Requested period                   | `2015-01-01` through the provider's latest available date          |
| Interval                           | `1d`                                                               |
| Tickers                            | `2330`, `2317`, `2454`, `2881`, `2882`, `0050`                     |
| Downloaded tickers                 | 6 / 6                                                              |
| Raw rows                           | 16,921                                                             |
| Rows after feature/label filtering | 16,828                                                             |
| `ohlcv.csv` SHA-256                | `2bd86eea9c5411d75b3f1920c55ea218c2fe06255d887391578770890b341c5f` |
| `tickers.csv` SHA-256              | `ad35f2e64297b83bdfef3dad4975cf1f22b3fffcd2e91ba4c72322c4ceec178d` |

The raw CSV and prediction CSVs remain outside git. The hashes identify the exact local snapshot
used for the committed aggregate results; they do not grant redistribution rights or protect against
provider corrections.

## Evaluation protocol

Each of the 39 folds uses the same leakage-aware temporal protocol:

```text
252 train dates -> 5 purge dates -> 63 calibration dates
-> 5 purge dates -> 63 test dates
```

The label is positive when the minimum close-to-close drawdown over the next five trading days is at
most `-0.05`. Features, Platt calibration, and the F1 alert threshold are fit without using test
outcomes. The three baseline runs share the exact `fold_id | ticker | date | risk_label` keys:
14,734 test rows, with SHA-256 `fab43a5c11bb55890ba33e2f486406239f9158619f306b09eb272538a9f1d536`.

## Results

Values are mean metrics across the 39 test folds. `calibrated` uses the calibration-fitted Platt
probability at the default 0.5 classification threshold. `tuned` uses an F1 threshold selected on
the calibration window.

| Model                                 | Calibrated AUC | Calibrated PR-AUC | Calibrated Brier | Calibrated ECE | Tuned F1 | Tuned recall | Tuned FDR |
| ------------------------------------- | -------------: | ----------------: | ---------------: | -------------: | -------: | -----------: | --------: |
| Logistic regression                   |         0.5177 |            0.1004 |           0.0710 |         0.0620 |   0.1264 |       0.3485 |    0.8997 |
| Random forest (100 trees)             |         0.5098 |            0.0924 |           0.0718 |         0.0635 |   0.0967 |       0.3655 |    0.9219 |
| HistGradientBoosting (100 iterations) |         0.5101 |            0.1016 |           0.0718 |         0.0636 |   0.1066 |       0.3850 |    0.9221 |

The positive-label rate across test folds was `0.0736`. The calibrated probability at 0.5 produced
no positive predictions in these folds; this is a useful warning about rare-event calibration, not
evidence that the model is safe or accurate. The tuned results retain high false-discovery rates and
must not be presented as actionable alerts.

## Limitations and rights boundary

- Six current TWSE symbols are a convenience sample, not the Taiwan universe. There is no
  point-in-time constituent history, delisting treatment, sector or liquidity coverage claim, and no
  TPEx listed/emerging symbol in this run.
- The run uses a current vendor-adjusted snapshot and therefore cannot answer a formal historical
  Taiwan index-membership question. The point-in-time membership framework is tracked separately in
  Issue #29.
- Yahoo Finance data is suitable here only for pipeline validation. TWSE/TPEx terms and any formal
  vendor license must be reviewed before redistribution, publication, or commercial use; see
  [`docs/data_and_model_licenses.md`](../../docs/data_and_model_licenses.md).
- The aggregate table has no multiple-comparison correction or external confidence interval. It does
  not establish cross-market transfer, deep-model parity, profitability, or investment advice.

## Reproduce

Run from the repository root. The output paths below use `/tmp` so provider data and prediction rows
are not added to git.

```bash
PYTHONPATH=src python -m scripts.download_tickers \
  --tickers 2330 2317 2454 2881 2882 0050 \
  --market auto \
  --start 2015-01-01 \
  --interval 1d \
  --dataset-name taiwan_pilot \
  --output-dir /tmp/tsi-taiwan-pilot/data

COMMON="--input /tmp/tsi-taiwan-pilot/data/ohlcv.csv --horizon 5 \
  --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 --calibration-method platt \
  --threshold-objective f1"

PYTHONPATH=src python -m scripts.train $COMMON --model-type logistic \
  --output /tmp/tsi-taiwan-pilot/logistic.json \
  --predictions-output /tmp/tsi-taiwan-pilot/logistic_predictions.csv
PYTHONPATH=src python -m scripts.train $COMMON --model-type random_forest \
  --tree-n-estimators 100 \
  --output /tmp/tsi-taiwan-pilot/random_forest.json \
  --predictions-output /tmp/tsi-taiwan-pilot/random_forest_predictions.csv
PYTHONPATH=src python -m scripts.train $COMMON --model-type hist_gradient_boosting \
  --tree-max-iter 100 \
  --output /tmp/tsi-taiwan-pilot/hist_gradient_boosting.json \
  --predictions-output /tmp/tsi-taiwan-pilot/hist_gradient_boosting_predictions.csv
```

The training CLI uses the shared trust decision threshold helper so a very low calibration-selected
alert threshold cannot make the watch threshold invalid.
