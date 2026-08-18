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

This means the model and trust layer run end to end, but the decision thresholds need tuning before
dashboard work.

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
  --trust-score-method subtractive \
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

The immediate goal is to avoid watch rates near 100% and find a useful coverage versus alert-quality
tradeoff.

## Prediction Diagnostics

```bash
python -m scripts.diagnose_predictions \
  --input experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/predictions.csv \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/diagnostics.json
```

Use this when `alert_count` or `trust_score` distributions look suspicious. The first full run
showed that subtractive entropy trust scoring can collapse scores to zero, so multiplicative trust
scoring should be compared before dashboard work.

## Report Generation

```bash
python -m scripts.report_trust_experiment \
  --summary experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/summary.json \
  --warning-eval experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/warning_eval.json \
  --threshold-sweep experiments/005_temporal_transformer_trust/runs/platt_entropy_t05/threshold_sweep.csv \
  --output experiments/005_temporal_transformer_trust/report.md
```

## V1 Comparison Report

Compare the subtractive and multiplicative trust-score runs:

```bash
python -m scripts.compare_experiments \
  --runs \
    experiments/005_temporal_transformer_trust/runs/platt_entropy_wr08 \
    experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08 \
  --output experiments/005_temporal_transformer_trust/comparison.md
```

Export reliability bins for dashboard calibration diagnostics:

```bash
python -m scripts.export_reliability_bins \
  --input experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08/predictions.csv \
  --output experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08/reliability_bins.csv
```

Current v1 findings should be framed as a trust-aware conservative risk alerting demo. The
multiplicative trust-score run emits a small alert set (`alert_rate` about 2.5%) with low recall,
while the subtractive trust-score run is too conservative and emits no alerts under this policy.
This supports the serving and dashboard demo, but it should not be described as accurate stock
drawdown prediction or trading advice.

Known limitations:

- Alert recall is low, so the system misses many positive risk events.
- Watch coverage is broad and should be interpreted as monitoring, not a strong prediction.
- Calibration and warning policies need more folds, regimes, and baseline comparisons before
  stronger claims.
- The current dashboard and Go API serve generated artifacts; they do not run live market inference.

## Baseline vs Transformer Comparison

Compare a logistic baseline summary against the Transformer trust run:

```bash
python -m scripts.compare_model_variants \
  --runs \
    data/artifacts/sp100_logistic_platt_summary.json \
    experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08 \
  --output experiments/005_temporal_transformer_trust/baseline_vs_transformer.md
```

This comparison intentionally separates probability-model rows (`raw`, `calibrated`, `tuned`) from
the warning-policy row (`trust_decision`). The expected v1 question is not whether the Transformer
wins every metric; it is whether calibration improves reliability and whether the trust decision
creates a more interpretable alerting policy.
