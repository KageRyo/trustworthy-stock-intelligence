# Experiment 011: Deep-Model Purged Alignment

## Result

This full 39-fold CUDA run completes the deep-model comparison portion of Issue
#21 for the current S&P 100 pilot. It is reproducible research evidence, not
investment advice or a trading-performance claim.

The fail-closed audit matched the protocol, raw-input SHA-256, membership
state, all folds, and every `fold_id | ticker | date | risk_label` sample key.
It compared 241,634 shared test rows. The private prediction and per-fold audit
artifacts are not committed; the public-safe run details are in
[`run_manifest.json`](run_manifest.json).

| Metric | Logistic regression | Temporal Transformer |
| --- | ---: | ---: |
| Calibrated ROC-AUC | 0.6079 | 0.5867 |
| Calibrated PR-AUC | 0.1538 | 0.1345 |
| Calibrated Brier | 0.0920 | 0.0945 |
| Calibrated ECE | 0.0548 | 0.0616 |
| Tuned precision | 0.1476 | 0.1364 |
| Tuned recall | 0.4317 | 0.5056 |
| Tuned F1 | 0.2072 | 0.1881 |
| Tuned false-positive rate | 0.3077 | 0.4135 |
| Tuned false-discovery rate | 0.8524 | 0.8636 |
| Tuned alert coverage | 0.3204 | 0.4197 |

On this pilot, the Transformer recovers more positives at its tuned threshold,
but it performs worse than logistic regression on the calibrated discrimination,
calibration, F1, false-positive-rate, and false-discovery-rate measures. Both
models have high false-discovery rates. The result is therefore negative
evidence for adopting this Transformer configuration as the preferred warning
model, not an investment-usefulness claim.

## Protocol and Integrity

- Input: 101-symbol current S&P 100 Yahoo Finance/yfinance snapshot from
  2015-01-01; OHLCV SHA-256
  `bb6e994d062d57d18eaedd80e38ea672917cd1933573081d89231c8a51769be2`.
- Purged walk-forward: `252 / 5 / 63 / 5 / 63`, 5-trading-day drawdown label,
  39 contiguous folds (`0`–`38`).
- Features: `return_1d`, `return_5d`, `sma_5_gap`, `sma_10_gap`,
  `volatility_5d`, `volatility_10d`, and `volume_ratio_5d`.
- Sequence support: the 60-day lookback is applied inside every baseline fold,
  so newly listed symbols cannot appear in a baseline test row that the deep
  model cannot represent.
- Deep training: CUDA, one RTX 4090, 20 epochs, batch size 128; no CPU
  fallback. One GPU was used because the other card lacked free memory.
- Shared-row SHA-256 digest:
  `75cd49779a343bdf84f2b45d716418421fcabc1d42f0a9c69ad3766a44d6ee70`.

## Reproduce

The raw snapshot and prediction artifacts remain private. With the same local
OHLCV file, run the two models and then the audit:

```bash
PYTHONPATH=src python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --model-type logistic --horizon 5 \
  --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 --max-folds 39 --sequence-lookback 60 \
  --calibration-method platt \
  --output /tmp/tsi-baseline-aligned/summary.json \
  --predictions-output /tmp/tsi-baseline-aligned/predictions.csv

CUDA_VISIBLE_DEVICES=1 PYTHONPATH=src python -m scripts.train_deep \
  --input data/raw/sp100/ohlcv.csv \
  --lookback 60 --horizon 5 \
  --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 --max-folds 39 \
  --epochs 20 --batch-size 128 --device cuda --disable-multi-gpu \
  --output /tmp/tsi-deep-aligned/summary.json \
  --predictions-output /tmp/tsi-deep-aligned/predictions.csv

PYTHONPATH=src python -m scripts.audit_deep_alignment \
  --baseline-summary /tmp/tsi-baseline-aligned/summary.json \
  --deep-summary /tmp/tsi-deep-aligned/summary.json \
  --expected-fold-count 39 \
  --output /tmp/tsi-deep-aligned/alignment.json \
  --report /tmp/tsi-deep-aligned/alignment.md
```

## Limitations

- The current S&P 100 constituent list has survivorship bias. It is not a
  point-in-time universe and does not close Issue #29.
- The pilot uses Yahoo Finance/yfinance input. It does not establish data
  rights for redistribution or formal research claims.
- This comparison evaluates one fixed Transformer configuration. It does not
  prove that every deep architecture is ineffective.
- High false-discovery rates make both tuned warning policies unsuitable for a
  trustworthy production claim without further policy and validation work.
