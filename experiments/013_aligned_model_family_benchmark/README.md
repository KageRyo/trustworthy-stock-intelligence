# Experiment 013: Fully Aligned Model-Family Benchmark

## Result

This experiment completes the current-universe pilot comparison requested by Issue #21. Logistic
regression, Random Forest, HistGradientBoosting, and the Temporal Transformer were evaluated on
exactly the same 39 purged walk-forward folds and 241,634 test samples. It is pilot research
evidence, not investment advice or a trading-performance claim.

| Model                                 | Cal. AUC | Cal. PR-AUC | Cal. Brier | Cal. ECE | Tuned precision | Tuned recall | Tuned F1 | Tuned FPR | Tuned FDR | Alert coverage |
| ------------------------------------- | -------: | ----------: | ---------: | -------: | --------------: | -----------: | -------: | --------: | --------: | -------------: |
| Logistic regression                   |   0.6079 |      0.1538 |     0.0920 |   0.0548 |          0.1476 |       0.4317 |   0.2072 |    0.3077 |    0.8524 |         0.3204 |
| Random Forest (100 trees)             |   0.5653 |      0.1327 |     0.0941 |   0.0588 |          0.1241 |       0.4895 |   0.1849 |    0.4128 |    0.8759 |         0.4208 |
| HistGradientBoosting (100 iterations) |   0.5943 |      0.1462 |     0.0933 |   0.0580 |          0.1376 |       0.4707 |   0.1969 |    0.3607 |    0.8624 |         0.3722 |
| Temporal Transformer                  |   0.5867 |      0.1345 |     0.0945 |   0.0616 |          0.1364 |       0.5056 |   0.1881 |    0.4135 |    0.8636 |         0.4197 |

Logistic regression has the strongest calibrated discrimination, calibration, tuned F1,
false-positive rate, and false-discovery rate in this fixed pilot. The Transformer has the highest
tuned recall, but at a materially higher alert coverage and false-positive rate. All four tuned
policies retain a high false-discovery rate, so none is suitable for a trustworthy
production-warning claim without further policy work and external validation.

## Shared Protocol and Audit

- Current 101-symbol S&P 100 Yahoo Finance/yfinance snapshot, 2015-01-01 onward; OHLCV SHA-256
  `bb6e994d062d57d18eaedd80e38ea672917cd1933573081d89231c8a51769be2`.
- Same features, 5-trading-day drawdown label, `252 / 5 / 63 / 5 / 63` purged walk-forward protocol,
  and contiguous folds `0`–`38`.
- The 60-day sequence eligibility rule is applied inside every baseline fold; the baseline cannot
  evaluate an early newly-listed row that the sequence model cannot represent.
- All four model outputs have 241,634 shared test rows and the same shared-row SHA-256 digest:
  `75cd49779a343bdf84f2b45d716418421fcabc1d42f0a9c69ad3766a44d6ee70`.
- Platt calibration and the F1 alert threshold are fit on each fold's calibration window only. Test
  rows are never used for fitting or threshold selection.
- The Transformer used one CUDA RTX 4090 for 20 epochs at batch size 128; no CPU fallback was used.
  Random Forest and HistGradientBoosting use their fixed, documented 100-tree / 100-iteration
  configurations.

Private prediction and per-fold audit outputs are reproducible with the commands in
[`../011_deep_alignment/README.md`](../011_deep_alignment/README.md) and remain outside Git.
Aggregate evidence and exact reproducibility hashes are recorded in
[`run_manifest.json`](run_manifest.json).

## Limitations

- The S&P 100 constituent list is current, not point-in-time, so the pilot has survivorship bias.
  Issue #29 remains open pending a legally usable historical membership source and a paired re-run.
- Yahoo Finance/yfinance is a pilot provider; raw data and predictions are not redistributed in this
  repository.
- This tests fixed configurations only. It does not prove a general ranking of all tree or deep
  architectures.
- High FDR is a safety limitation. The results must not be used as an automated trading policy or
  presented as investment guidance.
