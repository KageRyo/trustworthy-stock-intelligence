# Documentation Index

This documentation set is organized by reader intent. The repository still
contains research notes and engineering contracts, but this index is the main
entry point for finding the right document.

## Start Here

| Document | Purpose |
| --- | --- |
| `../README.md` | Project overview, quick start, badges, and release status. |
| `user_guide.md` | Dashboard-oriented usage: ticker input, analysis output, watchlists, and limitations. |
| `demo/local_demo.md` | Local end-to-end runbook for PostgreSQL, Go API, and TypeScript dashboard. |

## Architecture And Operations

| Document | Purpose |
| --- | --- |
| `architecture.md` | Python, PostgreSQL, Go, and dashboard boundaries. |
| `data_store.md` | PostgreSQL schema intent, provider ingestion, freshness target, and Taiwan provider notes. |
| `prediction_jobs.md` | PostgreSQL prediction queue lifecycle, idempotency, worker claims, and local startup. |
| `warning_transitions.md` | Deterministic warning-change semantics, deduplication, and serving endpoint. |
| `dashboard_operations.md` | Freshness, trust, provider coverage, and prediction-job states shown by the dashboard. |
| `watchlist_grouping.md` | Session-scoped watchlist groups, filters, sorting, and confirmed bulk cleanup. |
| `observability.md` | Health/readiness probes, metrics, structured logs, and local inspection commands. |
| `e2e.md` | Deterministic PostgreSQL watchlist-to-warning pipeline and CI smoke test. |
| `provider_coverage.md` | Supported markets, provider fallback paths, intervals, and coverage limits. |
| `environment.md` | Python, Go, Node, CUDA, and local environment versions. |
| `python-package.md` | PyPI package API, extras, CLI, build checks, and release setup. |
| `development.md` | Development rules, tests, schema-first policy, and commit/release workflow. |
| `project_roadmap.md` | Current milestone state and next implementation tasks. |
| `backlog.md` | Prioritized task backlog after `0.3.1`. |

## API Contracts

| Document | Purpose |
| --- | --- |
| `api/warning_api.md` | Warning, watchlist, health, status, and model endpoint contracts. |
| `api/analysis_api.md` | Ticker analysis response schema used by the dashboard. |
| `api/openapi.yaml` | OpenAPI 3.1 document served by the API. |

## Trustworthy AI

| Document | Purpose |
| --- | --- |
| `trustworthy_ai_checklist.md` | TAI dimensions mapped to this stock-risk system. |
| `reproducibility.md` | Reproducibility requirements for experiments and artifacts. |
| `evaluation_metrics.md` | Alert-oriented and calibration-aware evaluation metrics. |
| `data_and_model_licenses.md` | Code, provider-data, model, and redistribution boundaries. |
| `research_readiness.md` | Evidence gates and source boundaries for open research issues. |
| `public_private_boundary.md` | What belongs in public source versus private operations. |

## Research Protocol

| Document | Purpose |
| --- | --- |
| `problem_definition.md` | Research framing for drawdown-risk warning. |
| `research_scope.md` | Formal research scope and exclusions. |
| `risk_labeling.md` | Future drawdown label definitions. |
| `experiment_protocol.md` | Temporal validation and experiment rules. |
| `data_download.md` | Batch market-data download notes. |
| `literature_plan.md` | Literature-review plan and benchmark direction. |

## Experiment Reports

Experiment reports live under `../experiments/`. They are retained as research
artifacts and are separate from the live dashboard runbooks.

The current primary pilot evidence is
`../experiments/007_research_evidence/README.md`.

## Release Notes

Use `../CHANGELOG.md` for release notes and `release.md` for the maintainer
release checklist.
