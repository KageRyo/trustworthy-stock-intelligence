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

## Deferred Work

The following topics are deferred until the core risk warning protocol is stable:

- candlestick image modeling
- news and social-media NLP
- LLM reasoning
- retrieval-augmented generation
- full multimodal fusion
- dashboard
- FastAPI service
- real-time streaming
- automated trading

These extensions may be used later, but they are not part of the first research milestone.
