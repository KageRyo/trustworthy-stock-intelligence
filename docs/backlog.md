# Backlog

This backlog tracks the work after `0.3.0`. The roadmap groups the work by
release evidence and product maturity; issue numbers below are the canonical
discussion threads.

## 0.3.x Public Release Hardening

```text
[Docs #18] Align roadmap and backlog with the 0.3.0 research-evidence release.
[Docs #19] Add repository citation metadata in CITATION.cff.
[Docs #20] Add contributor setup, tests, research protocol, and PR guidance.
[Security #28] Add SHA-pinned CodeQL workflow and verify native GitHub scanning
             settings in the repository UI/API.
[Security] Keep the full-history Gitleaks scan, Dependabot, and branch gates
          healthy; document the commit-email privacy decision.
```

## 0.4.0 Comparative Evidence

```text
[Research #21] Compare logistic, tree, and deep models under identical purged
              walk-forward splits and the same alert-oriented metrics.
[Research #22] Add confidence intervals and paired bootstrap model comparisons.
[Research] Record data fingerprints, limitations, calibration, false alarms,
           misses, lead time, coverage, and selective risk.
```

## 0.5.0 Taiwan And Cross-Market Evidence

```text
[Research #23] Evaluate Taiwan listed, TPEx listed, and TPEx emerging symbols
              within market with explicit coverage metadata.
[Research #24] Evaluate cross-market transfer after within-market baselines;
              Experiment 010 records the logistic US/Taiwan pilot and keeps
              the formal-universe/deep-model gaps explicit.
[Data] Build point-in-time universe metadata before claiming all-market
       coverage.
```

## 0.6.0 Drift And Trust Under Shift

```text
[Research #25] Track calibration drift and trust degradation over time.
[Trust] Test stale data, provider revisions, perturbation stability, and
       abstention thresholds under distribution shift.
```

## Product Track

```text
[Data] Schedule 5-minute ingestion for active watchlists.
[Data] Track provider freshness and provider coverage per ticker.
[Model] Add prediction jobs that consume PostgreSQL market_bars directly.
[Model] Keep daily and intraday model metadata separate.
[API] Add warning changes and warning history/date endpoints.
[Dashboard #27] Add ticker detail timelines and warning changes views.
[Dashboard] Add freshness, low-trust, coverage, loading, and error states.
[Trust #26] Add feature attribution beyond reason codes.
[Trust] Generate model-run TAI audit artifacts and monitor abstain rate.
[Data] Build provider health checks and outage reporting.
```

## Later Research And Data

```text
[Research #29] Build a point-in-time universe and quantify survivorship bias.
[Data] Validate intraday 5-minute data quality before model training.
[Data] Review provider revisions and licensed formal-research datasets.
[Research] Keep experiment reports reproducible and under experiments/.
```

## Deferred

```text
[Deferred] Automated trading.
[Deferred] Investment recommendation wording.
[Deferred] LLM-based advice.
[Deferred] Full multimodal learning.
[Deferred] Production authentication and paid plans.
```
