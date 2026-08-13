# Trustworthy Stock Intelligence

`trustworthy-stock-intelligence` is a Python package for leakage-aware stock
drawdown-risk research. It provides reusable feature, labeling, baseline-model,
evaluation, uncertainty, trust-score, and serving-schema primitives.

This distribution is the Python/ML core of the larger
[Trustworthy Stock Intelligence repository](https://github.com/KageRyo/trustworthy-stock-intelligence).
The Go API, PostgreSQL workers, TypeScript dashboard, Docker Compose stack, and
market-data artifacts are separate surfaces and are not included in this wheel.

## Install

```bash
python -m pip install trustworthy-stock-intelligence
```

Install provider and universe-ingestion support only when needed:

```bash
python -m pip install "trustworthy-stock-intelligence[data]"
```

Optional model/runtime groups are explicit:

```bash
python -m pip install "trustworthy-stock-intelligence[models]"
python -m pip install "trustworthy-stock-intelligence[deep]"
python -m pip install "trustworthy-stock-intelligence[db]"
```

The `deep` extra records the PyTorch dependency. For CUDA installations,
follow the [GPU environment guide](https://github.com/KageRyo/trustworthy-stock-intelligence/blob/main/docs/environment.md)
and install the wheel index matching the target host.

## Python API

```python
from tsi import (
    add_future_drawdown_label,
    build_technical_features,
    classification_metrics,
    read_ohlcv_csv,
)
import numpy as np

ohlcv = read_ohlcv_csv("ohlcv.csv")
featured = build_technical_features(ohlcv)
labeled = add_future_drawdown_label(featured, horizon=5, threshold=-0.05)

# Future labels must be separated with a leakage-aware temporal split before
# training or evaluating a model. A metrics call receives model probabilities:
metrics = classification_metrics(
    np.array([0, 1]),
    np.array([0.10, 0.90]),
)
```

Top-level exports include `LogisticRiskModel`, `TreeRiskModel`, technical
features, future drawdown labels, warning-level selection, calibration-aware
metrics, uncertainty functions, trust scores, and Pydantic serving schemas.
Ticker symbols remain strings, so values such as `0050` and `00981A` retain
their leading zeroes and suffixes.

## CLI

The package exposes a deterministic local CLI. It reads local artifacts and does
not silently call a provider or start the full application:

```bash
tsi --version
tsi inspect-csv path/to/ohlcv.csv --json
tsi evaluate predictions.csv \
  --label-column risk_label \
  --probability-column calibrated_risk_probability \
  --threshold 0.25 \
  --json
```

## Scope and limitations

This package supports trustworthy-ML engineering and reproducible pilot
research. It is not investment advice, a price-prediction guarantee, an
automated trading system, or evidence of externally validated performance.
Labels intentionally use future observations; temporal splitting, calibration
protocols, data provenance, provider terms, and survivorship-bias limitations
remain the responsibility of each experiment.

See the [package guide](https://github.com/KageRyo/trustworthy-stock-intelligence/blob/main/docs/python-package.md)
for the full API boundary, extras, local checks, and release process. See the
[main README](https://github.com/KageRyo/trustworthy-stock-intelligence#readme)
for the complete operational prototype.
