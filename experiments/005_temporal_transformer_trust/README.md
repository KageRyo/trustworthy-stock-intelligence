# Temporal Transformer Trust Experiments

This experiment track evaluates the Python DL closed loop:

```text
OHLCV
-> technical features
-> 60-day sequence dataset
-> Temporal Transformer
-> calibration
-> uncertainty
-> trust score
-> warning decision
-> trust-aware evaluation
```

## Current Diagnostic Focus

The first GPU smoke run showed an overly broad watch decision:

```text
row_count = 6174
watch_count = 6156
coverage = 0.9971
```

This means the model and trust layer run end to end, but the decision
thresholds need tuning before dashboard work.

## Baseline Run

```bash
python -m scripts.train_deep \
  --input data/raw/sp100/ohlcv.csv \
  --lookback 60 \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --epochs 20 \
  --batch-size 256 \
  --watch-threshold-ratio 0.8 \
  --min-watch-threshold 0.05 \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/summary.json \
  --predictions-output experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/predictions.csv
```

## Warning Evaluation

```bash
python -m scripts.evaluate_warnings \
  --input experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/predictions.csv \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/warning_eval.json
```

## Threshold Sweep

```bash
python -m scripts.sweep_warning_thresholds \
  --input experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/predictions.csv \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/threshold_sweep.csv
```

Compare sweep rows by:

```text
alert_rate
watch_rate
abstain_rate
coverage
selective_risk
alert_precision
alert_false_alarm_rate
```

The immediate goal is to avoid watch rates near 100% and find a useful
coverage versus alert-quality tradeoff.
