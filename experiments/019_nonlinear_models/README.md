# Experiment 019: Nonlinear Models and Training Windows

## Question

The served model is a Platt-calibrated logistic regression on the 12 `technical_range` features. Experiment 013 found logistic regression ahead of Random Forest, HistGradientBoosting, and a Temporal Transformer, but that comparison used the older 7 features, default tree settings (31-leaf trees), and a 252-date training window, which is small for a model that has to learn interactions.

The training window also differs between evaluation and serving. Experiments 007 to 018 train each fold on the latest 252 trading dates. Serving (`predict_latest_baseline` without `--train-size`) trains on every labeled date before the calibration window, which is about ten years for most tickers. The published walk-forward numbers therefore do not measure the served training scheme.

This experiment asks three questions on the current feature set:

1. Does a model that can use nonlinear effects and feature interactions rank drawdown risk better than the logistic baseline?
1. Does a longer training window help either model family?
1. Does the served expanding window perform like the 252-date window that earlier experiments measured?

It is pilot research evidence, not investment advice or a trading-performance claim.

## Protocol

- Same label, features, calibration, and threshold policies as serving and Experiment 017:
  - The label is a drawdown of -5% or worse within 5 trading days.
  - Features are `technical_range`.
  - Platt calibration on a 63-date calibration window, then a 63-date test window, with 5-date purges between windows.
  - Alert and watch thresholds use the serving policies (`alert_rate:0.05`, `alert_rate:0.2`), chosen on the calibration window only.
- Three training windows share every fold's calibration and test windows:
  - `252`: the last 252 dates of the fold's training window, the schedule of Experiments 007 to 018.
  - `756`: the fold's full training window, about three years. Folds are built with this window. Because `756 - 252 = 504` is a multiple of the 63-date step, these folds are the later folds of the Experiment 017 schedule.
  - `all`: every labeled row dated before the fold's training window, plus the training window, as serving does. Rows before the training window end more than a purge gap before calibration, so no label overlaps the calibration window.
- Four model families, with parameters fixed before any run:
  - `logistic`: the served `LogisticRiskModel` (median imputation, standardization, L2 logistic regression with balanced class weights).
  - `logistic_quadratic`: the same logistic regression on all degree-2 terms of the standardized features (12 linear, 12 squared, and 66 interaction terms), standardized again.
  - `hist_gradient_boosting`: shallow, slow boosting meant for noisy labels: learning rate 0.05, 200 iterations, at most 8 leaves per tree, at least 200 rows per leaf, L2 regularization 1.0, balanced class weights, and no early stopping.
  - `mlp`: a feed-forward network with hidden layers of 64 and 32 ReLU units and dropout 0.1, trained on the RTX 3090 with AdamW (learning rate 0.001, weight decay 0.0001), batch size 1,024, 20 epochs, and a positive-class loss weight of negatives over positives. Seeds and deterministic algorithms are fixed, and there is no early stopping.
- Ranking and calibration metrics are fold means. Alert precision and recall are pooled over test rows. Brier skill uses the 756-date window's event rate as the reference for every variant. Paired 95% intervals come from a percentile bootstrap over test folds (4,000 resamples, seed 42).
- Samples are the three from Experiment 017: S&P 100 (discovery), S&P 500 excluding S&P 100 (ticker holdout), and Taiwan large caps (market transfer check).

### Decision rule (set before the runs)

The serving reference is `logistic@all`. Serving changes only if a variant beats it on all of these:

- Mean AUC rises by at least 0.005, with a paired 95% interval above zero, on both S&P 100 and the S&P 500 holdout.
- The Taiwan AUC change is not negative.
- Mean ECE does not rise by more than 0.005, and pooled alert precision does not fall, on any sample.

A fixed window for `logistic` would be the smallest possible serving change: `predict_latest_baseline --train-size` already caps the training dates. It would not raise the minimum history, because serving trains on whatever earlier dates exist.

If `logistic@all` and `logistic@252` differ materially, the model card and earlier reports describe a different training scheme from the served one, and the model card has to say so.

## Result

The runs used plain `platt` calibration, before ADR 0007. A negative Platt slope reverses a fold's ranking, so the tables report both the uncalibrated AUC, which equals the AUC under the `platt_monotone` fallback that serving now uses, and the AUC as calibrated in the run. Each sample has 31 folds with no skipped folds; the MLP trained on CUDA.

### Ranking by variant

Each cell is uncalibrated AUC / calibrated AUC / folds with a reversed Platt fit.

| Variant                      | S&P 100             | S&P 500 holdout     | Taiwan              |
| ---------------------------- | ------------------- | ------------------- | ------------------- |
| `logistic@252`               | 0.6341 / 0.6341 / 0 | 0.6295 / 0.6295 / 0 | 0.7304 / 0.6979 / 2 |
| `logistic@756`               | 0.6490 / 0.6402 / 1 | 0.6383 / 0.6290 / 1 | 0.7389 / 0.7234 / 1 |
| `logistic@all`               | 0.6520 / 0.6417 / 1 | 0.6414 / 0.6310 / 1 | 0.7420 / 0.7268 / 1 |
| `logistic_quadratic@252`     | 0.6269 / 0.6193 / 1 | 0.6258 / 0.6258 / 0 | 0.7018 / 0.6870 / 1 |
| `logistic_quadratic@756`     | 0.6474 / 0.6474 / 0 | 0.6369 / 0.6277 / 1 | 0.7268 / 0.7268 / 0 |
| `logistic_quadratic@all`     | 0.6522 / 0.6522 / 0 | 0.6385 / 0.6286 / 1 | 0.7328 / 0.7328 / 0 |
| `hist_gradient_boosting@252` | 0.6256 / 0.6256 / 0 | 0.6265 / 0.6265 / 0 | 0.7186 / 0.7040 / 1 |
| `hist_gradient_boosting@756` | 0.6471 / 0.6366 / 1 | 0.6392 / 0.6292 / 1 | 0.7381 / 0.7381 / 0 |
| `hist_gradient_boosting@all` | 0.6505 / 0.6401 / 1 | 0.6420 / 0.6316 / 1 | 0.7442 / 0.7442 / 0 |
| `mlp@252`                    | 0.6336 / 0.6336 / 0 | 0.6211 / 0.6211 / 0 | 0.7332 / 0.7172 / 1 |
| `mlp@756`                    | 0.6489 / 0.6387 / 1 | 0.6344 / 0.6257 / 1 | 0.7423 / 0.7423 / 0 |
| `mlp@all`                    | 0.6508 / 0.6403 / 1 | 0.6379 / 0.6279 / 1 | 0.7468 / 0.7468 / 0 |

### Paired differences in uncalibrated AUC

Mean fold delta with its 95% interval.

| Comparison                                    | S&P 100                    | S&P 500 holdout            | Taiwan                     |
| --------------------------------------------- | -------------------------- | -------------------------- | -------------------------- |
| `logistic@756` − `logistic@252`               | +0.0149 [+0.0068, +0.0237] | +0.0088 [+0.0023, +0.0154] | +0.0086 [+0.0031, +0.0152] |
| `logistic@all` − `logistic@252`               | +0.0179 [+0.0094, +0.0276] | +0.0119 [+0.0050, +0.0197] | +0.0116 [+0.0054, +0.0196] |
| `logistic_quadratic@all` − `logistic@all`     | +0.0002 [−0.0034, +0.0046] | −0.0029 [−0.0057, −0.0005] | −0.0092 [−0.0237, +0.0025] |
| `hist_gradient_boosting@all` − `logistic@all` | −0.0015 [−0.0043, +0.0011] | +0.0006 [−0.0017, +0.0029] | +0.0023 [−0.0026, +0.0076] |
| `mlp@all` − `logistic@all`                    | −0.0012 [−0.0055, +0.0032] | −0.0035 [−0.0076, +0.0004] | +0.0048 [+0.0001, +0.0100] |

### Calibration and alerts at the served window

As calibrated in the run (`platt`), pooled over test rows.

| Variant                      | S&P 100 ECE / precision / recall | S&P 500 holdout        | Taiwan                 |
| ---------------------------- | -------------------------------- | ---------------------- | ---------------------- |
| `logistic@252`               | 0.0604 / 0.306 / 0.222           | 0.0551 / 0.330 / 0.208 | 0.0565 / 0.267 / 0.170 |
| `logistic@all`               | 0.0587 / 0.296 / 0.226           | 0.0543 / 0.328 / 0.214 | 0.0526 / 0.284 / 0.190 |
| `logistic_quadratic@all`     | 0.0587 / 0.297 / 0.206           | 0.0562 / 0.321 / 0.200 | 0.0512 / 0.285 / 0.172 |
| `hist_gradient_boosting@all` | 0.0583 / 0.293 / 0.219           | 0.0545 / 0.325 / 0.213 | 0.0498 / 0.297 / 0.180 |
| `mlp@all`                    | 0.0580 / 0.292 / 0.214           | 0.0552 / 0.316 / 0.202 | 0.0503 / 0.301 / 0.191 |

On the S&P 500 holdout the MLP's alert precision is 0.018 lower than logistic's (interval −0.0275 to −0.0094) and its recall 0.009 lower.

## Findings

- **Nonlinear models do not beat the logistic baseline.** At the served window, no family gains on both US samples. Quadratic logistic is worse on the S&P 500 holdout, gradient boosting is within ±0.0023 everywhere, and the MLP gains only in Taiwan (+0.0048, interval barely above zero) while losing alert precision on the S&P 500 holdout. The apparent +0.0105 calibrated-AUC gain of `logistic_quadratic@all` on S&P 100 came from a single fold (test start 2020-05-19) where the logistic model's Platt fit reversed and the quadratic model's did not; uncalibrated, the two differ by 0.0002.
- **Longer training windows help every family.** For logistic, the served expanding window beats 252 dates by 0.018 (S&P 100), 0.012 (S&P 500 holdout), and 0.012 (Taiwan), all with intervals above zero, and it also lowers ECE in Taiwan. Nonlinear models gain more from longer windows than logistic does, but not enough to overtake it.
- **Earlier experiments understate the served model.** Experiments 007 to 018 trained on 252 dates. The served expanding window ranks about 0.012 to 0.018 AUC better on the same folds, so the walk-forward numbers in the model card are conservative for ranking.
- **Calibration reversals distort comparisons.** Every sample had folds where Platt reversed the ranking, including two Taiwan folds for `logistic@252`, which lowered its calibrated AUC from 0.7304 to 0.6979. Experiment 020 and ADR 0007 follow up on this.

## Decision for serving

- Serving keeps the logistic baseline. No variant met the decision rule: none raised AUC by 0.005 with an interval above zero on both US samples.
- Serving keeps its expanding training window. It was already the best window tested.
- The Taiwan MLP gain is recorded but not acted on. It needs confirmation on the Taiwan holdout and a reason the same model loses on the S&P 500 holdout.

## Reproduce

```bash
python -m scripts.evaluate_model_variants --input data/raw/sp100/ohlcv.csv \
  --output-dir experiments/019_nonlinear_models/runs/sp100_model_variants
python -m scripts.evaluate_model_variants --input data/raw/sp500_ex_sp100/ohlcv.csv \
  --output-dir experiments/019_nonlinear_models/runs/sp500_ex_sp100_model_variants
python -m scripts.evaluate_model_variants --input data/raw/tw_large/ohlcv.csv \
  --output-dir experiments/019_nonlinear_models/runs/tw_large_model_variants
```

The runs took about 29 minutes (S&P 100), 64 minutes (S&P 500 holdout), and 22 minutes (Taiwan) on a 20-thread CPU and one RTX 3090, sharing the machine with other jobs. `--reuse-per-fold` rebuilds `summary.json` from a saved `per_fold.csv` without refitting; the committed summaries were rebuilt that way to add paired uncalibrated-AUC intervals, and every other field matched the fitted run exactly.

## Limitations

- Each nonlinear family was tested with one fixed configuration chosen before the runs. The result does not rule out every tree or neural architecture.
- The runs calibrated with `platt`. Alert precision and recall under `platt_monotone` differ only in folds with a reversed fit, which these tables count.
- GPU training is deterministic with fixed seeds on this machine, but bit-identical results across GPU models or driver versions are not guaranteed.
- Current-constituent samples carry survivorship bias (Issue #29).
