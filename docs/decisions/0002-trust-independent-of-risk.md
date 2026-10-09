# 0002: Trust and Uncertainty Are Independent of the Risk Probability

- Status: Accepted
- Date: 2026-10-06 (v0.5.0, pull request #122)
- Evidence: [Experiment 015](../../experiments/015_reliability_trust/README.md)

## Context

Before v0.5.0, `uncertainty = binary_entropy(p)` and `trust = p * (1 - 0.5 * uncertainty)`. Both were functions of the calibrated risk probability `p`, so the trust gate acted as a hidden second probability threshold. It halved recall without improving precision.

## Decision

- `uncertainty_score` averages bootstrap-ensemble disagreement and feature novelty, each ranked against the calibration window. It only moves rows below the watch threshold to `abstain`, and it never blocks an alert.
- `trust_score` is data quality (labeled history length, stale bars) times a calibration-drift multiplier. The alert trust threshold defaults to 0.4.
- Conformal sets only produce reason codes.
- No trust gate may be derived from `p`. `--trust-method legacy` reproduces the old behavior for comparison only.

## Consequences

Alert volume rose from about 17% to 32% of rows at unchanged precision. Experiment 016 then capped volume with explicit threshold policies.

## Revisit when

A new uncertainty signal identifies less reliable predictions on the same walk-forward protocol. That means a positive Brier skill for selective prediction, and blocked alerts that are less precise than kept ones.
