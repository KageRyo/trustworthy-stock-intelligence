# Trust Dashboard

Streamlit dashboard for local trust experiment artifacts.

## Run

Install the optional dashboard dependency:

```bash
pip install -e ".[dashboard]"
```

Start the app:

```bash
streamlit run dashboard/app.py
```

The default run directory is:

```text
experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08
```

The dashboard reads committed summary, warning evaluation, diagnostics,
threshold sweep, and report artifacts. Ticker-level timelines are enabled only
when the local ignored `predictions.csv` exists in the run folder.
