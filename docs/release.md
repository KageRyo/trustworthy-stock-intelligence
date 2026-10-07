# Maintainer Release Checklist

## 0.7.0 Scope

`0.7.0` changes the served baseline's features:

- Serving defaults to `--feature-set technical_range`. It adds split-adjusted Parkinson and
  Garman-Klass volatility, ATR(14) as a share of price, 20-day volatility, and drawdown from the
  20-day high to the 7 technical features. The batch `model_bundle` records the feature set.
- Experiment 017 compared feature sets on identical purged walk-forward folds:
  - Range features raised AUC by 0.023 to 0.029 on S&P 100, on 402 held-out S&P 500 tickers, and on
    53 Taiwan large caps.
  - Market regime features (SPY return and drawdown, VIX) lowered AUC and alert recall, so serving
    does not use them.
  - A 60-day beta helped slightly in the US only and needs a serving reference-data path, so it
    stays experimental.
- Reruns of Experiments 015 and 016 with the new set keep `alert_rate:0.05` and the rule that
  uncertainty never blocks alerts.
- `--feature-set technical` reproduces the previous features.

Issue #29 remains open.

## 0.6.0 Scope

`0.6.0` changes how alert and watch thresholds are chosen:

- Serving defaults to calibration-window alert-rate policies: `--alert-policy alert_rate:0.05` and
  `--watch-policy alert_rate:0.2`. These replace the F1 threshold and the fixed 0.8 watch ratio.
- Experiment 016 showed:
  - Precision targets do not transfer to test windows.
  - The 5% alert-rate cap beats F1 precision in 85% of folds and cuts alert days per ticker-month
    from 6.75 to 1.67.
  - Recall falls from 0.52 to 0.20; the watch tier covers 0.40.
- Batches, the Go analysis API, and the dashboard expose `alert_policy` metadata. Small calibration
  windows are flagged as noisy.
- Ticker analysis reads calibration-drift and alert-policy metadata from the record's own batch.
- `--alert-policy objective --watch-policy ratio` reproduces the previous thresholds.

Issue #29 remains open.

## 0.5.0 Scope

`0.5.0` changes the meaning of the served `trust_score` and `uncertainty_score`:

- `uncertainty_score` comes from bootstrap-ensemble disagreement and feature novelty, ranked against
  the calibration window.
- `trust_score` comes from per-ticker data quality and calibration drift, not from the risk
  probability.
- Experiment 015 showed that epistemic uncertainty must not gate alerts, so it only moves
  below-watch rows to abstain.
- Alert volume increases at unchanged precision because the previous trust gate was a hidden second
  probability threshold.
- `--trust-method legacy` reproduces the previous serving behavior.

The release also migrates the dashboard to Tailwind CSS v4 to clear npm audit advisories, refreshes
torch 2.14 and security-patched Python dependencies, and confines the selective-trust experiment
output path. Issue #29 remains open.

## 0.4.4 Python Package Scope

`0.4.4` is a backward-compatible dependency-maintenance release following the `0.4.3` Python package
release. It refreshes the Go, frontend, and GitHub Actions dependency baselines, including Vitest
5.0.1 and SHA-pinned CodeQL updates, while keeping the Python package, Go API, PostgreSQL, and
TypeScript boundaries explicit. Issue #29 remains open because licensed historical constituents,
inactive/delisted OHLCV, rights review, and a real paired benchmark are still required for a
research claim.

Before tagging the release:

```bash
uv sync --locked --extra dev --extra data --extra deep
uv run --locked --no-sync python -m pytest
uv run --locked --no-sync python -m ruff check src tests scripts dashboard
uv run --locked --no-sync python -m build
uv run --locked --no-sync python -m twine check dist/*
uv run --locked --no-sync python -m tsi --version
```

Configure PyPI's Trusted Publisher with owner `KageRyo`, repository
`trustworthy-stock-intelligence`, workflow filename `release.yml`, and GitHub environment `pypi`.
The workflow is stored in the repository at `.github/workflows/release.yml`. It verifies that the
tag version matches `pyproject.toml`, publishes the wheel and sdist, and creates the GitHub Release
only after PyPI succeeds. See [`python-package.md`](python-package.md) for the initial
pending-publisher setup and package boundary.

The package-only release sequence is:

```bash
git tag -a v0.7.0 -m "release: v0.7.0"
git push origin v0.7.0
```

## 0.4.0 Scope

`0.4.0` is the product-readiness release following the `0.3.2` maintenance and security release:

- scheduled five-minute watchlist ingestion with provider health and coverage
- actionable freshness/stale policy and queue-backed prediction jobs
- deterministic warning transitions and typed job status/failure responses
- dashboard operational states and richer session-scoped watchlists
- readiness, structured observability, metrics, and deterministic PostgreSQL watchlist-to-warning
  E2E coverage

The release does not claim a high-precision warning policy, a trading edge, all-market coverage,
point-in-time historical membership, or externally validated cross-market suitability. Issue #29
remains open because the actual licensed historical constituent archive and comparable benchmark
rerun are not present in the repository.

## Version Files

Update:

```text
pyproject.toml
frontend/stock-dashboard/package.json
frontend/stock-dashboard/package-lock.json
frontend/stock-dashboard/README.md
dashboard/README.md
docs/api/openapi.yaml
services/api-gateway-go/internal/http/openapi.yaml
services/api-gateway-go/README.md
README.md
CITATION.cff
docs/environment.md
docs/project_roadmap.md
docs/demo/local_demo.md
CHANGELOG.md
docs/release.md
```

## Required Checks

```bash
uv run --locked --no-sync python -m pytest
uv run --locked --no-sync python -m ruff check src tests scripts dashboard
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

The CI `Watchlist-to-warning E2E` job additionally starts PostgreSQL 17, applies all migrations,
runs the deterministic fake-provider pipeline, starts the Go API, and validates the captured
response with the frontend Zod schema. It must be green before the release merge.

## Release Procedure

1. Prepare the version and changelog changes on a release branch.
1. Merge the release PR only after all required checks pass.
1. Confirm the merge commit is the current `main` head and rerun all checks.
1. Create an annotated `v0.7.0` tag on that verified commit.
1. Push the tag and create a GitHub Release with `--verify-tag`.
1. Confirm the remote tag, release target, release notes, and downloadable source archives.
