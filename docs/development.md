# Development Guide

## Principles

- Keep API and CLI payloads schema-first. JSON examples in docs must correspond
  to Go structs, Pydantic models, Zod schemas, or OpenAPI schemas.
- PostgreSQL is required for API startup. Do not add a hidden file fallback for
  the Go API serving path.
- Preserve ticker symbols as strings. This is required for Taiwan leading zeroes
  and suffix letters such as `00981A` and `02001L`.
- Keep Python responsible for data science, feature engineering, training,
  calibration, uncertainty, trust scoring, and prediction writes.
- Keep Go responsible for PostgreSQL-backed API serving, watchlists, CORS,
  OpenAPI, and typed dashboard responses.
- Keep TypeScript responsible for UI state, runtime schema validation, i18n, and
  presentation.
- Do not commit `.env`, downloaded data, model bundles, generated caches, or
  local artifact outputs.

## Tests

Run focused tests while developing and the full relevant suite before commit:

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
npm audit --audit-level=moderate
```

Coverage priorities:

- temporal split and leakage-sensitive Python logic
- provider payload schemas and Taiwan ticker normalization
- PostgreSQL write/read behavior and migrations
- Go API error envelopes, CORS, OpenAPI, watchlists, and ticker analysis
- frontend Zod schemas, API adapters, i18n, and dashboard rendering states

## CI

GitHub Actions workflow:

```text
.github/workflows/ci.yml
```

CI runs:

- Python tests and Ruff
- Go API tests
- frontend Vitest tests, production build, and moderate dependency audit
- separate CodeQL analysis for Python, Go, and JavaScript/TypeScript

The CI badge in `README.md` points to the latest workflow result on GitHub.

## Commit Policy

Use:

```text
type(scope): summary
```

Examples:

```text
feat(api): add on-demand ticker analysis
fix(data): preserve taiwan ticker symbols
docs(release): document 0.2.0 dashboard workflow
```

Common types:

```text
feat
fix
docs
test
refactor
chore
```

Commit in tested slices. Do not batch unrelated work into the same commit just
because files are locally modified.

## Release Checklist

For a version release:

1. Update `pyproject.toml`.
2. Update `frontend/stock-dashboard/package.json` and lockfile.
3. Update OpenAPI `info.version` in both API specs.
4. Update README badges and `CHANGELOG.md`.
5. Run Python, Go, and frontend checks.
6. Commit with a `chore(release): bump version to X.Y.Z` message.
7. Tag with `vX.Y.Z`.
8. Push the branch and tag.

See `docs/release.md` for the command checklist.
