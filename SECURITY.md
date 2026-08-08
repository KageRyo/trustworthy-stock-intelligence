# Security Policy

## Supported Versions

Security fixes target the latest release and `main`. Older research snapshots
are retained for reproducibility but are not maintained as deployable versions.

## Reporting A Vulnerability

Use GitHub's private security-advisory reporting flow when available. Do not
open a public issue containing credentials, exploit details, private data, or
internal deployment information.

If a secret is exposed:

1. revoke or rotate it immediately
2. remove it from active configuration
3. assess logs and downstream systems for use
4. clean repository history only after preserving required forensic evidence

## Repository Security Controls

The source repository is public. The repository uses required CI checks,
Dependabot updates, a full-history Gitleaks workflow, and a SHA-pinned CodeQL
workflow for Go, JavaScript/TypeScript, and Python. Native GitHub Secret
Scanning and Push Protection are managed in repository settings and must be
verified there; they are not implied by the presence of a workflow file.

The current public-history review found research notebooks and aggregate
experiment CSVs, but no `.env` files, credentials, private keys, database
files, or model weights. Do not add raw provider downloads or private
operational artifacts to the repository.

## Security Boundary

The current product has no authentication boundary. Browser session identifiers
organize watchlist state but are not credentials. PostgreSQL credentials,
provider keys, private holdings, and future user data must remain outside the
repository and outside client-side bundles.
