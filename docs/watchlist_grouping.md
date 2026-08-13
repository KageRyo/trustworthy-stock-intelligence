# Session watchlist grouping and cleanup

Watchlist grouping is intentionally browser-session scoped until account-level
watchlists are required. The DB-backed watchlist remains the source of ticker
membership; group names and ticker assignments are stored under a namespaced
`sessionStorage` key and are never sent as user identity or authentication
data.

The dashboard supports filters for market, warning level, low trust, and
freshness, plus deterministic sorting by ticker, market, warning, trust,
freshness, or most recently added. Selecting rows and confirming “Remove
selected” calls the existing typed delete endpoint for each ticker. A failed
delete keeps the API error visible and does not silently claim that cleanup
completed.
