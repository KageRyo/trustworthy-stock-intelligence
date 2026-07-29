# Recommended Repository Settings

These settings cannot be enforced by files in the repository. Apply them in
GitHub after the workflows on `main` have completed at least once.

## Branches

- Default branch: `main`.
- Observed remote branches on 2026-07-29: `main` only.
- Use `main` for normal development. Add `develop` only when a real Git Flow
  collaboration need exists.

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
- require CodeQL results for Python, Go, and JavaScript/TypeScript

For a solo-maintainer repository, required approvals can remain at zero while
the pull-request and CI gates remain active. Raise the approval count when
another regular reviewer is available.

## Security And Dependencies

- keep Dependabot alerts and security updates enabled
- commit `.github/dependabot.yml` to enable scheduled version-update PRs
- keep secret scanning and push protection enabled
- use the committed CodeQL advanced workflow; do not enable CodeQL default
  setup at the same time
- review `npm audit --audit-level=moderate` in CI

Public repositories receive GitHub secret scanning, but push protection and
repository-specific policy still need to be verified in the GitHub settings UI.

## Releases

- create annotated release tags for user-visible releases
- keep `CHANGELOG.md` updated under `Unreleased` before cutting a tag
- existing local tags at this review: `v0.1.0`, `v0.2.0`
