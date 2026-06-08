# Project Roadmap

## Project Goal

Trustworthy Stock Intelligence is evolving into a deep-learning stock risk
alerting side project.

The goal is to build a complete, runnable, explainable, and auditable risk
warning system. The system focuses on trustworthy AI behavior, not investment
advice, exact price prediction, or automated trading.

```text
Historical market data
-> deep risk predictor
-> calibration
-> uncertainty estimation
-> trust score
-> warning decision
-> dashboard and audit-ready logs
```

## Scope Shift

The original milestone remains useful as the leakage-aware baseline and
experiment protocol. For the side project version, the scope expands beyond the
research-only first milestone.

In scope for the side project:

- Logistic, tree-based, and deep-learning risk models
- Temporal Transformer as the first main DL model
- Probability calibration and calibration diagnostics
- Uncertainty estimation
- Trust score and abstain decisions
- Explanation factors and warning reason codes
- Prediction and warning audit logs
- Streamlit dashboard for the first demo
- Go API gateway after the Python ML loop is stable

Still out of scope:

- Investment recommendations
- Automated trading
- Claims of guaranteed profit
- Random train-test splits for main evaluation
- Rewriting DL training or feature engineering in Go

## Milestone 0: Preserve Baseline

Keep the existing leakage-aware baseline pipeline runnable:

```text
OHLCV
-> technical features
-> future drawdown label
-> walk-forward split
-> logistic regression
-> calibration
-> warning level
-> alert-oriented metrics
```

The baseline is used to validate labels, temporal splits, calibration, and
warning decisions before adding deep models.

## Milestone 1: Python DL Closed Loop

Build the first complete Python-only trustworthy DL loop.

Target additions:

```text
src/tsi/training/dataset.py
src/tsi/training/trainer.py
src/tsi/models/temporal_transformer.py
scripts/train_deep.py
```

Initial modeling setup:

```text
lookback = 60 trading days
horizon = 5 trading days
risk event = future 5-day max drawdown <= -5%
model = Temporal Transformer Encoder
loss = BCEWithLogitsLoss
optimizer = AdamW
```

Expected output fields:

```text
risk_probability
calibrated_risk_probability
uncertainty_score
trust_score
warning_level
reason_codes
```

## Milestone 2: Trust Layer

Add a dedicated trust layer after model inference.

Target modules:

```text
src/tsi/trust/uncertainty.py
src/tsi/trust/trust_score.py
src/tsi/trust/decision.py
```

First decision rule:

```text
trust_score = calibrated_risk_probability - lambda * uncertainty_score

if calibrated_p >= alert_threshold and trust_score >= trust_threshold:
    alert
elif calibrated_p >= watch_threshold:
    watch
elif uncertainty_score >= uncertainty_threshold:
    abstain
else:
    no_alert
```

## Milestone 3: Streamlit Dashboard

Use Streamlit for the first demo. The first version may read prediction CSV
artifacts directly instead of requiring a database.

Required views:

- Ticker selector
- Latest risk probability
- Raw versus calibrated probability
- Uncertainty score
- Trust score
- Warning level timeline
- Recent explanation factors

## Milestone 4: Go API Gateway

Add Go only after the Python training, inference, trust score, and dashboard
loop is stable.

Recommended split:

```text
Go = user-facing API, WebSocket/SSE, cache, warning queries, job dispatch
Python = feature engineering, training, inference, calibration, uncertainty, explanation
Redis = cache and queue
PostgreSQL = source of truth
```

Most user requests should read precomputed predictions and warnings from
Redis/PostgreSQL. On-demand prediction should be submitted as a job instead of
running synchronous model inference on every request.

## Engineering Rules

Feature changes should start with explicit tests or test cases. After
implementation, the relevant test suite must pass before commit or push.

Commit messages use this format:

```text
type(scope): summary
```

Allowed types include:

```text
chore
init
feat
fix
refactor
docs
test
```

If environment variables change, update `.env` and `.env.example` together.
Never commit `.env`, and never put secrets or sensitive values in
`.env.example`.
