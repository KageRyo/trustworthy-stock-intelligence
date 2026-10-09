# 0007: Calibration Must Not Reverse the Model's Ranking

- Status: Accepted
- Date: 2026-10-09
- Evidence: [Experiment 020](../../experiments/020_serving_replay/README.md) and the [Experiment 007 audit](../../experiments/007_research_evidence/README.md)

## Context

Serving calibrates the logistic model with Platt scaling on the latest 63 labeled dates. Platt scaling is a logistic regression on the model's score, and nothing kept its slope positive. When the calibration window is a regime break and the model's ranking fails there, the slope turns negative and the calibrated probabilities rank the riskiest rows as the safest.

The Experiment 007 audit found one such fold in 2018 (slope -0.798) and recorded it without changing serving. Replaying the served scheme in Experiment 020 found the same 2018 period reversed (slope -1.12, test AUC 0.758 calibrated to 0.242), and Experiment 019 found a 2020 crash fold reversed. Single-ticker on-demand models reverse at about half of all as-of dates, because their 63-row calibration windows hold about 7 drawdowns.

## Decision

- Serving and on-demand analysis default to `--calibration-method platt_monotone`.
- `platt_monotone` fits Platt scaling. If the slope is not positive, it keeps the model's ranking and shifts the raw log-odds so the mean calibrated probability equals the calibration window's event rate.
- Every row scored with the fallback carries the reason code `calibration_slope_nonpositive`, which the API and dashboard explain.
- `platt` remains a choice, and the research scripts keep it as the default so that earlier experiments reproduce.

## Consequences

- Non-reversed batches are unchanged. In the Experiment 020 pooled replay, the mean S&P 100 AUC rises from 0.6556 to 0.6602, Brier from 0.0929 to 0.0927, and ECE from 0.0534 to 0.0526. Taiwan never reversed.
- The fallback's probabilities keep the raw model's spread, so they are less well calibrated than a perfect recalibration would be. For single-ticker models, which have no ranking signal, it costs about 0.002 Brier and 0.008 ECE against Platt.
- On-demand results will often show `calibration_slope_nonpositive`. That is accurate: their calibration window gives no evidence that the ranking works.
- Thresholds, trust, and uncertainty are unchanged. The reason code does not lower trust.

## Revisit when

- On-demand analysis scores tickers with a pooled model, which removes most single-ticker reversals.
- A calibration method that cannot reverse by construction, such as isotonic regression with enough calibration rows, matches Platt's Brier and ECE on the same replay.
