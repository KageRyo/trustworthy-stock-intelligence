# Release Checklist

## 0.3.0 Scope

`0.3.0` is the research-evidence-hardening release:

- purged walk-forward train/calibration/test boundaries
- per-row `label_end_date` leakage controls
- ECE, Brier score, false-discovery metrics, and no-feature baselines
- reproducible Experiment 007 evidence and artifact fingerprints
- per-fold Platt AUC invariance and ranking diagnostics
- explicit pilot-evidence, limitations, and data/model licensing boundaries
- patched Python, Go, npm, and GitHub Actions dependencies
- required CI, Dependabot, `govulncheck`, race tests, and Gitleaks history scans
- SHA-pinned, Node 24-compatible GitHub Actions

The release does not claim a high-precision warning policy, a trading edge, or
cross-market external validity.

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
