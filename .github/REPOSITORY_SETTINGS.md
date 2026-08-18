# Repository Governance and Security Settings

This document is public maintainer guidance. It records which controls should be enabled for the
open-source repository and which settings must be verified in GitHub's UI/API; it is not required
for ordinary package or dashboard users.

These settings cannot be enforced by files in the repository. Apply and re-verify them in GitHub
after workflow names or repository visibility change.

Verified on 2026-08-09:

- repository visibility is `public`
- `main` requires pull requests, conversation resolution, the three CI jobs, and the Gitleaks secret
  scan; force pushes, deletion, and administrator bypass are disabled; required approvals remain at
  zero for solo maintenance
- Dependabot vulnerability alerts and automatic security updates are enabled
- CodeQL passed on PR #30 for Go, JavaScript/TypeScript, and Python; its checks should be added to
  the required branch gates after the next successful run on `main`
- native Secret Scanning and Push Protection are enabled

## Branches

- Default branch: `main`.
- Observed remote branches on 2026-07-29: `main` only.
- Use `main` for normal development. Add `develop` only when a real Git Flow collaboration need
  exists.

## Main Ruleset

Target `main` and configure:

- require a pull request before merging
- require conversation resolution
- block force pushes
- block branch deletion
- require branches to be up to date before merging
- require these uniquely named CI checks:
  - `Python tests and lint`
  - `Go API tests`
  - `Frontend tests and build`
  - `Gitleaks secret scan`

For a solo-maintainer repository, required approvals can remain at zero while the pull-request and
CI gates remain active. Raise the approval count when another regular reviewer is available.

## Security And Dependencies

- keep Dependabot alerts and security updates enabled
- commit `.github/dependabot.yml` to enable scheduled version-update PRs
- keep the committed Gitleaks history scan required; its third-party actions are pinned to immutable
  commit SHAs
- keep Ruff, `go vet`, pinned `govulncheck`, Go race tests, and the TypeScript production-build
  typecheck required
- keep the CodeQL workflow enabled for Python, Go, and JavaScript/TypeScript; require its checks
  after the workflow has completed successfully on `main`
- native GitHub Secret Scanning and repository Push Protection are enabled; re-check them after
  changes to repository visibility or security policy
- review `npm audit --audit-level=moderate` in CI

Native scanning status was verified through the repository API on 2026-08-09.

## Releases

- create annotated release tags for user-visible releases
- keep `CHANGELOG.md` updated under `Unreleased` before cutting a tag
- existing local tags at this review: `v0.1.0`, `v0.2.0`
