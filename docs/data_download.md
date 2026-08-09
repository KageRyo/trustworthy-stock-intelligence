# Data Download

## Purpose

This project uses `yfinance` only for pilot OHLCV experiments. The downloaded data is intended to validate the research pipeline before using higher-quality formal research data.

Formal research should prefer:

```text
WRDS/CRSP
Polygon
Tiingo
official exchange data
```

## Conda Environment

Create and activate a local Python 3.11 environment:

```bash
conda create -n stock python=3.11 -y
conda activate stock
```

Install the project into the environment:

```bash
python -m pip install -e .
```

## Download Commands

Download S&P 100:

```bash
python -m scripts.prepare_data \
  --universe sp100 \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Download S&P 500:

```bash
python -m scripts.prepare_data \
  --universe sp500 \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Download both:

```bash
python -m scripts.prepare_data \
  --universe all \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Download explicit US and Taiwan tickers:

```bash
python -m scripts.download_tickers \
  --tickers NVDA 2330 \
  --interval 1d \
  --output-dir data/raw/watchlist
```

The reproducible Taiwan baseline pilot uses the explicit six-ticker list in
[`configs/dataset/taiwan_pilot.yaml`](../configs/dataset/taiwan_pilot.yaml) and
is documented in
[`experiments/009_taiwan_pilot/README.md`](../experiments/009_taiwan_pilot/README.md).
It commits only snapshot fingerprints and aggregate metrics; raw provider data
and prediction rows remain gitignored.

For intraday freshness checks, request 5-minute bars. Numeric Taiwan tickers are
resolved to yfinance provider symbols such as `2330.TW`, while the output keeps
the user-facing ticker as `2330`.

```bash
python -m scripts.download_tickers \
  --tickers NVDA 2330 \
  --interval 5m \
  --start 2026-06-12 \
  --output-dir data/raw/watchlist_5m
```

## Output Files

Each universe writes:

```text
data/raw/<universe>/ohlcv.csv
data/raw/<universe>/tickers.csv
data/raw/<universe>/metadata.json
```

`metadata.json` records the provider, download timestamp, requested interval,
failed batches, and SHA-256 fingerprints for `ohlcv.csv` and `tickers.csv`.
The hashes identify an exact snapshot so later provider corrections can be
detected; they do not by themselves explain why a provider revised data.

The OHLCV schema is:

```text
date
ticker
open
high
low
close
adj_close
volume
```

## Version Control Policy

Downloaded data files are not committed to git.

The repository commits:

```text
downloader code
configuration
documentation
data directory README
```

The repository does not commit:

```text
data/raw/
data/interim/
data/processed/
data/artifacts/
```

This avoids pushing large vendor-adjusted files to GitHub while preserving the exact commands needed to regenerate the pilot datasets.

## Local Validation

The first successful local download used:

```text
start date: 2015-01-01
S&P 100 rows: 283,289
S&P 500 rows: 1,388,643
```

Local data sizes:

```text
data/raw/sp100: 31M
data/raw/sp500: 151M
```
