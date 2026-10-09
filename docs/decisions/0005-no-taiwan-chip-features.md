# 0005: Do Not Serve Taiwan Institutional-Flow or Margin Features

- Status: Accepted
- Date: 2026-10-08 (pull request #136)
- Evidence: [Experiment 018](../../experiments/018_taiwan_chip_features/README.md)

## Context

TWSE publishes daily institutional net buying (T86) and margin and short balances (MI_MARGN). These "chip" data are widely used in Taiwan, and the Taiwan baseline was the obvious place to add them.

## Decision

- Serving stays on `technical_range`.
- No PostgreSQL chip tables, scheduled chip ingestion, or Taiwan-specific serving feature set are added.
- The adapters, resumable backfill, and leakage-safe chip features remain for research.

## Consequences

- Adding chip features lowered AUC by 0.007 on 50 large caps.
- On a 199-stock seed-18 holdout, AUC moved by at most 0.0011, at both one-day and same-day publication lags.
- Serving avoids a daily TWSE dependency and the 2,854-request backfill per environment.

## Revisit when

A nonlinear model, a longer label horizon, or a market-relative label shows a chip-feature gain on the same discovery and holdout samples.
