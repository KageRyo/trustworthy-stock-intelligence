# Backlog

This backlog tracks the work after `0.3.0`. The roadmap groups the work by
release evidence and product maturity; issue numbers below are the canonical
discussion threads.

## Completed: 0.3.x Public Release Hardening

```text
[Docs #18] Align roadmap and backlog with the 0.3.0 research-evidence release.
[Docs #19] Add repository citation metadata in CITATION.cff.
[Docs #20] Add contributor setup, tests, research protocol, and PR guidance.
[Security #28] Add SHA-pinned CodeQL workflow and verify native GitHub scanning
             settings in the repository UI/API.
[Security] Keep the full-history Gitleaks scan, Dependabot, and branch gates
          healthy; document the commit-email privacy decision.
```

## v0.4.0 Product And Open-Source Readiness

```text
[Data] Schedule 5-minute ingestion for active watchlists.
[Data] Add provider health, retry, freshness, and coverage state per ticker.
[Model] Add queue-backed prediction jobs consuming PostgreSQL market_bars.
[Model] Keep daily and intraday model metadata and stale-state rules separate.
[API] Add warning-change detection on top of the completed warning-history API.
[Dashboard] Add freshness, stale, low-trust, coverage, loading, and error states.
[Dashboard] Add richer session-scoped watchlist grouping, filters, and cleanup.
```

## Research-Quality Enhancements

```text
[Research #29] Build a point-in-time universe and quantify survivorship bias.
[Research] Extend the current Taiwan and cross-market pilots only with explicit
           dated-membership, coverage, and provider-data boundaries.
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
