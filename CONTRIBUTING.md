# Contributing

Thanks for helping improve Trustworthy Stock Intelligence. The project is an
active research prototype for human-in-the-loop drawdown-risk analysis; it is
not an investment-advice or automated-trading system.

## Before You Start

- Read the [development guide](docs/development.md),
  [roadmap](docs/project_roadmap.md), and
  [public/private boundary](docs/public_private_boundary.md).
- Do not commit `.env` files, credentials, downloaded provider data, database
  dumps, model weights, generated caches, or private user data.
- Keep API, provider, CLI, and frontend boundaries schema-first. Tickers are
  identifiers and must remain strings, including Taiwan codes with leading
  zeroes or suffix letters.

## Local Checks

Run the checks relevant to your change. Before a cross-stack change, run the
full set:

```bash
uv sync --locked --extra dev --extra data --extra db --extra dashboard --extra deep
uv run --locked --no-sync python -m pytest
uv run --locked --no-sync python -m ruff check src tests scripts dashboard

cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go vet ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go run golang.org/x/vuln/cmd/govulncheck@v1.6.0 ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=1 go test -race ./...

cd ../../frontend/stock-dashboard
npm ci
npm test -- --run
npm run build
npm audit --audit-level=moderate
```

Research changes should also record the data fingerprint, temporal split,
purging/label-overlap checks, calibration protocol, metrics, and limitations.
Do not compare models using different data windows or validation rules.

## Issues and Pull Requests

Open an issue before a large change when the scope or research question is not
already tracked. A pull request should describe the goal, key changes, tests,
data/artifact assumptions, and any known limitations. Link the relevant issue.

Use small commits with this format:

```text
type(scope): summary
```

Common types include `feat`, `fix`, `docs`, `test`, `refactor`, and `chore`.

## Security

Never place credentials or private data in an issue or pull request. For a
vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening a public
issue with exploit details or secrets.
