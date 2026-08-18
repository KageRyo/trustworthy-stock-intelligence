# Public And Private Boundary

The GitHub repository is public as of 2026-08-09. Public source does not make local market-data
downloads, credentials, deployments, or user-specific state public or redistributable.

## Public By Default

- source code and tests
- typed schemas, OpenAPI, and synthetic payload examples
- architecture diagrams without hostnames, IP addresses, credentials, or internal topology
- aggregate research metrics, experiment protocols, model cards, and dataset fingerprints
- synthetic sample data and API mocks
- changelog and release tags
- contribution and citation metadata that identify the public software

## Private By Default

- `.env`, credentials, API keys, private certificates, and database URLs
- raw/downloaded provider data and provider response archives
- PostgreSQL dumps, warning rows tied to private portfolios, and operational logs
- model weights unless training-data and base-model rights are cleared
- user holdings, personal data, browser-session mappings, and future account data
- internal hostnames, public/static IP addresses, filesystem paths, deployment inventory, firewall
  details, and non-public monitoring endpoints
- unpublished research data and commercial delivery artifacts

## Repository Controls

- `.gitignore` excludes `.env`, raw data, derived artifacts, caches, and model run predictions.
- `.env.example` uses placeholders only.
- public run reports commit aggregate metrics and hashes, not raw OHLCV or prediction rows.
- Ruff, `go vet`, pinned `govulncheck`, Go race tests, TypeScript typechecking, Dependabot, CI
  dependency audit, the SHA-pinned Gitleaks history scan, and the SHA-pinned CodeQL workflow should
  all be active.
- Native GitHub Secret Scanning and Push Protection are enabled and were verified in repository
  settings on 2026-08-09. Gitleaks remains the repository-level full-history scan and complementary
  control.
- Branch protection and required checks are recorded in `.github/REPOSITORY_SETTINGS.md`; the
  settings should be re-verified after changes to workflow names.
- Documentation uses `<dashboard-host>`, `<repo-root>`, and similar placeholders instead of an
  actual deployment address.

Before making any artifact public, verify both content sensitivity and license rights. A file being
technically reproducible does not make it redistributable. The current history audit found research
notebooks and aggregate experiment CSVs but no environment files, credentials, private keys,
database files, or model weights. An older commit author email is documented for review; no history
rewrite is performed by default.
