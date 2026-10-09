# Problem Definition

## Positioning

Trustworthy Stock Intelligence is a research-oriented framework for stock risk early-warning. It is not a stock recommendation system, an automated trading bot, or an exact price prediction system.

The project studies how to produce reliable warnings for future risk events under high market noise, non-stationarity, imperfect model confidence, and class imbalance.

## Core Problem

Traditional stock prediction tasks often force a model to predict next-day price direction or future price level. This framing is difficult to trust because small price movements are noisy, unstable, and often not actionable as risk signals.

This project reformulates stock analysis as a future risk-event detection problem:

```text
Given historical market observations up to day t,
predict whether a stock will experience a drawdown risk event within the next H trading days.
```

## Initial Task: 5-Day Drawdown Risk Warning

Milestone 1 uses the following setting:

```text
Universe: S&P 100
Frequency: Daily
Horizon: 5 trading days
Risk event: future 5-day max drawdown <= -5%
```

The target label is binary:

```text
Risk = 1 if the future 5-day max drawdown is <= -5%
Risk = 0 otherwise
```

## Research Questions

RQ1: Can stock analysis be framed more reliably as future drawdown risk warning instead of next-day movement prediction?

RQ2: Can probability calibration improve the reliability of model confidence for stock risk warning?

RQ3: Can uncertainty-aware selective prediction reduce false alerts while maintaining useful risk-event coverage?

## Trustworthy Warning Objective

The expected output is not only a class label. A trustworthy warning should include:

```text
risk probability
calibrated confidence
uncertainty estimate
warning level
explanation factors
```

The intended decision space is:

```text
Alert: issue a high-risk warning
Watch: mark the stock as uncertain or moderately risky
Abstain: avoid making a confident warning decision
No Alert: no material risk warning
```

## Non-Goals

This study does not aim to:

- provide investment advice
- recommend stocks to buy or sell
- maximize trading profit
- build an autonomous trading system
- predict exact future stock prices
- make real-time production alerts

The system implementation exists to support reproducible experiments, not to serve as a trading product.
