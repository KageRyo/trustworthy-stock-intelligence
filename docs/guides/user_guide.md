# User Guide

The main workflow is ticker-in, analysis-out:

```text
Enter ticker
-> Go API checks latest PostgreSQL warning records
-> optional Python on-demand analysis for missing tickers
-> dashboard renders warning, trust, reason codes, and limitations
```

## Dashboard

Start the API and dashboard:

```bash
docker compose up -d postgres
make api API_ADDR=0.0.0.0:18080
make stock-dashboard
```

Open:

```text
http://localhost:5175
http://<dashboard-host>:5175
```

The dashboard supports English and 正體中文. The language setting is stored in the browser.

## Ticker Search

Supported input styles:

| Example         | Notes                                                                |
| --------------- | -------------------------------------------------------------------- |
| `NVDA`          | US ticker.                                                           |
| `AAPL`          | US ticker.                                                           |
| `2330`          | Taiwan local numeric code.                                           |
| `0050`          | Taiwan ETF local code.                                               |
| `00981A`        | Taiwan alphanumeric ETF code.                                        |
| `02001L`        | Taiwan alphanumeric local code.                                      |
| `6488.TWO`      | Explicit TPEx listed provider suffix.                                |
| `5240`          | Can resolve through TPEx emerging fallback when listed sources miss. |
| `5240.EMERGING` | Explicit TPEx emerging-stock suffix.                                 |

Taiwan local stock codes are stored as strings. This preserves leading zeroes and suffix letters.

## Analysis Output

The analysis response includes:

| Section        | Meaning                                                                      |
| -------------- | ---------------------------------------------------------------------------- |
| Warning        | Raw and calibrated drawdown-risk probability, thresholds, and warning level. |
| Trust          | Trust score, uncertainty score, calibration method, and trust status.        |
| Model          | Model name and model bundle reference.                                       |
| Data freshness | Data cutoff, generation time, API load time, and record count.               |
| Reasons        | Schema-owned reason-code explanations.                                       |
| Limitations    | Fixed statements that keep the output framed as risk warning, not advice.    |

Warning levels:

| Level      | Meaning                                                |
| ---------- | ------------------------------------------------------ |
| `alert`    | Risk probability is above alert policy thresholds.     |
| `watch`    | Risk is elevated enough to monitor.                    |
| `abstain`  | Confidence, history, or uncertainty is not sufficient. |
| `no_alert` | No current warning under the configured policy.        |

## Watchlists

The dashboard uses a browser-session watchlist name stored in `sessionStorage`. There is no default
curated stock list. Tickers are added after the user views or adds them in that browser session.

The API persists watchlist rows in PostgreSQL, so the browser session name is the link between the
UI and DB-backed watchlist state.

## Taiwan Provider Behavior

The on-demand path attempts provider coverage in this order for Taiwan local codes:

```text
yfinance symbol
-> TWSE daily fallback
-> TPEx listed daily fallback
-> TPEx emerging-stock daily fallback
```

Provider payloads are parsed through explicit schemas before being normalized into OHLCV rows. TPEx
emerging daily data may not provide the same open/close semantics as exchange-listed OHLCV; the
system marks the source through ticker metadata and should treat low-history results cautiously.

## Limitations

- The output is a risk-warning signal, not investment advice.
- Provider coverage is not the same as complete market coverage.
- Five-minute ingestion supports freshness, but a model trained on daily labels remains a daily
  warning model until intraday training is implemented.
- `abstain` is a valid result when the system has data but cannot make a trustworthy calibrated
  decision.
- The analysis response reports a typed freshness assessment. Fresh data is allowed, stale data
  remains visible only with a confidence downgrade, and unusable or missing-cutoff data is blocked
  from actionable interpretation with an `abstain` override. Thresholds are selected by feature
  interval (`1m`, `5m`, or `1d`) and market.
