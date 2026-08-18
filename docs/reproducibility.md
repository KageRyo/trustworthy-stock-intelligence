# Reproducibility

## Goal

The repository should support reproducible research experiments for stock risk early-warning.
Reproducibility is especially important because financial results can change due to data vendor
adjustments, survivorship bias, split choices, and leakage.

## Required Experiment Metadata

Each experiment report should record:

```text
experiment id
date executed
git commit hash
dataset config
data source
download date
input artifact SHA-256
date range
stock universe
feature set
label definition
label end date
split protocol
purge size and overlap-removal counts
model configuration
calibration method
warning thresholds
random seed
metrics
known limitations
```

## Data Versioning

Pilot experiments may use Yahoo Finance. Reports must state that Yahoo Finance data is used for
pilot research only.

Formal research should prefer:

```text
WRDS/CRSP
Polygon
Tiingo
official exchange data
```

Because adjusted historical data can change, experiments should record the data download date and
vendor.

## Randomness

All stochastic models should use documented seeds. Randomness may appear in:

- train-validation fold construction
- model initialization
- bootstrapping
- random forests
- XGBoost training
- calibration procedures

## Temporal Integrity

The following must be reproducible and auditable:

- feature windows
- label horizon
- train/calibration/test windows
- threshold tuning window
- normalization fitting window

No transform should be fit on the full dataset before temporal splitting.

## Environment

`pyproject.toml` defines dependency ranges, `.python-version` selects the maintainer/CI Python, and
`uv.lock` records the exact resolution. Reproduce the CPU environment with:

```bash
uv sync --locked \
  --extra dev \
  --extra models \
  --extra explainability \
  --extra viz \
  --extra notebooks \
  --extra data \
  --extra deep
```

For a CUDA 12.6 experiment, replace `--extra deep` with `--extra deep-cu126`. Never enable both
profiles. Record `torch.__version__`, `torch.version.cuda`, device names and device count in every
GPU run. Historical CUDA 12.8 results retain their original environment metadata rather than being
silently reclassified as CUDA 12.6 runs.

## Reporting Standard

Reports should distinguish:

```text
pilot result
main v0 result
formal v1 result
benchmark comparison
```

Pilot results are useful for debugging the research workflow, but they should not be overstated as
final evidence.
