# Experiment 014: Taiwan TWSE and TPEx Purged Pilot

## Result

This current-universe research pilot evaluates three TWSE and three TPEx-listed
companies on the same 39 purged walk-forward folds. It advances Issue #23, but
does not establish all-Taiwan, emerging-market, point-in-time, or investment
performance coverage.

| Model | Cal. AUC | Cal. PR-AUC | Cal. Brier | Cal. ECE | Tuned precision | Tuned recall | Tuned F1 | Tuned FPR | Tuned FDR | Alert coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic regression | 0.5560 | 0.1904 | 0.1236 | 0.0895 | 0.1640 | 0.4804 | 0.2074 | 0.4225 | 0.8360 | 0.4305 |
| Random Forest (100 trees) | 0.5283 | 0.1624 | 0.1237 | 0.0864 | 0.1500 | 0.5558 | 0.2024 | 0.5208 | 0.8500 | 0.5249 |
| HistGradientBoosting (100 iterations) | 0.5041 | 0.1601 | 0.1238 | 0.0861 | 0.1447 | 0.5086 | 0.2010 | 0.4933 | 0.8553 | 0.4982 |

Logistic regression is the strongest fixed configuration in this pilot, but
its calibrated AUC is only modestly above random and every tuned policy has a
high false-discovery rate. These models are not production-ready warning
policies and must not be treated as investment advice.

## Data and Protocol

- The dated official current-company catalogue contains 1,093 TWSE, 890 TPEx,
  and 360 emerging companies. Its catalogue SHA-256 is
  `5084ffde87af1855635dbd2c531993a08c74ac512c50335a7b342b0a7111d8c3`.
- The stratified listed sample is `2330`, `2317`, `2454` (TWSE) and `3260`,
  `6147`, `8069` (TPEx). Each yielded 2,820 daily bars from 2015-01-01 onward;
  the merged input has 16,920 rows and SHA-256
  `f7dc98cf2fb9adaac1dd0921baaaaa2d6a713dd92a9cda2043a8ddfe94854b29`.
- Each model uses the seven existing technical features, a five-trading-day
  drawdown label at `-0.05`, and the `252 / 5 / 63 / 5 / 63` purged schedule.
  Platt calibration and each F1 threshold use the calibration window only.
- The model-family audit confirms identical `fold_id | ticker | date |
  risk_label` rows across all three models: 14,740 rows, with shared-row
  SHA-256
  `92c1a3f6dbede80270811f83bcd309c437e3a0baaf0c8f6239ec8040b2c8672d`.
- All 39 folds report zero label-overlap removals after their explicit purge
  windows. The first test window is 2016-05-23 to 2016-08-19; the last is
  2026-03-30 to 2026-06-30.

Raw OHLCV, prediction rows, current-company CSV, and private audit output stay
outside Git. Aggregate fields and exact reproducibility fingerprints are in
[`run_manifest.json`](run_manifest.json).

## Emerging-Market Boundary

The official current catalogue includes emerging companies and the downloader's
monthly TPEx emerging fallback was verified on a short probe. Long-horizon
fetches for the candidate emerging sample did not complete reliably in this
environment because DNS/endpoint requests stalled before any artifact could be
written. Emerging symbols are therefore excluded from the benchmark, not
silently represented by TWSE data. A resumed, rate-aware official download or
a licensed historical vendor is required before claiming emerging coverage.

## Limitations

- This is a current-company sample, not point-in-time membership. It has
  survivorship, delisting, suspension, sector, and liquidity-coverage limits.
- It covers only six selected listed companies; it does not represent all TWSE,
  all TPEx, or any emerging-stock historical performance.
- Yahoo Finance/yfinance is used only for pilot inputs. Recheck the TWSE/TPEx
  rights boundary before redistribution, publication, or commercial use.
- No external validation, confidence intervals, transfer claim, or deep-model
  comparison is made here.

## Reproduce

All provider-derived output below belongs outside Git:

```bash
PYTHONPATH=src python -m scripts.download_tickers \
  --tickers 2330 2317 2454 --market twse --start 2015-01-01 \
  --dataset-name taiwan_stratified_twse --output-dir /secure/tsi/twse
PYTHONPATH=src python -m scripts.download_tickers \
  --tickers 3260 6147 8069 --market tpex --start 2015-01-01 \
  --dataset-name taiwan_stratified_tpex --output-dir /secure/tsi/tpex
PYTHONPATH=src python -m scripts.combine_download_artifacts \
  --input-dir /secure/tsi/twse --input-dir /secure/tsi/tpex \
  --output-dir /secure/tsi/listed-tpex \
  --dataset-name taiwan_listed_tpex_stratified_current_pilot
PYTHONPATH=src python -m scripts.train \
  --input /secure/tsi/listed-tpex/ohlcv.csv --model-type logistic \
  --horizon 5 --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 --max-folds 39 \
  --calibration-method platt --threshold-objective f1 \
  --output /secure/tsi/logistic/summary.json \
  --predictions-output /secure/tsi/logistic/predictions.csv
```
