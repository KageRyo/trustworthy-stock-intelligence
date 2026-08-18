# Development and Runtime Environment

This document separates portable project requirements from maintainer hardware
and historical experiment provenance. A listed workstation is never a hardware
requirement for contributors.

## Supported project baseline

| Component | Supported baseline |
| --- | --- |
| Python package | Python `>=3.10` |
| Maintainer and CI Python | `3.11`, selected by `.python-version` |
| Python dependency manager | uv `0.12.5` or compatible newer release |
| Go API | Go `1.25.13` |
| TypeScript dashboard | Node.js `22.23.2`, npm `10.9.x` |
| PostgreSQL | `17-alpine` container |
| Container runtime | Docker with Compose |

General package, API, dashboard, and CPU test work does not require an NVIDIA
GPU. Deep-training results must use a compatible accelerator and record the
actual runtime, device count, model configuration, and data provenance.

## Python environment with uv

`pyproject.toml` defines dependency ranges and `uv.lock` records the exact
cross-platform resolution. Do not commit `.venv`, and do not install project
packages into the system Python.

Install uv, then create the CPU development environment used by CI:

```bash
uv sync --locked \
  --extra dev \
  --extra data \
  --extra db \
  --extra dashboard \
  --extra models \
  --extra explainability \
  --extra viz \
  --extra notebooks \
  --extra deep
```

Run commands without relying on shell activation:

```bash
uv run --locked --no-sync python -m pytest
uv run --locked --no-sync python -m ruff check src tests scripts dashboard
```

The `deep` extra selects CPU-only PyTorch wheels in uv. On a CUDA 12.6
workstation, replace `--extra deep` with `--extra deep-cu126`:

```bash
uv sync --locked \
  --extra dev \
  --extra data \
  --extra db \
  --extra dashboard \
  --extra models \
  --extra explainability \
  --extra viz \
  --extra notebooks \
  --extra deep-cu126
```

The two deep-learning extras conflict intentionally and cannot be enabled
together. PyTorch, torchvision, and torchaudio are kept on the tested `2.11.x`,
`0.26.x`, and `2.11.x` families respectively.

Miniforge or Conda is not required. Reconsider it only when a future dependency
needs a native library unavailable from PyPI/PyTorch wheels.

## Node.js and Go

`mise.toml` pins the maintainer toolchain. mise is optional for contributors;
equivalent installations of the exact versions are valid.

```bash
mise install
node --version
npm --version
go version
```

Node.js 22 is in Maintenance LTS. Migrate the project and CI to Node.js 24 LTS
before Node.js 22 reaches end of life; perform that migration as a separately
tested maintenance change.

## Docker and PostgreSQL

On native Linux, use one Docker Engine. On Windows with WSL2, prefer Docker
Desktop with WSL integration and do not also run a second `docker.service`
inside the same distribution. Keeping one daemon avoids separate image stores,
volumes, networks, and conflicting published ports.

Create `.env` from `.env.example`, provide local-only PostgreSQL credentials,
then start the database:

```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
```

PostgreSQL remains required for the Go API. The service must fail fast when the
database URL is absent or unreachable.

## CUDA on WSL2

WSL2 uses the NVIDIA driver installed on Windows. Do not install a Linux NVIDIA
display driver, `cuda-drivers`, or a driver-bearing `cuda` meta-package inside
WSL. PyTorch wheels include the CUDA runtime needed by this project; a system
`nvcc` compiler is not required for normal training.

Install a WSL-safe CUDA Toolkit only if future work must compile custom CUDA
extensions. In that case, choose a toolkit-only package and record its exact
version.

Verify the active PyTorch environment:

```bash
uv run --locked --no-sync python -c \
  "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

## Current maintainer workstation snapshot

Snapshot recorded on `2026-08-19`; these values describe one development
machine and are not project requirements:

```text
Host: Windows with WSL2
Distribution: Ubuntu 26.04 LTS
CPU: Intel Core i7-12700KF
Memory: 32 GiB
GPU: NVIDIA GeForce RTX 3090, 24 GiB, one device
Windows/WSL NVIDIA driver: 560.94
WSL CUDA capability: 12.6
Python: 3.11.16
PyTorch: 2.11.0+cu126
uv: 0.12.5
Node.js: 22.23.2
npm: 10.9.8
Go: 1.25.13
Docker Desktop: 29.7.2
Docker Compose: 5.3.1
```

Single-GPU training must not be described as multi-GPU training. Detect device
count at runtime and enable `DataParallel` or `DistributedDataParallel` only
when more than one usable device is actually present.

## Historical GPU experiment provenance

Previously published GPU experiment reports were produced in this recorded
reference environment:

```text
Python: 3.11.15
PyTorch: 2.11.0+cu128
CUDA available in PyTorch: true
CUDA device count: 2
GPU 0: NVIDIA GeForce RTX 4090
GPU 1: NVIDIA GeForce RTX 4090
uv: 0.11.11
```

Those values remain attached to the historical results for auditability. They
do not describe the current maintainer workstation and are not requirements for
installing or contributing to the project.
