# Release Checklist

## 0.3.1 Scope

`0.3.1` is the public open-source product and research-quality release:

- aligned logistic, tree, and GPU deep-model pilot comparison with documented
  current-universe limits
- paired bootstrap intervals, calibration-drift detection, and a schema-first
  TAI audit artifact for each model run
- reproducible Taiwan and US/Taiwan transfer pilots with explicit coverage,
  provider, and current-universe limitations
- typed feature attributions, warning-history timelines, and calibrated drift
  state in the PostgreSQL-backed Go API and TypeScript dashboard
- public-source contribution, citation, licensing, and public/private-boundary
  documentation
- required CI, Dependabot, `govulncheck`, race tests, Gitleaks, CodeQL, native
  GitHub Secret Scanning, and Push Protection
- v0.4 product priorities for 5-minute ingestion, provider health/freshness,
  queue-backed prediction jobs, warning-change detection, and richer watchlists

The release does not claim a high-precision warning policy, a trading edge,
all-market coverage, or externally validated cross-market suitability.

## Version Files

Update:

```text
pyproject.toml
frontend/stock-dashboard/package.json
frontend/stock-dashboard/package-lock.json
frontend/stock-dashboard/README.md
docs/api/openapi.yaml
services/api-gateway-go/internal/http/openapi.yaml
services/api-gateway-go/README.md
README.md
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

## Release Procedure

1. Prepare the version and changelog changes on a release branch.
2. Merge the release PR only after all required checks pass.
3. Confirm the merge commit is the current `main` head and rerun all checks.
4. Create an annotated `vX.Y.Z` tag on that verified commit.
5. Push the tag and create a GitHub Release with `--verify-tag`.
6. Confirm the remote tag, release target, release notes, and downloadable
   source archives.
