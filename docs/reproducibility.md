# Reproducibility

## Goal

The repository should support reproducible research experiments for stock risk early-warning. Reproducibility is especially important because financial results can change due to data vendor adjustments, survivorship bias, split choices, and leakage.

## Required Experiment Metadata

Each experiment report should record:

```text
experiment id
date executed
git commit hash
dataset config
data source
download date
date range
stock universe
feature set
label definition
split protocol
model configuration
calibration method
warning thresholds
random seed
metrics
known limitations
```

## Data Versioning

Pilot experiments may use Yahoo Finance. Reports must state that Yahoo Finance data is used for pilot research only.

Formal research should prefer:

```text
WRDS/CRSP
Polygon
Tiingo
official exchange data
```

Because adjusted historical data can change, experiments should record the data download date and vendor.

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

The project uses `pyproject.toml` as the canonical dependency entry point.

Suggested environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,models,explainability]"
```

The local GPU research environment on this machine is:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock
```

It is created with Python 3.11:

```bash
/mnt/8tb_hdd/ryo/miniconda3/bin/conda create -n stock python=3.11 -y
```

`pyproject.toml` is the canonical dependency definition for this repository. The recommended workflow is to use `uv` inside the `stock` environment:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install uv
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/uv pip install \
  --python /mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python \
  -e ".[dev,models,explainability,viz,notebooks,cli,data]"
```

Plain pip is also valid:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install -e ".[dev,models,explainability,viz,notebooks,cli,data]"
```

Install PyTorch with the CUDA wheel that matches the local NVIDIA driver/runtime. On this machine, `nvidia-smi` reports CUDA 12.8, so the pilot environment uses:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
```

The `deep` extra records the Python package requirement, but explicit PyTorch CUDA installation is preferred for reproducibility on GPU machines.

## Reporting Standard

Reports should distinguish:

```text
pilot result
main v0 result
formal v1 result
benchmark comparison
```

Pilot results are useful for debugging the research workflow, but they should not be overstated as final evidence.
