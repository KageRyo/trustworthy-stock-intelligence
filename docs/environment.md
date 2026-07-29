# Environment

## Runtime Targets

| Component | Version |
| --- | --- |
| Python package | `0.2.0` |
| Python | `>=3.10`, CI uses `3.11` |
| Go API | `1.25.x` |
| Node.js CI runtime | `22.x` |
| TypeScript | `5.6.x` |
| PostgreSQL container | `17-alpine` |

## Recommendation

Use a two-layer setup:

```text
conda: creates the machine-level Python 3.11 GPU environment
uv: manages fast Python package installation from pyproject.toml
```

For this project, `pyproject.toml` is the canonical dependency definition. The file already exists at the repository root.

The practical recommendation is to create a named conda environment, activate
it, use `uv` or pip for project dependencies, and install PyTorch from the CUDA
wheel index that matches the machine.

## Local Conda Environment

Create and activate it with:

```bash
conda create -n stock python=3.11 -y
conda activate stock
```

## uv

Install `uv` if needed:

```bash
python -m pip install uv
```

Recommended project install with `uv`:

```bash
uv pip install -e ".[dev,models,explainability,viz,notebooks,cli,data]"
```

`uv` is preferred for normal dependency sync because it is fast and resolves
packages consistently. Conda remains useful for a named, GPU-oriented Python
environment.

## General Research Libraries

Install the project and research dependencies with pip if not using `uv`:

```bash
python -m pip install -e ".[dev,models,explainability,viz,notebooks,cli,data]"
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
python -m pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
```

Verify CUDA availability:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

Expected device count on this machine:

```text
2
```

## Notes

PyTorch is installed with an explicit CUDA wheel command instead of relying only on `pip install -e ".[deep]"`, because CUDA wheel selection should be documented for GPU reproducibility.

If using `uv` for the full environment including deep learning dependencies, pass both the Python target and the PyTorch CUDA index explicitly:

```bash
uv pip install \
  -e ".[dev,models,explainability,viz,notebooks,cli,data,deep]" \
  --extra-index-url https://download.pytorch.org/whl/cu128
```

Avoid `uv pip install --system`; activate the intended environment explicitly.

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
