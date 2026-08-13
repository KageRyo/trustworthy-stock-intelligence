# Release Checklist

## 0.4.0 Scope

`0.4.0` is the product-readiness release following the `0.3.2` maintenance
and security release:

- scheduled five-minute watchlist ingestion with provider health and coverage
- actionable freshness/stale policy and queue-backed prediction jobs
- deterministic warning transitions and typed job status/failure responses
- dashboard operational states and richer session-scoped watchlists
- readiness, structured observability, metrics, and deterministic PostgreSQL
  watchlist-to-warning E2E coverage

The release does not claim a high-precision warning policy, a trading edge,
all-market coverage, point-in-time historical membership, or externally
validated cross-market suitability. Issue #29 remains open because the actual
licensed historical constituent archive and comparable benchmark rerun are not
present in the repository.

## Version Files

Update:

```text
pyproject.toml
frontend/stock-dashboard/package.json
frontend/stock-dashboard/package-lock.json
frontend/stock-dashboard/README.md
dashboard/README.md
docs/api/openapi.yaml
services/api-gateway-go/internal/http/openapi.yaml
services/api-gateway-go/README.md
README.md
CITATION.cff
docs/environment.md
docs/project_roadmap.md
docs/demo/local_demo.md
CHANGELOG.md
docs/release.md
```

## Required Checks

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
go vet ./...
govulncheck ./...
go test ./...
go test -race ./...
cd ../../frontend/stock-dashboard
npm ci
npm test
npm run build
npm audit --audit-level=moderate
```

The CI `Watchlist-to-warning E2E` job additionally starts PostgreSQL 17,
applies all migrations, runs the deterministic fake-provider pipeline, starts
the Go API, and validates the captured response with the frontend Zod schema.
It must be green before the release merge.

## Release Procedure

1. Prepare the version and changelog changes on a release branch.
2. Merge the release PR only after all required checks pass.
3. Confirm the merge commit is the current `main` head and rerun all checks.
4. Create an annotated `v0.4.0` tag on that verified commit.
5. Push the tag and create a GitHub Release with `--verify-tag`.
6. Confirm the remote tag, release target, release notes, and downloadable
   source archives.
