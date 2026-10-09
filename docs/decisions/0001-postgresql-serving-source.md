# 0001: PostgreSQL Is the Serving Source of Truth

- Status: Accepted
- Date: recorded 2026-10-08; in force since the PostgreSQL serving path replaced JSON artifacts
- Evidence: [Architecture](../concepts/architecture.md), [Data store](../reference/data_store.md)

## Context

Early prototypes served `latest_warnings.json` and CSV artifacts. That made results hard to audit: there was no history, no batch metadata, and no way to tell a stale file from a fresh one. The product also needs watchlists, universe membership, market bars, and prediction history.

## Decision

- Python writes `prediction_batches` and `warning_records` to PostgreSQL. The Go API reads only from PostgreSQL.
- The Go API requires `TSI_DATABASE_URL` and fails at startup when the database is missing or unreachable. There is no JSON or sample-data fallback.
- Provider APIs (yfinance, TWSE, TPEx) are ingestion sources, not the state layer.

## Consequences

- Every served record carries its batch, run ID, data cutoff, and policy metadata.
- Local demos need Docker and PostgreSQL. CSV and JSON files remain reproducible research artifacts only.

## Revisit when

A hosted deployment needs a different managed store, or read volume requires a separate read model.
