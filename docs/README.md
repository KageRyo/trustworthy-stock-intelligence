# Documentation

Start here to find the right document. Documents are grouped by what the reader is trying to do.

## Layout

| Folder                                        | Holds                                                         | Ask yourself                |
| --------------------------------------------- | ------------------------------------------------------------- | --------------------------- |
| [`guides/`](guides/)                          | Task-oriented steps: run, develop, release, download data     | "How do I ...?"             |
| [`reference/`](reference/)                    | Contracts and definitions: API, schema, metrics, labels       | "What exactly is ...?"      |
| [`concepts/`](concepts/)                      | Design and boundaries: architecture, trustworthy AI, licenses | "Why is it built this way?" |
| [`operations/`](operations/)                  | Runtime behavior: jobs, freshness, observability, E2E         | "What happens when ...?"    |
| [`research/`](research/)                      | Experiment rules: protocol, reproducibility, readiness        | "How is evidence produced?" |
| [`decisions/`](decisions/)                    | Decision records with their evidence                          | "Why did we choose this?"   |
| [`roadmap.md`](roadmap.md)                    | Now, next, later, and completed milestones                    | "What is planned?"          |
| [`../experiments/`](../experiments/README.md) | Experiment reports and their index                            | "What did we measure?"      |

## Model card

The [model card](model_card.md) describes the model served today: task, data, label, features, training and serving steps, performance, explanations, and limitations.

## Guides

| Document                                   | Purpose                                                                |
| ------------------------------------------ | ---------------------------------------------------------------------- |
| [User guide](guides/user_guide.md)         | Dashboard use: ticker input, analysis output, watchlists, limitations. |
| [Local demo](guides/local_demo.md)         | End-to-end local run of PostgreSQL, the Go API, and the dashboard.     |
| [Development](guides/development.md)       | Development rules, tests, schema-first policy, and commit workflow.    |
| [Environment](guides/environment.md)       | Python, Go, Node, CUDA, and local tool versions.                       |
| [Python package](guides/python_package.md) | PyPI package API, extras, CLI, and build checks.                       |
| [Data download](guides/data_download.md)   | Market data, reference series, and TWSE chip-history downloads.        |
| [Release](guides/release.md)               | Maintainer release checklist and per-release scope notes.              |

## Reference

| Document                                                      | Purpose                                                           |
| ------------------------------------------------------------- | ----------------------------------------------------------------- |
| [Analysis API](reference/api/analysis_api.md)                 | Ticker analysis response used by the dashboard.                   |
| [Warning API](reference/api/warning_api.md)                   | Warning, watchlist, health, status, and model endpoints.          |
| [OpenAPI spec](reference/api/openapi.yaml)                    | OpenAPI 3.1 document; must match the copy embedded in the Go API. |
| [Data store](reference/data_store.md)                         | PostgreSQL schema, provider ingestion, and freshness targets.     |
| [Provider coverage](reference/provider_coverage.md)           | Supported markets, provider fallbacks, intervals, and limits.     |
| [Evaluation metrics](reference/evaluation_metrics.md)         | Alert-oriented and calibration-aware metrics.                     |
| [Risk labeling](reference/risk_labeling.md)                   | Future-drawdown label definitions.                                |
| [Point-in-time universe](reference/point_in_time_universe.md) | Versioned identity mappings and membership filtering.             |

## Concepts

| Document                                                           | Purpose                                                  |
| ------------------------------------------------------------------ | -------------------------------------------------------- |
| [Architecture](concepts/architecture.md)                           | Python, PostgreSQL, Go, and dashboard boundaries.        |
| [Trustworthy AI checklist](concepts/trustworthy_ai_checklist.md)   | TAI dimensions mapped to this system.                    |
| [Problem definition](concepts/problem_definition.md)               | Research framing for drawdown-risk warning.              |
| [Research scope](concepts/research_scope.md)                       | Formal scope and exclusions.                             |
| [Data and model licenses](concepts/data_and_model_licenses.md)     | Code, provider-data, model, and redistribution limits.   |
| [Public and private boundary](concepts/public_private_boundary.md) | What belongs in public source versus private operations. |

## Operations

| Document                                                   | Purpose                                                            |
| ---------------------------------------------------------- | ------------------------------------------------------------------ |
| [Dashboard operations](operations/dashboard_operations.md) | Freshness, trust, coverage, and job states shown in the dashboard. |
| [Prediction jobs](operations/prediction_jobs.md)           | Queue lifecycle, idempotency, worker claims, and recovery.         |
| [Warning transitions](operations/warning_transitions.md)   | Warning-change semantics and deduplication.                        |
| [Watchlist grouping](operations/watchlist_grouping.md)     | Session watchlist groups, filters, and cleanup.                    |
| [Observability](operations/observability.md)               | Health probes, metrics, and structured logs.                       |
| [End-to-end pipeline](operations/e2e.md)                   | PostgreSQL watchlist-to-warning pipeline and its CI smoke test.    |

## Research

| Document                                               | Purpose                                                  |
| ------------------------------------------------------ | -------------------------------------------------------- |
| [Experiment protocol](research/experiment_protocol.md) | Temporal validation and experiment rules.                |
| [Reproducibility](research/reproducibility.md)         | Requirements for reproducible experiments and artifacts. |
| [Research readiness](research/research_readiness.md)   | Evidence gates for open research issues.                 |
| [Literature plan](research/literature_plan.md)         | Literature review plan and benchmark direction.          |

## Writing and maintaining docs

- **Placement.** Put each document in the one folder that matches its reader's question, and add it to the table above in the same pull request.
- **Names.** Use lowercase `snake_case.md`. Decision records use `NNNN-short-title.md`.
- **Opening.** Start with a title and one or two sentences saying what the document covers and who it is for.
- **Single source.**
  - Link to a fact instead of copying it.
  - Plans go in the roadmap, and decisions go in decision records.
  - Experiment numbers go in experiment reports. Other documents summarize them and link back.
- **Checks.** `make docs-check` runs mdformat (`--wrap no`, so each paragraph stays on one line) and `scripts/check_markdown_links.py`. The link checker fails on a relative link or an inline repository path (such as `docs/roadmap.md`) that Git does not track. Python CI runs the same check through `tests/test_markdown_links.py`.
- **Moves.** Use `git mv` so history follows the file, then run `make docs-check`.
