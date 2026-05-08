# Environment

## Recommendation

Use a two-layer setup:

```text
conda: creates the machine-level Python 3.11 GPU environment
uv: manages fast Python package installation from pyproject.toml
```

For this project, `pyproject.toml` is the canonical dependency definition. The file already exists at the repository root.

The practical recommendation is:

```text
Use conda once to create /mnt/8tb_hdd/ryo/miniconda3/envs/stock.
Use uv or pip inside that environment to install project dependencies.
Install PyTorch CUDA with an explicit CUDA wheel index.
```

## Local Conda Environment

The local research environment is:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock
```

Create it with:

```bash
/mnt/8tb_hdd/ryo/miniconda3/bin/conda create -n stock python=3.11 -y
```

## uv

`uv` is installed in the `stock` environment:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/uv
```

Install `uv` if needed:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install uv
```

Recommended project install with `uv`:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/uv pip install \
  --python /mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python \
  -e ".[dev,models,explainability,viz,notebooks,cli,data]"
```

`uv` is preferred for normal dependency sync because it is faster and resolves packages consistently. Conda is still useful here because the machine already has a shared Miniconda installation and GPU-oriented environments under `/mnt/8tb_hdd/ryo/miniconda3`.

## General Research Libraries

Install the project and research dependencies with pip if not using `uv`:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install -e ".[dev,models,explainability,viz,notebooks,cli,data]"
```

This includes:

```text
numpy
pandas
scikit-learn
scipy
pydantic
pyarrow
duckdb
polars
yfinance
xgboost
lightgbm
imbalanced-learn
statsmodels
optuna
shap
matplotlib
seaborn
plotly
jupyterlab
ipykernel
tensorboard
pytest
ruff
uv
```

## PyTorch CUDA

This machine has two NVIDIA GeForce RTX 4090 GPUs. `nvidia-smi` reports CUDA 12.8, so install PyTorch with the CUDA 12.8 wheel:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
```

Verify CUDA availability:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

Expected device count on this machine:

```text
2
```

## Notes

PyTorch is installed with an explicit CUDA wheel command instead of relying only on `pip install -e ".[deep]"`, because CUDA wheel selection should be documented for GPU reproducibility.

If using `uv` for the full environment including deep learning dependencies, pass both the Python target and the PyTorch CUDA index explicitly:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/uv pip install \
  --python /mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python \
  -e ".[dev,models,explainability,viz,notebooks,cli,data,deep]" \
  --extra-index-url https://download.pytorch.org/whl/cu128
```

Avoid using bare `uv pip install --system` on this machine, because it may target the base conda environment instead of `stock`.

## Verified Local Versions

The local `stock` environment has been verified with:

```text
Python: 3.11.15
PyTorch: 2.11.0+cu128
CUDA available in PyTorch: True
CUDA device count: 2
GPU 0: NVIDIA GeForce RTX 4090
GPU 1: NVIDIA GeForce RTX 4090
uv: 0.11.11
```

Core research packages installed:

```text
numpy
pandas
scikit-learn
scipy
pydantic
pydantic-settings
pyarrow
yfinance
xgboost
lightgbm
shap
matplotlib
seaborn
plotly
jupyterlab
notebook
ipykernel
pytest
ruff
```
