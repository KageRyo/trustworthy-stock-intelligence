# Development and Runtime Environment

## Runtime Targets

| Component | Version |
| --- | --- |
| Python package | `0.4.1` |
| Python | `>=3.10`, CI uses `3.11` |
| Go API | `1.25.x` |
| Node.js CI runtime | `22.x` |
| TypeScript | `7.0.x` |
| PostgreSQL container | `17-alpine` |

## Recommended setup

Use a two-layer setup:

```text
conda: creates an isolated Python environment
uv: manages fast dependency installation from pyproject.toml
```

For this project, `pyproject.toml` is the canonical dependency definition. The file already exists at the repository root.

The practical recommendation is to create a named conda environment, activate
it, use `uv` or pip for project dependencies, and install PyTorch from the CUDA
wheel index that matches the machine.

## Isolated Python environment

Create and activate it with:

```bash
conda create -n tsi python=3.11 -y
conda activate tsi
```

## uv

Install `uv` if needed:

```bash
python -m pip install uv
```

Recommended project install with `uv`:

```bash
uv pip install -e ".[dev,models,explainability,viz,notebooks,data]"
```

`uv` is preferred for normal dependency sync because it is fast and resolves
packages consistently. Conda remains useful for a named, GPU-oriented Python
environment.

## General Research Libraries

Install the project and research dependencies with pip if not using `uv`:

```bash
python -m pip install -e ".[dev,models,explainability,viz,notebooks,data]"
```

This includes:

```text
numpy
pandas
joblib
scikit-learn
pydantic
lxml
pandas-market-calendars
requests
ta
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
torch
torchvision
torchaudio
build
pytest
ruff
twine
uv
```

## Optional GPU setup

Deep-learning experiments require a CUDA-compatible PyTorch installation. Match
the wheel index to the CUDA runtime supported by the target machine. For a CUDA
12.8 host, the installation is:

```bash
python -m pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
```

Verify CUDA availability:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

The expected device count depends on the target host. Verify that it is
available before starting a GPU experiment. The reference GPU reports used two
devices:

```text
2
```

## Notes

PyTorch is installed with an explicit CUDA wheel command instead of relying only on `pip install -e ".[deep]"`, because CUDA wheel selection should be documented for GPU reproducibility.

If using `uv` for the full environment including deep learning dependencies, pass both the Python target and the PyTorch CUDA index explicitly:

```bash
uv pip install \
  -e ".[dev,models,explainability,viz,notebooks,data,deep]" \
  --extra-index-url https://download.pytorch.org/whl/cu128
```

Avoid `uv pip install --system`; activate the intended environment explicitly.

## Reference environment for GPU reports

The published GPU experiment reports record the following reference
environment. These values document provenance; they are not requirements for
using the CPU-capable package or dashboard:

```text
Python: 3.11.15
PyTorch: 2.11.0+cu128
CUDA available in PyTorch: True
CUDA device count: 2
GPU 0: NVIDIA GeForce RTX 4090
GPU 1: NVIDIA GeForce RTX 4090
uv: 0.11.11
```

Core package dependencies are defined by `pyproject.toml`; install only the
extras needed for the task rather than reproducing this entire environment.

For the full research environment, the relevant extras are:

```text
data, models, explainability, viz, notebooks, deep, dev
```
