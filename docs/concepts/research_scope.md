# Research Scope

## Working Title

```text
Trustworthy Stock Risk Early-Warning via Calibrated Uncertainty and Selective Prediction
```

## Key Idea

Stock models should not be forced to issue confident predictions every day. When a model is poorly calibrated, uncertain, or operating under unstable market conditions, the safer research objective is to allow the system to watch or abstain.

The first version focuses on:

```text
calibrated risk probability
predictive uncertainty
selective warning decisions
alert-oriented evaluation
```

## Proposed Contribution

Contribution 1:

```text
Reformulate stock prediction as a future drawdown risk early-warning task.
```

Contribution 2:

```text
Introduce a trust-aware selective warning framework that combines calibrated probability and uncertainty.
```

Contribution 3:

```text
Evaluate stock risk warnings with false alarm rate, miss rate, lead time, calibration error, coverage, and selective risk under walk-forward validation.
```

Contribution 4:

```text
Provide a reproducible research codebase for stock risk early-warning experiments.
```

## Milestone 1: TSI-Risk-v0

```text
Universe: S&P 100
Data: Daily OHLCV + technical indicators + market index features
Task: 5-day drawdown risk warning
Label: future 5-day max drawdown <= -5%
Models: Logistic Regression, Random Forest, XGBoost
Trust layer: Calibration + uncertainty-aware warning levels
Evaluation: walk-forward validation, false alarm rate, miss rate, lead time, ECE
```

## Accepted universe-data limitation

Historical results apply to the selected securities, supplied snapshots and evaluated dates. The main current-constituent pilots retain survivorship bias; authoritative historical membership and independently verified inactive/delisted OHLCV coverage are not available for the formal paired benchmark.

[Experiment 021](../../experiments/021_public_snapshot_proxy/README.md) adds a bounded weekly public-information proxy comparison. It does not certify effective-date index membership or quantify pure survivorship bias. Model comparisons within the same sample and protocol remain sample-conditional; they cannot establish full historical-index, whole-market or investment performance.

[ADR 0010](../decisions/0010-accept-universe-data-limitations.md) accepts this limitation and defers the formal benchmark. Issue #29 is retired from active delivery as not planned under that scope, not as completed research. Revisit it when usable historical membership, identities, usage rights and matching inactive/delisted prices can support a coverage audit and protocol-matched paired evaluation. The [Model Card](../model_card.md) carries the same boundary.

## Formal Research Deferred Work

The following topics are deferred for the formal research milestone until the core risk warning protocol is stable:

- candlestick image modeling
- news and social-media NLP
- LLM reasoning
- retrieval-augmented generation
- full multimodal fusion
- real-time streaming
- automated trading

The side-project product track now includes a Go API and TypeScript dashboard. Those product surfaces do not change the formal research requirement: model claims still need leakage-aware temporal validation and trustworthy AI reporting before being treated as research results.
