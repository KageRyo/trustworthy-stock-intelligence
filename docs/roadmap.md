# Roadmap

This is the single planning document. It replaces the earlier separate backlog. Issue numbers are
the canonical discussion threads. Decisions that are already made live in
[decision records](decisions/README.md).

## Goal

Trustworthy Stock Intelligence is a public open-source and portfolio project for human-in-the-loop
stock drawdown-risk assessment:

```text
stock ticker -> market data -> calibrated drawdown-risk model -> uncertainty and trust
-> warning level and reasons -> dashboard/API analysis
```

It focuses on calibration, uncertainty, abstention, transparency, auditability, and clear
limitations. It is not an investment recommendation or automated trading system.

## Current state

Version `0.7.0` is an operational prototype. Since that release, `main` also has:

- the Taiwan chip-data research path (Experiment 018, no serving change);
- dashboard localization of trust and freshness summaries;
- a Go dependency security update.

The served model and the evidence behind it are summarized in the
[experiment index](../experiments/README.md) and the decision records.

## Now

1. **On-demand reliability.**
   - Replace string matching of insufficient-history errors with a typed error.
   - Handle Yahoo's zero-volume placeholder bars on Taiwan typhoon closures in the technical
     features.
1. **On-demand concurrency.** Run one analysis per ticker at a time (singleflight) and cap
   concurrent analyses in the Go bridge.
1. **Documentation.**
   - Add a model card for the served model.
   - Refresh the README with dashboard screenshots and live badges.

## Next

1. Move on-demand analysis onto the `prediction_jobs` queue and show progress in the dashboard.
1. Split `frontend/stock-dashboard/src/App.tsx` (about 1,750 lines) into components with Testing
   Library coverage.
1. Model research on the Experiment 017 protocol:
   - nonlinear models that can use interactions;
   - a market-relative drawdown label;
   - longer label horizons.
1. A validated SPY and TAIEX reference-data path in serving, so the beta feature from Experiment 017
   can be considered.

## Later or blocked

- **Survivorship bias (Issue #29):** needs licensed historical constituents and inactive or delisted
  OHLCV. Issues #91, #92, and #93 built the comparison machinery but do not replace that data.
- **Five-minute models:** five-minute bars are ingestion and freshness coverage only. Do not build
  an interval model until the daily model's predictive value is established, and the quality audit
  has run repeatedly across real US and Taiwan provider snapshots.
- **Broader Taiwan coverage:** dated membership, wider stratification, and reliable TPEx emerging
  history before any all-market claim.
- **Licensed research data:** provider-revision and external-data studies on licensed, versioned
  data.

## Deferred

Automated trading, investment-recommendation wording, LLM-based advice, full multimodal learning,
and production authentication or paid plans.

## Completed milestones

| Version    | Highlights                                                                                                                                                           |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.3.x      | Public release hardening: citation, contribution guide, CodeQL, Gitleaks, required CI                                                                                |
| 0.4.x      | Scheduled five-minute ingestion, provider health, market-bar quality audit, prediction jobs, warning transitions, dashboard states                                   |
| 0.5.0      | Reliability-based trust and uncertainty ([ADR 0002](decisions/0002-trust-independent-of-risk.md)), Tailwind CSS v4                                                   |
| 0.6.0      | Calibration-window alert-rate policies ([ADR 0003](decisions/0003-alert-rate-threshold-policy.md))                                                                   |
| 0.7.0      | Range-volatility serving features ([ADR 0004](decisions/0004-range-volatility-features.md))                                                                          |
| Unreleased | Taiwan chip-data research ([ADR 0005](decisions/0005-no-taiwan-chip-features.md)), localized summaries ([ADR 0006](decisions/0006-dashboard-localizes-api-codes.md)) |

See [`CHANGELOG.md`](../CHANGELOG.md) for full release notes. Engineering rules are in the
[development guide](guides/development.md).
