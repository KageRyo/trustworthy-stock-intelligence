# TSI Stock Dashboard

Version: `0.2.0`

TypeScript dashboard for the PostgreSQL-backed Go warning API.

## Data Contract

All API responses are validated with Zod schemas before rendering:

```text
src/lib/schemas.ts
```

The main ticker analysis endpoint is:

```text
GET /api/v1/analysis/{ticker}
```

The dashboard also manages a DB-backed browser-session watchlist. The session
name is generated in `sessionStorage`, and searched/viewed tickers are added to
that list:

```text
GET /api/v1/watchlists/{session-name}
POST /api/v1/watchlists/{session-name}/tickers
DELETE /api/v1/watchlists/{session-name}/tickers/{ticker}
```

See:

```text
docs/api/analysis_api.md
```

The UI supports English and 正體中文 through a client-side language switcher.
Ticker symbols are handled as strings so Taiwan codes keep leading zeroes and
suffix letters.

## Run

Start PostgreSQL and the Go API first:

```bash
docker compose up postgres
make api
```

Start the dashboard:

```bash
cd frontend/stock-dashboard
npm ci
npm run dev
```

Default local URL:

```text
http://localhost:5175
```

For LAN testing, use:

```text
http://140.123.105.126:5175
```

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:18080`
by default. Override the proxy target with:

```bash
TSI_DASHBOARD_API_BASE_URL=http://127.0.0.1:18080 npm run dev
```

For a built deployment, set the browser-facing API base URL at build time:

```bash
VITE_TSI_API_BASE_URL=http://127.0.0.1:18080 npm run build
```
