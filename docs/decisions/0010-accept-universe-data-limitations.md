# 0010: Accept Universe Data Limits and Defer the Formal Historical Benchmark

- Status: Accepted
- Date: 2026-10-26
- Evidence: [Issue #29](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/29), [Experiment 021](../../experiments/021_public_snapshot_proxy/README.md), [PR #179](https://github.com/KageRyo/trustworthy-stock-intelligence/pull/179)

## Context

The current-constituent pilots have survivorship bias. Issues #91, #92 and #93 delivered membership identities, import/coverage audits and a protocol-checked paired comparator. Experiment 021 adds a real-data weekly public-snapshot comparison, but its observation dates are not authoritative index-effective dates and its inactive/delisted price coverage is not independently verified. Neither implementation nor the proxy establishes that the bias has been removed or quantified.

## Decision

Accept these data gaps as an explicit limitation of the current project scope and defer the formal effective-date historical-universe benchmark. Close Issue #29 as not planned under this scope decision, preserving its original acceptance criteria as unmet rather than marking the research complete.

- Historical metrics describe the selected securities, supplied data snapshots and evaluated dates. Within-sample model comparisons must still use matching data and protocols and retain this qualification.
- Do not generalize those metrics to the full historical index, inactive/delisted securities or the whole market, or present them as evidence of investment performance.
- Experiment 021 is descriptive cohort sensitivity. Its two folds, source errors, mixed price retrieval dates and entry/exit censoring do not support a pure survivorship-bias estimate or a significance claim.
- The Model Card and research scope keep the limitation prominent. Data/rights provenance and the existing fail-closed comparison checks remain required; this decision relaxes no validation rule.

## Consequences

Documentation and implementation may be merged without treating the deferred benchmark as a delivery gate. Existing serving models, metrics, datasets and runtime behavior are unchanged. The limitation is accepted, not corrected; unavailable delisted observations remain unknown, not evidence of zero missing coverage. No stronger historical-performance claim follows from closing the issue.

## Revisit when

Reopen Issue #29 or create a linked follow-up when there is a concrete route to historical membership with effective and knowability dates, historical security identities and documented usage rights, together with matching inactive/delisted OHLCV and a coverage audit. A corresponding protocol-matched paired benchmark is required before revising the limitation. Public or institutional data may qualify if their coverage and permitted use are verified; a paid subscription alone is not sufficient.
