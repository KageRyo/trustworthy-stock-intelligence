# Experiment 006: Recall-Oriented Trust Policy

This experiment studies warning-policy tradeoffs using an existing threshold sweep from the Temporal
Transformer trust run. It does not retrain the model.

The goal is to identify candidate policies that improve alert recall and then make the cost explicit
through alert false alarm rate, coverage, and selective risk.

Generate candidates:

```bash
python -m scripts.select_warning_policy \
  --sweep experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08/threshold_sweep.csv \
  --objective recall \
  --limit 10 \
  --output experiments/006_recall_oriented_trust_policy/recall_policy_candidates.md
```

Current readout:

- Recall-oriented candidates can raise alert recall materially versus the v1 conservative policy.
- The cost is a much higher alert rate and false alarm rate.
- These rows are useful for research planning, not for the v1 demo default.
