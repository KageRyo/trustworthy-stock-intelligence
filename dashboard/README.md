# Trust Dashboard

Streamlit dashboard for local trust experiment artifacts and the Go warning API.

## Run

Install the optional dashboard dependency:

```bash
pip install -e ".[dashboard]"
```

Start the app:

```bash
streamlit run dashboard/app.py
```

For the Live API tab, run the Go gateway separately:

```bash
make predict-latest
make api
make dashboard
```

The default run directory is:

```text
experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08
```

The dashboard reads committed summary, warning evaluation, diagnostics,
threshold sweep, and report artifacts. Ticker-level timelines are enabled only
when the local ignored `predictions.csv` exists in the run folder.

The Live API tab reads:

```text
GET /health
GET /api/v1/status
GET /api/v1/models/current
GET /api/v1/warnings/latest?level=alert
GET /api/v1/warnings/latest?level=watch
```

Set the API base URL in the sidebar. The default is `http://localhost:8080`.
