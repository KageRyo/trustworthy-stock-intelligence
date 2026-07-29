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

## Security Boundary

The current product has no authentication boundary. Browser session identifiers
organize watchlist state but are not credentials. PostgreSQL credentials,
provider keys, private holdings, and future user data must remain outside the
repository and outside client-side bundles.
