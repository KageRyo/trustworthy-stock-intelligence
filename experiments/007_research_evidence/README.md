# Experiment 007: Purged Calibration Evidence

## Status

Reproducible pilot evidence. This is not formal external validation and is not
investment advice.

This experiment replaces the earlier unpurged preliminary table in Experiment
002 as the current calibration evidence. The historical table remains useful
for provenance, but its fold boundaries did not exclude the label horizon.

## Research Question

Does Platt calibration improve the reliability of logistic-regression
drawdown-risk probabilities when every train/calibration/test boundary is
purged by the five-day label horizon?

## Dataset And Label

```text
Provider: Yahoo Finance via yfinance
Snapshot downloaded_at_utc: 2026-05-08T02:50:28.018207+00:00
Universe: 101 S&P 100 tickers from a 2026 universe list
Raw rows: 283,289
Rows after feature/label filtering: 281,774
Test predictions: 244,268
Test dates: 2016-05-03 through 2026-02-09
Feature interval: 1d
Label horizon: 5 trading days
Positive label: min(P[t+1:t+5] / P[t] - 1) <= -0.05
```

The snapshot has survivorship bias because current-universe membership was used
for historical evaluation. It is a pipeline pilot, not a point-in-time index
constituent study.

Dataset fingerprints:

```text
ohlcv.csv SHA-256:
6b1357c8414888cb0a467eb717df0261ff69bd3b8e9b0244ff115be820395ba6

tickers.csv SHA-256:
3023bcc40e666c0151ac3aeb895aae9f8d1f04f9da6db01977a1f8204ef2d890
```

## Temporal Protocol

Each of 39 sliding folds uses:

```text
252 train dates
-> 5 excluded/purged dates
-> 63 calibration dates
-> 5 excluded/purged dates
-> 63 test dates
```

The model and feature scaling are fit on train only. Platt calibration and the
F1 alert threshold are fit on calibration only. Test labels and probabilities
are never used for fitting or threshold selection.

The purge is a label-overlap guard: a label at the end of an earlier window
uses the following five trading days, so those dates must not be part of the
next model-selection window.

Each row also stores its actual `label_end_date`. The splitter removes a row if
that end date reaches the following window, which protects mixed-market
calendars where five global dates may not equal five bars for every ticker. No
additional overlapping rows were found in this single-market S&P 100 run.

## Results

Values are mean ± sample standard deviation across 39 test folds.
`false_alarm_rate` in stored artifacts is retained for compatibility and means
false-positive rate, `FP / (FP + TN)`. False discovery rate is reported
separately as `FP / (TP + FP)`.

| Variant | AUC | Brier | ECE | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Training-window event-rate prior | 0.5000 ± 0.0000 | 0.0935 ± 0.0592 | 0.0655 ± 0.0545 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| Raw logistic | 0.6153 ± 0.0418 | 0.2318 ± 0.0469 | 0.3736 ± 0.0427 | 0.1432 ± 0.0787 | 0.4502 ± 0.1919 | 0.2101 ± 0.1057 |
| Logistic + Platt at 0.5 | 0.6086 ± 0.0573 | 0.0917 ± 0.0591 | 0.0546 ± 0.0609 | 0.0622 ± 0.1782 | 0.0015 ± 0.0048 | 0.0030 ± 0.0093 |
| Logistic + Platt, calibration-tuned threshold | 0.6086 ± 0.0573 | 0.0917 ± 0.0591 | 0.0546 ± 0.0609 | 0.1469 ± 0.0798 | 0.4344 ± 0.2123 | 0.2077 ± 0.1049 |

Mean tuned threshold: `0.1055 ± 0.0607`.

### AUC Invariance Audit

The raw-versus-Platt AUC difference has been audited without changing the
original artifacts or reported values. All 244,268 paired predictions use
identical `fold_id | ticker | date | risk_label` sample keys.

In 38/39 folds, the reconstructed Platt coefficient is positive and raw versus
calibrated AUC is identical within `1e-12`. Fold 8 is the exception: its
coefficient is `-0.798373`, so it reverses ranking exactly:

```text
raw AUC:         0.630840
calibrated AUC:  0.369160 = 1 - raw AUC
fold AUC delta: -0.261680
mean contribution across 39 folds: -0.0067097
```

That one fold fully explains the main table's mean AUC change from `0.615325`
to `0.608615`. It is distinct from the COVID calibration failure in fold 15.
Fold 8 used a 2018-01-25 through 2018-04-25 calibration window and a 2018-05-03
through 2018-08-01 test window.

The main table is unweighted mean-fold AUC. Pooled AUC is a different statistic:
fold-specific coefficients and intercepts can change cross-fold ranking even
when every mapping is increasing. Definitions, per-fold sample hashes,
coefficients, ranking diagnostics, executable invariants, and reproduction
instructions are in [`audit/README.md`](audit/README.md).

### Calibration Effectiveness

- Versus raw logistic probabilities, Brier and ECE improved in 38/39 folds.
- Mean paired fold delta was `-0.1401` Brier and `-0.3190` ECE.
- Across pooled ticker breakdowns, both metrics improved for 101/101 tickers.
- Across yearly breakdowns, both metrics improved for 11/11 represented years.
- Versus the no-feature prior, improvements were much smaller: mean Brier
  `0.0935 -> 0.0917` and ECE `0.0655 -> 0.0546`.

Fold 15 is the retained failure case. Its calibration window had a 3.8% event
rate, while its 2020-02-04 through 2020-05-04 test window had a 40.3% event
rate. Platt calibration worsened Brier by `0.0020` and ECE by `0.0241`. This is
evidence that calibration itself drifts under abrupt regime changes.

### Decision-Policy Interpretation

Calibration improved probability reliability but did not make `0.5` a useful
alert threshold. The fixed threshold had mean recall `0.0015`. Selecting an F1
threshold only on the calibration window recovered mean recall `0.4344` and F1
`0.2077`, with mean false-positive rate `0.3088` and false-discovery rate
`0.8531`.

The evidence supports the narrow claim that Platt scaling usually repairs the
raw logistic probabilities in this pilot. It does not support a claim of high
warning precision, stable calibration under every regime, or profitable use.

## Reproduce

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --horizon 5 \
  --purge-size 5 \
  --calibration-method platt \
  --output experiments/007_research_evidence/runs/sp100_logistic_platt_purged/summary.json \
  --predictions-output experiments/007_research_evidence/runs/sp100_logistic_platt_purged/predictions.csv

python -m scripts.compare_calibration \
  --input experiments/007_research_evidence/runs/sp100_logistic_platt_purged/predictions.csv \
  --group-cols fold_id ticker \
  --period year \
  --output experiments/007_research_evidence/runs/sp100_logistic_platt_purged/calibration_comparison.json
```

The prediction CSV is gitignored because it contains provider-derived rows.
Committed aggregate artifacts:

```text
summary.json SHA-256:
265f5a9d10d36cde4c19fc3350d89fd89779be811b79e76286a615d6bc1ad65e

calibration_comparison.json SHA-256:
bc7fb825bd539084612f28371a7a9990f830cfabd5f2e45346742a23d3b68a0e
```

Execution environment:

```text
Date: 2026-07-29
Base git commit: b09b9e70fee133869452455b64690c3155f7342d
Working tree: includes the purge/evidence changes described in this experiment
Python: 3.11.15
numpy: 2.4.4
pandas: 3.0.2
scikit-learn: 1.8.0
```

## Evidence Gaps

- No purged random-forest or gradient-boosting comparison yet.
- No Taiwan, cross-market, sector, liquidity, or market-cap evaluation.
- No point-in-time universe membership or delisting treatment.
- No confidence intervals or multiple-comparison corrections.
- ECE is equal-width 10-bin ECE and remains bin-sensitive.
- No provider re-download diff or correction-latency study; hashes only identify
  the exact local snapshot.
- No transaction-cost analysis. It is not relevant to the current probability
  and warning-quality claim, but it is required before any trading-strategy
  claim.
- No externally reviewed or licensed formal-research dataset.
