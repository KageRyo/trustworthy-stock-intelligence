# Local daily updates and service recovery

The optional local services run PostgreSQL on Docker Desktop, and the Go API, Vite dashboard and daily model updates as systemd user services under WSL2. They are for local development, not a production deployment. Daily models predict five-trading-day drawdown risk; five-minute ingestion does not turn them into five-minute models.

## Prerequisites and installation

1. Start Docker Desktop on Windows and enable WSL integration for the current distro. Do not enable the native `docker.service` or `docker.socket`.
1. Configure `.env` as described in [the demo guide](local_demo.md). Set `TSI_MODEL_BUNDLE_DIR`, `TSI_US_BUNDLE_INPUT` and `TSI_TAIWAN_BUNDLE_INPUT` to absolute paths. Seed OHLCV snapshots provide the reference universe's string ticker identifiers; their historical rows are not the daily training input and remain unchanged. Keep at least two tickers per market. The daily schedule refreshes these reference universes and their warning records; it does not silently combine session watchlists into the training universe or claim all-market refresh coverage. Other tickers continue to use the existing on-demand/job flow.
1. Install the Python `dev`, `data` and `db` extras plus the Go and Node dependencies (`make frontend-install`). `uv sync` uninstalls packages from extras it is not given, so list these together with the extras the environment already uses, such as the [environment guide](environment.md) profile with `deep-cu126`.
1. Provision PostgreSQL once with `docker compose up -d postgres`. The recovery service subsequently starts only the existing `trustworthy-stock-intelligence-postgres-1` container, and verifies its mounted `trustworthy-stock-intelligence_postgres-data` volume. It deliberately refuses to create a replacement database automatically. Apply missing migrations to an existing database before use.
1. Install and verify units:

```bash
make local-services-install
systemd-analyze --user verify ~/.config/systemd/user/tsi-*.service ~/.config/systemd/user/tsi-*.timer
systemctl --user enable --now tsi-postgres tsi-api tsi-dashboard
```

The installer embeds this checkout's absolute path and the current Go/Node executable directories; rerun it after moving the repository or changing those toolchains. It does not embed database credentials in unit files. Services read `.env`; keep it private. User services run when the WSL user manager is active. Persistent timers catch up when WSL runs again; they cannot wake a stopped Windows/WSL host. Docker Desktop must be configured to start at Windows sign-in if unattended local startup is needed.

## Daily refresh

Run each market once and inspect its output before enabling timers:

```bash
make refresh-daily-us
make refresh-daily-taiwan
systemctl --user enable --now tsi-daily-refresh-us.timer tsi-daily-refresh-taiwan.timer
systemctl --user list-timers 'tsi-*'
```

The US timer runs weekdays at 18:15 New York time, following daylight saving time. The Taiwan timer runs weekdays at 19:15 Taipei time. Both have up to two minutes of jitter and persistent catch-up. Transient failures (including Docker Desktop or DB unavailability) retry every 15 minutes without a start-limit cutoff. Quality/configuration failures exit with status 65 and do not retry until the next timer or a manual start. To retry manually after correcting a quality failure:

```bash
systemctl --user reset-failed tsi-daily-refresh@us
systemctl --user start tsi-daily-refresh@us
```

Each run follows these steps:

1. Acquire the market's lock. Fetch the fixed seed universe's full adjusted daily history from 2015, including provider revisions; never append a new adjusted series blindly to an old price scale. Daily refresh opts into [yfinance price repair](https://ranaroussi.github.io/yfinance/advanced/price_repair.html), including the TPEx `.TWO` fallback, and records `provider_price_repair` in the run report. This provider-assisted correction does not bypass the subsequent quality audit. Residual TPEx closes outside their high/low bounds require an official daily row: the open/high/low scale ratios must agree, the corrected close must fit the bounds, and the provider adjustment factor must agree with the preceding trading row within seven days. Only then are close and adjusted close rescaled together. Each correction records the official prices, original and corrected values, scale and adjustment-factor reference. Without that corroboration, publication fails closed. Existing research downloads keep their default behavior.
1. Exclude the current unfinished market session using an exclusive provider end date. Today is included only after 18:00 in the market's timezone. Persistent catch-up before that time uses earlier complete dates.
1. Audit numeric/OHLCV invariants, timestamps, duplicates and full ticker coverage. Every ticker's latest bar must be within seven calendar days. This tolerates weekends and short exchange holidays; it is not an exchange-calendar guarantee that the latest expected session exists. A provider outage, longer holiday, missing ticker or quality error blocks publication and leaves the active bundle unchanged. There is no synthetic-data fallback.
1. Persist the validated download to `market_bars` and read the daily training frame back from PostgreSQL. Re-audit the stored frame, fit the existing `technical_range` logistic model with monotone Platt calibration, and write a candidate bundle and warnings in a unique run directory.
1. Validate candidate schemas, ticker prediction coverage and non-regressing `data_as_of`. Commit `prediction_batches` and `warning_records`, then atomically replace that market's active bundle. Other markets are independent.

A failed run never replaces the serving bundle. A validated, committed candidate whose filesystem publication fails is marked `publication_pending`; its per-market journal allows the next invocation to validate the DB batch and finish publishing without refetching or retraining. Market bars already committed before a later failure remain available for retry. PostgreSQL and the filesystem cannot commit in one transaction: if the process stops after committing warnings but before publishing the bundle, the DB may hold the newer batch while on-demand scoring still uses the older valid model. Rerun the market refresh to recover that committed candidate and converge them. If its fetch cutoff predates the current complete-session cutoff, the same invocation then performs the current refresh. Do not delete pending markers or candidate directories during recovery. Serving can still block or abstain when freshness or calibration drift is unsafe; publishing a valid model does not imply a safe alert.

## Run evidence and troubleshooting

Reports live under `data/artifacts/daily_refresh/<run_id>/`:

- `status.json`: schema `daily_model_refresh.v1`, market, stage, success/failure, data date, input and published-bundle SHA-256; errors record the exception type without raw credential-bearing messages.
- `download.csv` preserves the provider snapshot before official reconciliation; `download_quality.json` and `persisted_quality.json`: schema-validated quality audits.
- `ohlcv.csv`, `predictions.csv`, `warnings.json` and `candidate/`: local reproducibility artifacts; PostgreSQL remains the serving data layer.

These paths are gitignored. The full training snapshots can grow substantially; retain the evidence needed for your runs and include it in your local backup/retention policy. No automatic deletion of historical evidence is enabled.

```bash
systemctl --user status tsi-postgres tsi-api tsi-dashboard
journalctl --user -u tsi-daily-refresh@us -u tsi-daily-refresh@taiwan --since today
curl --fail http://127.0.0.1:18080/readyz
curl --fail http://127.0.0.1:5175/api/v1/analysis/2330
```

`/readyz` must report the DB ready; an HTML 200 response from Vite alone does not prove integration. Check real analysis metadata (`feature_interval`, `data_as_of`, model, freshness, warning and reasons) through `/api` on port 5175.

PostgreSQL gets Docker's `unless-stopped` restart policy. Its systemd wrapper retries if Desktop is not ready. The PostgreSQL wrapper supervises the same container every 30 seconds and recovers it after a container/engine interruption. The API checks DB availability before startup and retries after 15 seconds; it never starts with JSON/sample fallback. The dashboard restarts after process failure and proxies API errors while the API recovers. To stop the local stack, stop these user services (including `tsi-postgres`) before stopping the project container; do not stop Docker Desktop because other projects may share it.
