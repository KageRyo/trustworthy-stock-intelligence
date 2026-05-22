# Trustworthy Stock Intelligence

A research-oriented framework for explainable, calibrated, and uncertainty-aware stock risk early-warning.

This project does not aim to provide investment advice, automated trading, or exact stock price prediction.  
Instead, it reformulates stock analysis as a future risk-event detection problem.

## Research Focus

Trustworthy Stock Intelligence studies whether stock risk warning models can issue reliable warnings under noisy and non-stationary market conditions. The core objective is not to maximize trading profit or predict the next closing price, but to detect future drawdown risk events early and explain why a warning is produced.

The first milestone is:

```text
Milestone 1: TSI-Risk-v0
```

## Main Task

```text
Given historical market observations up to day t,
predict whether a stock will experience a drawdown risk event within the next H trading days.
```

Initial setting:

```text
Universe: S&P 100
Frequency: Daily
Horizon: 5 trading days
Risk event: future 5-day max drawdown <= -5%
```

## Inputs and Outputs

Input:

```text
historical OHLCV
technical indicators
market index features
```

Output:

```text
future risk-event probability
warning level
calibrated confidence
uncertainty estimate
explanation factors
```

## Dataset Roadmap

```text
Demo: DJIA 30
Main experiment v0: S&P 100
Formal research v1: S&P 500
Benchmark comparison: ACL18 / StockNet, CIKM18, BigData22
```

The first implementation phase focuses only on:

```text
S&P 100
Daily OHLCV
Technical indicators
Market index
5-day drawdown risk label
```

Yahoo Finance is used for pilot experiments. For formal research, higher-quality data sources such as WRDS/CRSP, Polygon, Tiingo, or official exchange data are preferred.

## Research Scope

This repository is a research codebase, not a stock application.

In scope for Milestone 1:

- leakage-free future drawdown risk labeling
- walk-forward validation
- baseline models: Logistic Regression, Random Forest, XGBoost
- probability calibration
- uncertainty-aware warning levels
- alert-oriented evaluation
- reproducible experiment documentation

Out of scope for Milestone 1:

- investment recommendation
- automated trading
- exact stock price prediction
- dashboard
- FastAPI service
- real-time streaming
- news NLP
- LLM agents
- RAG
- full multimodal learning
- high-frequency data
- Taiwan stock data
- Transformer-scale models

## Repository Structure

```text
configs/dataset/     Dataset definitions for demo, v0, and v1 research settings.
data/                Local data artifact documentation; raw datasets are gitignored.
src/tsi/data/        Downloading, preprocessing, universe loading, and temporal splits.
src/tsi/features/    Technical indicator feature generation.
src/tsi/labeling/    Risk-event labeling and warning-level definitions.
src/tsi/models/      Baseline warning models.
src/tsi/trust/       Calibration, uncertainty, and explainability modules.
src/tsi/evaluation/  Alert-oriented metrics, lead-time evaluation, and backtesting checks.
docs/                Research definitions and experiment protocol.
experiments/         Experiment notes and reports.
notebooks/           Exploratory notebooks.
scripts/             Command-line experiment entry points.
tests/               Unit tests for leakage-sensitive logic.
```

## Evaluation Principles

Accuracy alone is not sufficient for stock risk early-warning. The first milestone evaluates:

```text
Precision
Recall
F1
AUC
False Alarm Rate
Miss Rate
Brier Score
Expected Calibration Error
Lead Time
Coverage
Selective Risk
```

All evaluation should use temporal or walk-forward splits. Random train-test splits are not allowed for the main protocol.

## Pilot Data Download

Pilot S&P 100 and S&P 500 OHLCV downloads are implemented with `yfinance`.

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -m scripts.prepare_data \
  --universe all \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Downloaded files are written under `data/raw/` and are intentionally excluded from git. See `docs/data_download.md` for details.

## Environment

This project uses `pyproject.toml` as the dependency definition. On this machine, the recommended setup is:

```text
conda for the Python 3.11 GPU environment
uv for fast Python package installation
explicit PyTorch CUDA wheel for RTX 4090 GPU support
```

The verified local environment is:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock
Python 3.11.15
PyTorch 2.11.0+cu128
2 x NVIDIA GeForce RTX 4090 visible to PyTorch
```

See `docs/environment.md` for installation details.

## Baseline Training

The repository now supports a minimal leakage-aware baseline pipeline:

```text
OHLCV CSV
-> technical features
-> future drawdown labels
-> walk-forward split
-> logistic regression baseline
-> calibration on a dedicated calibration window
-> fold-level evaluation
```

Example training run:

```bash
python -m scripts.train \
  --input data/raw/sp100/ohlcv.csv \
  --train-size 252 \
  --calibration-size 63 \
  --test-size 63 \
  --calibration-method platt \
  --output data/artifacts/sp100_logistic_summary.json \
  --predictions-output data/artifacts/sp100_logistic_predictions.csv
```

The training summary JSON reports both raw and calibrated test metrics. The
prediction CSV includes:

```text
date
ticker
risk_label
fold_id
model
risk_probability
calibrated_risk_probability
calibration_method
alert_threshold
warning_level
```

By default, the training pipeline also selects an alert threshold on each
calibration window using the chosen threshold objective. This separates
probability calibration from downstream alert decisions.

## Evaluation

Prediction artifacts can be re-evaluated independently:

```bash
python -m scripts.evaluate \
  --input data/artifacts/sp100_logistic_predictions.csv \
  --prob-col calibrated_risk_probability \
  --output data/artifacts/sp100_logistic_eval.json
```

## Status

This repository now has a runnable pilot baseline for TSI-Risk-v0. The next
priority is to compare raw and calibrated warnings on real S&P 100 pilot data,
then write the first experiment reports with actual fold-level results.
