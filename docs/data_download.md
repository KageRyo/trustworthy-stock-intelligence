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

The local environment used for pilot downloads is:

```text
/mnt/8tb_hdd/ryo/miniconda3/envs/stock
```

It was created with:

```bash
/mnt/8tb_hdd/ryo/miniconda3/bin/conda create -n stock python=3.11 -y
```

Install the project into the environment:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/pip install -e .
```

## Download Commands

Download S&P 100:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -m scripts.prepare_data \
  --universe sp100 \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Download S&P 500:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -m scripts.prepare_data \
  --universe sp500 \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

Download both:

```bash
/mnt/8tb_hdd/ryo/miniconda3/envs/stock/bin/python -m scripts.prepare_data \
  --universe all \
  --start 2015-01-01 \
  --output-root data/raw \
  --batch-size 50
```

## Output Files

Each universe writes:

```text
data/raw/<universe>/ohlcv.csv
data/raw/<universe>/tickers.csv
data/raw/<universe>/metadata.json
```

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
