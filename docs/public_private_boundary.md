# Public And Private Boundary

## Public By Default

- source code and tests
- typed schemas, OpenAPI, and synthetic payload examples
- architecture diagrams without hostnames, IP addresses, credentials, or
  internal topology
- aggregate research metrics, experiment protocols, model cards, and dataset
  fingerprints
- synthetic sample data and API mocks
- changelog and release tags

## Private By Default

- `.env`, credentials, API keys, private certificates, and database URLs
- raw/downloaded provider data and provider response archives
- PostgreSQL dumps, warning rows tied to private portfolios, and operational
  logs
- model weights unless training-data and base-model rights are cleared
- user holdings, personal data, browser-session mappings, and future account
  data
- internal hostnames, public/static IP addresses, filesystem paths, deployment
  inventory, firewall details, and non-public monitoring endpoints
- unpublished research data and commercial delivery artifacts

## Repository Controls

- `.gitignore` excludes `.env`, raw data, derived artifacts, caches, and model
  run predictions.
- `.env.example` uses placeholders only.
- public run reports commit aggregate metrics and hashes, not raw OHLCV or
  prediction rows.
- Ruff, `go vet`, TypeScript typechecking, Dependabot, CI dependency audit,
  secret scanning, and push protection should all be active.
- Add CodeQL when the repository is public or GitHub Code Security is enabled
  for the private repository.
- Documentation uses `<dashboard-host>`, `<repo-root>`, and similar placeholders
  instead of an actual deployment address.

Before making any artifact public, verify both content sensitivity and license
rights. A file being technically reproducible does not make it redistributable.
