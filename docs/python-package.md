# Python Package

## Scope

`trustworthy-stock-intelligence` is distributed on PyPI as the reusable Python and ML core of this
repository. The wheel contains `tsi` modules for:

- leakage-aware OHLCV feature and future-drawdown label construction
- baseline logistic and tree risk models
- calibration-aware evaluation and warning metrics
- uncertainty, trust-score, reason, and decision utilities
- Pydantic serving schemas and freshness metadata

The Go API, PostgreSQL schema and workers, TypeScript dashboard, Docker Compose stack, and
downloaded market data are not bundled into the wheel.

## Install

The base package supports offline artifact work and core model/evaluation use:

```bash
python -m pip install trustworthy-stock-intelligence
```

Install provider and universe-ingestion dependencies when downloading market data:

```bash
python -m pip install "trustworthy-stock-intelligence[data]"
```

Other optional surfaces are intentionally explicit:

```bash
python -m pip install "trustworthy-stock-intelligence[db]"     # PostgreSQL adapter
python -m pip install "trustworthy-stock-intelligence[models]"  # tree/boosting research tools
python -m pip install "trustworthy-stock-intelligence[deep]"    # PyTorch model bundles/training
```

The published `deep` extra records compatible PyTorch package families. In a uv checkout, `deep`
selects CPU wheels for CI and `deep-cu126` selects CUDA 12.6 wheels; they cannot be enabled
together. GPU users should follow the explicit profile and driver guidance in
[`environment.md`](environment.md).

## Python API

The top-level imports are deliberately small and stable:

```python
from tsi import (
    LogisticRiskModel,
    add_future_drawdown_label,
    build_technical_features,
    classification_metrics,
    compute_trust_score,
    read_ohlcv_csv,
)

ohlcv = read_ohlcv_csv("ohlcv.csv")
featured = build_technical_features(ohlcv)
labeled = add_future_drawdown_label(featured, horizon=5, threshold=-0.05)

model = LogisticRiskModel().fit(
    labeled.dropna(subset=["risk_label"])[["return_1d", "return_5d"]]
    .fillna(0.0)
    .to_numpy(),
    labeled.dropna(subset=["risk_label"])["risk_label"].astype(int).to_numpy(),
)
```

The package functions do not claim causal explanations or investment advice. Labels use future
observations by design and must only be used after a leakage-aware temporal split in an experiment.

## CLI

The CLI is deterministic and local; it does not start the API or silently call a market-data
provider:

```bash
tsi --version
tsi version
tsi inspect-csv data/raw/sp100/ohlcv.csv --json
tsi evaluate predictions.csv \
  --label-column risk_label \
  --probability-column calibrated_risk_probability \
  --threshold 0.25 \
  --json
```

The full ticker-driven lookup path remains the Go API's local on-demand bridge and the
production-oriented ingestion/worker flow; see the main README and `docs/architecture.md` for those
boundaries.

## Local package checks

From a clean checkout:

```bash
uv sync --locked --extra dev --extra data
uv run --locked --no-sync python -m pytest tests/test_cli.py
uv run --locked --no-sync python -m ruff check src tests scripts dashboard
uv run --locked --no-sync python -m build
uv run --locked --no-sync python -m twine check dist/*
uv run --locked --no-sync python -m tsi --version
```

The release workflow repeats the build and metadata checks on a `vX.Y.Z` tag, then publishes the
exact wheel and sdist through PyPI Trusted Publishing before creating the GitHub Release.

## Trusted Publishing setup

Before the first tag-triggered release, configure a PyPI Trusted Publisher for the project name
`trustworthy-stock-intelligence`:

```text
owner:       KageRyo
repository:  trustworthy-stock-intelligence
workflow:    release.yml
environment: pypi
```

In the repository, the workflow is stored at `.github/workflows/release.yml`; PyPI's **Workflow
name** field expects only the filename `release.yml`. If the project does not exist on PyPI, choose
**Publishing → Add a new pending publisher** and also enter the project name
`trustworthy-stock-intelligence`. If the project already exists, add the same values under that
project's **Publishing** settings instead.

Use the `pypi` GitHub environment named by the workflow. No long-lived PyPI token belongs in
repository secrets. If the project does not exist on PyPI yet, use PyPI's pending-publisher flow for
the initial release, then verify the project publisher configuration before pushing the release tag.

The release command is intentionally separate from ordinary CI:

```bash
git tag -a v0.4.2 -m "release: v0.4.2"
git push origin v0.4.2
```

Only tag a verified commit after the pull request/branch checks are green. A failed PyPI publish
stops the workflow before a GitHub Release is created.
