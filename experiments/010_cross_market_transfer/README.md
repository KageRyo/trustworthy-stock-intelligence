# Experiment 010: Within- and Cross-Market Transfer

## Status

This is a reproducible logistic-baseline transfer pilot for Issue #24. It completes the evaluator
and records US/Taiwan within-market and cross-market results, but it does not close the issue's
formal-universe or deep-model gaps. It is not investment advice or a trading-performance claim.

## Design

The evaluator in
[`scripts/evaluate_cross_market_transfer.py`](../../scripts/evaluate_cross_market_transfer.py) uses
the same feature and label definitions for both markets:

- Features: `return_1d`, `return_5d`, `sma_5_gap`, `sma_10_gap`, `volatility_5d`, `volatility_10d`,
  `volume_ratio_5d`
- Label: minimum close-to-close drawdown over the next five trading days at or below `-0.05`
- Fold protocol: 252 train dates, 5 purge dates, 63 source-calibration dates, 5 purge dates, and 63
  target-test dates
- Calibration: Platt scaling fit only on the source calibration window
- Alert threshold: F1-selected on source calibration only
- Transfer metric: target-test AUC, PR-AUC, Brier, ECE, and tuned alert metrics

For a within-market run, source and target are the same market. For a cross-market run, the source
model and calibration remain unchanged while the target is evaluated only on the source fold's
test-date window. Different exchange holidays are therefore visible as coverage differences rather
than being silently mixed into a random split.

## Snapshots

No raw data or prediction CSV is committed. The manifest records the exact input fingerprints used
for this run.

| Market | Dataset                            | Raw rows | Tickers | OHLCV SHA-256                                                      |
| ------ | ---------------------------------- | -------: | ------: | ------------------------------------------------------------------ |
| US     | S&P 100 current-universe pilot     |  283,289 |     101 | `6b1357c8414888cb0a467eb717df0261ff69bd3b8e9b0244ff115be820395ba6` |
| Taiwan | six-TWSE pilot from Experiment 009 |   16,921 |       6 | `2bd86eea9c5411d75b3f1920c55ea218c2fe06255d887391578770890b341c5f` |

The US `tickers.csv` fingerprint is
`3023bcc40e666c0151ac3aeb895aae9f8d1f04f9da6db01977a1f8204ef2d890`; the Taiwan `tickers.csv`
fingerprint is `ad35f2e64297b83bdfef3dad4975cf1f22b3fffcd2e91ba4c72322c4ceec178d`. Both are Yahoo
Finance/yfinance pilot snapshots, not licensed formal research datasets.

## Results

Metrics are means across 39 evaluated folds. `Target calibrated` uses the source-fitted Platt
calibrator; `Tuned F1/FDR` uses the source-calibration F1 threshold. `Δ Brier` and `Δ ECE` are
target calibrated metric minus the source calibration metric, so positive values indicate
degradation. The within-market rows include temporal degradation; cross-market rows include temporal
and market-transfer effects.

| Evaluation               | Target calibrated AUC | Target PR-AUC | Target Brier | Target ECE | Tuned F1 | Tuned FDR | Δ Brier |   Δ ECE |
| ------------------------ | --------------------: | ------------: | -----------: | ---------: | -------: | --------: | ------: | ------: |
| US → US (within)         |                0.6086 |        0.1540 |       0.0917 |     0.0546 |   0.2077 |    0.8531 | +0.0079 | +0.0499 |
| Taiwan → Taiwan (within) |                0.5177 |        0.1004 |       0.0710 |     0.0620 |   0.1264 |    0.8997 | +0.0090 | +0.0571 |
| US → Taiwan              |                0.6397 |        0.1288 |       0.0676 |     0.0655 |   0.1462 |    0.8988 | -0.0162 | +0.0608 |
| Taiwan → US              |                0.5557 |        0.1395 |       0.0961 |     0.0582 |   0.1799 |    0.8621 | +0.0341 | +0.0534 |

The transfer result is not a claim that a US-trained model generalizes safely to Taiwan: both
cross-market directions retain high false-discovery rates and show ECE degradation. A lower Brier
score in US → Taiwan does not override the calibration and coverage limitations.

## Reproduce

First reproduce the Taiwan snapshot from
[`experiments/009_taiwan_pilot/README.md`](../009_taiwan_pilot/README.md). The US snapshot is the
existing local `data/raw/sp100/ohlcv.csv`. The evaluator writes raw prediction rows only to `/tmp`
in this example:

```bash
US_INPUT=data/raw/sp100/ohlcv.csv
TW_INPUT=/tmp/tsi-taiwan-pilot/data/ohlcv.csv
COMMON="--horizon 5 --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 --calibration-method platt \
  --threshold-objective f1"

PYTHONPATH=src python -m scripts.evaluate_cross_market_transfer \
  --source-input "$US_INPUT" --target-input "$US_INPUT" \
  --source-market us --target-market us \
  --source-name sp100 --target-name sp100 $COMMON \
  --output /tmp/tsi-cross-market/us_within.json \
  --predictions-output /tmp/tsi-cross-market/us_within_predictions.csv

PYTHONPATH=src python -m scripts.evaluate_cross_market_transfer \
  --source-input "$TW_INPUT" --target-input "$TW_INPUT" \
  --source-market taiwan --target-market taiwan \
  --source-name taiwan_pilot --target-name taiwan_pilot $COMMON \
  --output /tmp/tsi-cross-market/taiwan_within.json \
  --predictions-output /tmp/tsi-cross-market/taiwan_within_predictions.csv

# Repeat with US -> Taiwan and Taiwan -> US by swapping source/target paths
# and market labels.
```

The committed [`run_manifest.json`](run_manifest.json) contains the aggregate results, source/target
fingerprints, and the exact protocol. Prediction CSVs are provider-derived and remain gitignored.

## Limitations and remaining acceptance work

- Taiwan is the six-symbol TWSE pilot from Experiment 009, not a full TWSE, TPEx listed, or TPEx
  emerging universe.
- The S&P 100 is a current-universe snapshot and inherits survivorship bias; the point-in-time
  membership framework is tracked in #29 / PR #36.
- The two markets have different holidays, trading hours, liquidity, and symbol coverage. This
  evaluator harmonizes model columns and reports the date-window coverage, but does not make the
  observations exchange-equivalent.
- No formal licensed dataset, sector/liquidity stratification, confidence interval, deep-model
  alignment, or economic-cost analysis is included.
- Review external-data rights before publication or commercial use; see
  [`docs/data_and_model_licenses.md`](../../docs/data_and_model_licenses.md).
