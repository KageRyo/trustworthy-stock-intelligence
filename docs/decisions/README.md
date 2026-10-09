# Decision Records

Each record captures one decision that shapes the served system, the evidence behind it, and when to revisit it. Records are short and stable. When a decision changes, add a new record that supersedes the old one, and mark the old one `Superseded by NNNN` instead of rewriting it.

| ID                                              | Decision                                                                                        | Status   | Evidence                                                               |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------- |
| [0001](0001-postgresql-serving-source.md)       | PostgreSQL is the serving source of truth, and the Go API fails fast without it                 | Accepted | [Architecture](../concepts/architecture.md)                            |
| [0002](0002-trust-independent-of-risk.md)       | Trust and uncertainty do not derive from the risk probability, and never block alerts           | Accepted | [Experiment 015](../../experiments/015_reliability_trust/README.md)    |
| [0003](0003-alert-rate-threshold-policy.md)     | Alert and watch thresholds use calibration-window alert-rate policies                           | Accepted | [Experiment 016](../../experiments/016_alert_policy/README.md)         |
| [0004](0004-range-volatility-features.md)       | Serve range-volatility features, and reject market-regime features                              | Accepted | [Experiment 017](../../experiments/017_feature_sets/README.md)         |
| [0005](0005-no-taiwan-chip-features.md)         | Do not serve Taiwan institutional-flow or margin features                                       | Accepted | [Experiment 018](../../experiments/018_taiwan_chip_features/README.md) |
| [0006](0006-dashboard-localizes-api-codes.md)   | The dashboard localizes stable API codes, and API text is only a fallback                       | Accepted | Pull request #138                                                      |
| [0007](0007-calibration-keeps-model-ranking.md) | Calibration keeps the model's ranking, and a reversed Platt fit falls back to a base-rate shift | Accepted | [Experiment 020](../../experiments/020_serving_replay/README.md)       |
| [0008](0008-keep-logistic-expanding-window.md)  | Keep the logistic model and train on every earlier labeled date                                 | Accepted | [Experiment 019](../../experiments/019_nonlinear_models/README.md)     |

## Template

```markdown
# NNNN: Decision title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD
- Evidence: links to experiments, pull requests, or issues

## Context

What problem or question forced a decision.

## Decision

What the system does now, stated so a reader can check it in code or configuration.

## Consequences

What this costs, what it enables, and what must stay true.

## Revisit when

The evidence or conditions that would reopen the decision.
```
