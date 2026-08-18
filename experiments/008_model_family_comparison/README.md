# Experiment 008: Purged Model-Family Comparison

This report compares baseline model families under the same leakage-aware protocol. It is
reproducible pilot evidence, not investment advice or a trading-performance claim.

## Protocol

- Horizon: `5` trading days
- Purge size: `5` dates
- Train/calibration/test: `252` / `63` / `63` dates
- Fold count: `39`
- Feature columns:
  `return_1d, return_5d, sma_5_gap, sma_10_gap, volatility_5d, volatility_10d, volume_ratio_5d`

## Sample-Key Audit

- Key columns: `fold_id, ticker, date, risk_label`
- Identical across models: **True**
- Shared row count: `244268`

| Model                  | Calibrated AUC | Calibrated PR-AUC | Calibrated Brier | Calibrated ECE | Tuned F1 | Tuned FDR |
| ---------------------- | -------------: | ----------------: | ---------------: | -------------: | -------: | --------: |
| logistic               |         0.6086 |            0.1540 |           0.0917 |         0.0546 |   0.2077 |    0.8531 |
| random_forest          |         0.5683 |            0.1347 |           0.0938 |         0.0587 |   0.1879 |    0.8749 |
| hist_gradient_boosting |         0.5942 |            0.1457 |           0.0929 |         0.0574 |   0.1982 |    0.8622 |

## Deep Model Boundary

The current temporal model uses sequence lookback windows and therefore does not emit the exact
row-level sample keys used by this baseline audit. It must be aligned separately before a
deep-vs-baseline claim.

## Limitations

- The benchmark uses the current-universe S&P 100 snapshot and inherits survivorship bias.
- Tree hyperparameters are fixed before the test windows; no test data are used for selection.
- Results are pilot evidence and do not establish trading performance or investment advice.

## Reproduce

The three summaries were generated from the same local S&P 100 snapshot:

```bash
python -m scripts.train --input data/raw/sp100/ohlcv.csv \
  --train-size 252 --calibration-size 63 --test-size 63 --step-size 63 \
  --purge-size 5 --horizon 5 --model-type logistic \
  --output experiments/008_model_family_comparison/runs/logistic/summary.json \
  --predictions-output experiments/008_model_family_comparison/runs/logistic/predictions.csv

# Repeat with --model-type random_forest and --model-type hist_gradient_boosting.
python -m scripts.compare_model_families \
  --runs experiments/008_model_family_comparison/runs/logistic/summary.json \
    experiments/008_model_family_comparison/runs/random_forest/summary.json \
    experiments/008_model_family_comparison/runs/hist_gradient_boosting/summary.json \
  --output experiments/008_model_family_comparison/comparison.json \
  --report experiments/008_model_family_comparison/README.md
```

The paired model comparisons use the same fold-level percentile bootstrap method as Experiment 007.
They are stored in `statistics/logistic_vs_random_forest_calibrated.json` and
`statistics/logistic_vs_hist_gradient_boosting_calibrated.json`.

```text
comparison.json SHA-256:
16574c8c36088ac8be803ff332aff7ab36c3278f450f6e1b564f8fad14262057

logistic_vs_random_forest_calibrated.json SHA-256:
da159fd240208425f504dfee63a7b3e94ec9ff7aee036a4cb0e0fbeb102d8224

logistic_vs_hist_gradient_boosting_calibrated.json SHA-256:
1e825fbb975c585b2d994ff3582a8e3bc7737fe778282cfbd13c89a3e47c45ab
```

The current temporal/deep model is deliberately not presented as an identical sample-key comparison:
sequence lookback removes or shifts row-level samples. Aligning its output to this protocol is a
separate research task.
