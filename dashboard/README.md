# Trust Dashboard

Streamlit dashboard for local trust experiment artifacts and the Go warning API. The TypeScript
stock dashboard is the primary ticker analysis UI as of `0.4.0`; this app remains useful for
research diagnostics and the Live API tab.

## Run

Install the optional dashboard dependency:

```bash
uv sync --locked --extra dashboard
```

Start the app:

```bash
uv run --locked --no-sync streamlit run dashboard/app.py
```

For the Live API tab, run the Go gateway separately:

```bash
make api
make dashboard
```

The default run directory is:

```text
experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08
```

The dashboard reads committed summary, warning evaluation, diagnostics, threshold sweep, and report
artifacts. Ticker-level timelines are enabled only when the local ignored `predictions.csv` exists
in the run folder.

The Live API tab reads:

```text
GET /health
GET /api/v1/status
GET /api/v1/models/current
GET /api/v1/warnings/latest?level=alert&sort=trust_score&order=desc
GET /api/v1/warnings/latest?level=watch&sort=calibrated_risk_probability&order=desc
```

Set the API base URL in the sidebar. Use `http://localhost:18080` when running the repository
`make api` target, or set `TSI_DASHBOARD_API_BASE_URL`.
