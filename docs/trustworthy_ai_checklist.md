# Trustworthy AI Checklist

Source reviewed: `air_screen3_TAI指標互動展示.pptx`, 58 slides verified from
the PPTX slide XML and extracted text on 2026-06-20.

This checklist adapts the deck's pre-modeling, modeling, and post-modeling TAI
dimensions to this stock drawdown-risk warning project.

## Dimensions

| Dimension | Project checkpoint |
| --- | --- |
| Accuracy | Track data freshness, data quality, completeness, calibration, precision, recall, F1, false alarm rate, miss rate, and lead time. |
| Reliability | Test provider outages, market-noise sensitivity, perturbation stability, drift, stale data handling, and warning-threshold stability. |
| Safety | Keep outputs framed as risk warnings, not investment advice. Show limitations, stale-data states, low-trust states, and warning thresholds. |
| Resilience | Support US and Taiwan symbols, numeric Taiwan codes, 1m/5m/1d bars, provider replacement, scheduled ingestion, and recovery after provider failures. |
| Transparency | Persist run IDs, model bundle names, data_as_of, generated_at, feature interval, reason codes, logs, and audit metadata. |
| Accountability | Keep API schemas, tests, dependency/license review, run notes, and Python/Go/dashboard responsibility boundaries explicit. |
| Explainability | Provide reason-code explanations, typed feature attributions, and ticker-level warning history; document their model-specific, non-causal limits. |
| Autonomy | Keep the dashboard human-over-the-loop. Users control watchlists, and the system must not automate trading actions. |
| Privacy | Minimize data collection. Protect `.env`, DB credentials, logs, and any future user holdings/watchlist-sensitive data. |
| Fairness | Track coverage bias across US/Taiwan markets, sectors, liquidity, market cap, and provider availability. Do not claim all-stock coverage until measured. |
| Security | Use typed schemas, strict error envelopes, input validation, dependency audits, CORS allowlists, DB-required startup, and provider payload validation. |

## Stage Gates

Before modeling:

- Define target use, users, non-use cases, and risk-warning limits.
- Validate provider freshness, required OHLCV fields, symbol normalization, and
  market coverage.
- Define risk labels, alert/watch/no-alert thresholds, and audit fields before
  training.
- Record privacy, license, dependency, and data-source assumptions.

During modeling:

- Report accuracy metrics and alert-oriented metrics under temporal validation.
- Monitor data quality, missing fields, class imbalance, calibration quality,
  uncertainty, and trust threshold behavior.
- Record training data, feature columns, model bundle, calibrator, thresholds,
  and run metadata.
- Test robustness against stale data, missing bars, noisy prices, and provider
  corrections.

After modeling:

- Continue monitoring freshness, drift, calibration, warning changes, and
  coverage.
- Provide user-facing explanations, limitations, and model decision purpose.
- Keep a correction path for bad warnings, stale predictions, and low-trust
  outputs.
- Maintain security, dependency, CORS, DB, and audit controls.

## Near-Term Tasks

- Schedule 5-minute watchlist ingestion into PostgreSQL with provider health,
  retry, and coverage records.
- Add queue-backed prediction jobs that consume fresh DB market bars and write
  `prediction_batches` / `warning_records`.
- Add warning-change detection on top of the available history and timeline
  contracts.
- Add API/dashboard freshness badges that block or downgrade stale predictions.
- Add universe coverage metadata for US and Taiwan markets.
- Use the available TAI audit artifact for every published model run, and keep
  deployment-specific evidence, known limitations, and open risks explicit.

## Per-Run Audit Artifact

Generate a schema-first JSON audit after model training. It records supplied
evidence and marks missing evidence as `partial` or `open`; it does not convert
an unchecked control into a pass.

```bash
export TSI_PRIVATE_DATA_DIR=/path/to/private/tsi-data

PYTHONPATH=src python -m scripts.generate_tai_audit \
  --summary "$TSI_PRIVATE_DATA_DIR/run/summary.json" \
  --data-manifest "$TSI_PRIVATE_DATA_DIR/data/metadata.json" \
  --warning-eval "$TSI_PRIVATE_DATA_DIR/run/warning_eval.json" \
  --feature-interval 1d \
  --known-limitation "Current-universe membership is not point-in-time." \
  --output "$TSI_PRIVATE_DATA_DIR/run/tai_audit.json" \
  --markdown-output "$TSI_PRIVATE_DATA_DIR/run/tai_audit.md"
```

The artifact covers Accuracy, Reliability, Safety, Resilience, Transparency,
Accountability, Explainability, Autonomy, Privacy, Fairness, and Security.
It requires the run owner to supply deployment-specific evidence such as
provider recovery, access controls, and user-facing human-control behavior.
