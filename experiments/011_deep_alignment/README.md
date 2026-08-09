# Experiment 011: Deep-Model Purged Alignment

## Status

This is a partial implementation of Issue #21. The deep trainer now records
the complete split protocol, and the fail-closed audit in
[`scripts/audit_deep_alignment.py`](../../scripts/audit_deep_alignment.py)
refuses a model comparison unless protocol metadata and every sample key match.

The current evidence is a one-fold GPU smoke run, not a full deep-model
benchmark. A full 39-fold run was not started because both configured GPUs were
occupied by existing `llama-server` processes, leaving less than 2.3 GiB free
per GPU. No CPU fallback is presented as the main result.

## Smoke evidence

The smoke run used the S&P 100 snapshot with the same `252 / 5 / 63 / 5 / 63`
purged schedule as the baseline. It used one epoch only to verify alignment,
with the trainer using CUDA and both GPUs through `DataParallel`.

| Field | Value |
| --- | --- |
| Fold | 0 |
| Test rows | 6,174 baseline / 6,174 deep |
| Key columns | `fold_id`, `ticker`, `date`, `risk_label` |
| Baseline-only keys | 0 |
| Deep-only keys | 0 |
| Shared sample-key SHA-256 | `71d0c2a59cf8b74a0fdab234756d0f14d0c60c55561e5cc3734cfad011b88c50` |
| CUDA device | `cuda`, 2 GPUs, DataParallel enabled |

This proves that the current sequence-window source-index alignment can match
the baseline test rows when the purge protocol is explicit. It does not prove
model quality or calibration; the one-epoch metrics are intentionally not
reported as research evidence.

## Reproduce a full comparison

Use a machine with enough free GPU memory. The raw/prediction artifacts below
are deliberately kept outside git:

```bash
PYTHONPATH=src python -m scripts.train_deep \
  --input data/raw/sp100/ohlcv.csv \
  --lookback 60 --horizon 5 \
  --train-size 252 --calibration-size 63 --test-size 63 \
  --step-size 63 --purge-size 5 \
  --epochs 20 --batch-size 256 --device cuda \
  --output /tmp/tsi-deep-aligned/summary.json \
  --predictions-output /tmp/tsi-deep-aligned/predictions.csv

PYTHONPATH=src python -m scripts.audit_deep_alignment \
  --baseline-summary experiments/008_model_family_comparison/runs/logistic/summary.json \
  --deep-summary /tmp/tsi-deep-aligned/summary.json \
  --output /tmp/tsi-deep-aligned/alignment.json \
  --report /tmp/tsi-deep-aligned/alignment.md
```

The audit is intentionally fail-closed: a different purge, calendar, fold
set, duplicate, or row key raises an error instead of producing an apparently
comparable metric table. After a full aligned run, the deep metrics can be
added to the existing model-family evidence in a follow-up PR.
