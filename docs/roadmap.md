# Roadmap

This is the single planning document. It replaces the earlier separate backlog. Issue numbers are the canonical discussion threads. Decisions that are already made live in [decision records](decisions/README.md).

## Goal

Trustworthy Stock Intelligence is a public open-source and portfolio project for human-in-the-loop stock drawdown-risk assessment:

```text
stock ticker -> market data -> calibrated drawdown-risk model -> uncertainty and trust
-> warning level and reasons -> dashboard/API analysis
```

It focuses on calibration, uncertainty, abstention, transparency, auditability, and clear limitations. It is not an investment recommendation or automated trading system.

## Current state

Version `0.10.1` is an operational prototype. It keeps the `0.9.0` model and adds:

- a guarded daily refresh per market that validates provider history, stores it in PostgreSQL, trains the pooled model on the stored copy, and atomically publishes the bundle used by on-demand analysis, with recoverable publication and a bounded run history;
- audited TPEx close corrections backed by official prices;
- systemd user units and weekday timers for the local PostgreSQL, Go API, dashboard, and refreshes (see [local operations](guides/local_operations.md));
- model provenance without host paths, and a dashboard trust panel that shows the selected ticker's own model.

Both timers have fired and published on schedule; recovery after a full Windows or WSL restart has not been observed yet.

The served model is described in the [model card](model_card.md). The evidence behind it is in the [experiment index](../experiments/README.md) and the decision records.

## Now

1. **Move on-demand analysis onto the `prediction_jobs` queue** and show progress in the dashboard. Pooled bundles now refresh daily, so queued jobs can score new tickers with a current model of their market ([ADR 0009](decisions/0009-on-demand-uses-pooled-bundles.md)).

## Next

1. Split `frontend/stock-dashboard/src/App.tsx` (about 1,750 lines) into components with Testing Library coverage.
1. Label research on the Experiment 017 protocol:
   - a market-relative drawdown label;
   - longer label horizons.
1. A validated SPY and TAIEX reference-data path in serving, so the beta feature from Experiment 017 can be considered.

## Later or blocked

- **Taiwan typhoon placeholder bars:**

  - Yahoo writes flat, zero-volume bars on market-wide closures, about six days since 2015.
  - Stock-specific no-trade days look identical and are real observations, about 1% of rows in the 199-stock Taiwan holdout.
  - Removing only the closures needs an exchange calendar in serving. Removing all flat zero-volume bars needs a walk-forward check, because it changes returns and labels for illiquid stocks.

- **Survivorship bias (Issue #29):** needs licensed historical constituents and inactive or delisted OHLCV. Issues #91, #92, and #93 built the comparison machinery but do not replace that data.

- **Five-minute models:** five-minute bars are ingestion and freshness coverage only. Do not build an interval model until the daily model's predictive value is established, and the quality audit has run repeatedly across real US and Taiwan provider snapshots.

- **Broader Taiwan coverage:** dated membership, wider stratification, and reliable TPEx emerging history before any all-market claim.

- **Licensed research data:** provider-revision and external-data studies on licensed, versioned data.

## Deferred

Automated trading, investment-recommendation wording, LLM-based advice, full multimodal learning, and production authentication or paid plans.

## Completed milestones

| Version | Highlights                                                                                                                                                                                                       |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.3.x   | Public release hardening: citation, contribution guide, CodeQL, Gitleaks, required CI                                                                                                                            |
| 0.4.x   | Scheduled five-minute ingestion, provider health, market-bar quality audit, prediction jobs, warning transitions, dashboard states                                                                               |
| 0.5.0   | Reliability-based trust and uncertainty ([ADR 0002](decisions/0002-trust-independent-of-risk.md)), Tailwind CSS v4                                                                                               |
| 0.6.0   | Calibration-window alert-rate policies ([ADR 0003](decisions/0003-alert-rate-threshold-policy.md))                                                                                                               |
| 0.7.0   | Range-volatility serving features ([ADR 0004](decisions/0004-range-volatility-features.md))                                                                                                                      |
| 0.8.0   | Taiwan chip-data research ([ADR 0005](decisions/0005-no-taiwan-chip-features.md)), localized summaries ([ADR 0006](decisions/0006-dashboard-localizes-api-codes.md)), on-demand concurrency limits               |
| 0.9.0   | Monotone calibration ([ADR 0007](decisions/0007-calibration-keeps-model-ranking.md)), pooled on-demand model bundles ([ADR 0009](decisions/0009-on-demand-uses-pooled-bundles.md)), TPEx and emerging resolution |
| 0.10.0  | Daily pooled-model refresh with recoverable publication, audited TPEx close corrections, local service timers                                                                                                    |

See [`CHANGELOG.md`](../CHANGELOG.md) for full release notes. Engineering rules are in the [development guide](guides/development.md).
