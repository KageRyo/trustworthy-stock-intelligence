# Release Checklist

## 0.3.2 Scope

`0.3.2` is a maintenance and security release following the public
open-source and research-quality `0.3.1` release:

- SHA-pinned CodeQL Action v4 workflow and continued security scanning gates
- explicit Ruff 0.16 migration with the existing lint baseline preserved
- grouped routine Dependabot minor and patch updates by ecosystem
- validated frontend dependency upgrades, including TypeScript 7 and Zod 4
- restored official Apache License 2.0 text
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

## Release Procedure

1. Prepare the version and changelog changes on a release branch.
2. Merge the release PR only after all required checks pass.
3. Confirm the merge commit is the current `main` head and rerun all checks.
4. Create an annotated `vX.Y.Z` tag on that verified commit.
5. Push the tag and create a GitHub Release with `--verify-tag`.
6. Confirm the remote tag, release target, release notes, and downloadable
   source archives.
