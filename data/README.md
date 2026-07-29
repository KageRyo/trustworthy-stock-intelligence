# Local Data Artifacts

This directory is reserved for local research data artifacts.

The downloader writes pilot Yahoo Finance datasets to:

```text
data/raw/sp100/
data/raw/sp500/
```

Expected files:

```text
ohlcv.csv
tickers.csv
metadata.json
```

These artifacts are intentionally excluded from git because they can be large
and may be vendor-adjusted over time. Downloader metadata includes SHA-256
fingerprints so an experiment can identify the exact input snapshot.

Current local validation on this machine produced:

```text
data/raw/sp100/ohlcv.csv
data/raw/sp500/ohlcv.csv
```

Do not commit files under `data/raw/`, `data/interim/`, or `data/processed/`.
