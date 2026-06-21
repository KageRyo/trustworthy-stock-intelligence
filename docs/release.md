# Release Checklist

## 0.2.0 Scope

`0.2.0` marks the first initially usable stock-risk dashboard release:

- PostgreSQL-backed serving source of truth
- Go API with Swagger/OpenAPI
- TypeScript dashboard with English and 正體中文
- browser-session watchlists
- on-demand ticker analysis
- US and Taiwan ticker handling, including alphanumeric Taiwan codes and TPEx
  emerging fallback
- schema-first tests across Python, Go, and frontend adapters

## Version Files

Update:

```text
pyproject.toml
frontend/stock-dashboard/package.json
frontend/stock-dashboard/package-lock.json
docs/api/openapi.yaml
services/api-gateway-go/internal/http/openapi.yaml
README.md
CHANGELOG.md
LICENSE
docs/README.md
docs/user_guide.md
docs/development.md
docs/release.md
```

## Required Checks

```bash
python -m pytest
python -m ruff check src tests scripts dashboard
cd services/api-gateway-go
GOCACHE=/tmp/tsi-go-build-cache CGO_ENABLED=0 go test ./...
cd ../../frontend/stock-dashboard
npm test -- --run
npm run build
```

## Git Commands

```bash
git status -sb
git add README.md CHANGELOG.md LICENSE docs .github/workflows/ci.yml pyproject.toml frontend/stock-dashboard/package.json frontend/stock-dashboard/package-lock.json docs/api/openapi.yaml services/api-gateway-go/internal/http/openapi.yaml
git commit -m "docs(release): prepare 0.2.0 documentation"
git tag v0.2.0
git push origin main
git push origin v0.2.0
```
