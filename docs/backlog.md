# Backlog

This backlog tracks the work after `0.3.1`. The roadmap groups the work by release evidence and
product maturity; issue numbers below are the canonical discussion threads.

## Completed: 0.3.x Public Release Hardening

```text
[Docs #18] Align roadmap and backlog with the 0.3.1 open-source release.
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
[Data] Add a schema-first 5-minute OHLCV quality audit and fail-closed persistence boundary.
[Model] Add queue-backed prediction jobs consuming PostgreSQL market_bars.
[Model] Keep daily and intraday model metadata and stale-state rules separate.
[API] Add warning-change detection on top of the completed warning-history API.
[Dashboard] Add freshness, stale, low-trust, coverage, loading, and error states.
[Dashboard] Add richer session-scoped watchlist grouping, filters, and cleanup.
```

## Ordered Research-Engineering Sequence

```text
[Research #91] Add stable security identities, versioned symbol mappings, and
              point-in-time filtering with v1 compatibility.
[Data #92] Import vendor-neutral membership archives through typed mappings,
           provenance fingerprints, issue reports, and coverage audits.
[Research #93] Compare current-universe and point-in-time runs only when fold,
                date, feature, label, calibration, threshold, and model contracts match.
[Research #29] Parent survivorship-bias question remains open until licensed
               historical constituents, inactive/delisted OHLCV, and the paired
               benchmark are available.
[Research] Extend the current Taiwan and cross-market pilots only with explicit
           dated-membership, coverage, and provider-data boundaries.
[Data] Run the five-minute quality audit repeatedly across real US/Taiwan provider
      snapshots, review calendar exceptions and revisions, and keep interval-model
      claims blocked until coverage evidence is sufficient.
[Model] Keep the current baseline described as daily; five-minute support is
       currently ingestion/freshness coverage and explicit worker abstention.
[Operations] Verify prediction-worker lease recovery, retry budgets, and stale
             output abstention with PostgreSQL-backed smoke tests and runbooks.
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
