# Dashboard operational states

The dashboard keeps risk output separate from operational trust state. A search can therefore show a
result while also making a stale provider, low trust score, or abstention visible.

## State sources

- `data_freshness.freshness.state` is shown as fresh, stale, or unusable. An unusable result is
  treated as blocked/abstained by the serving policy.
- `trust.trust_status`, `trust.uncertainty_status`, and the warning level are combined into trusted,
  limited-trust, or abstention cards.
- `GET /api/v1/providers/health` supplies the latest provider status and ticker-level coverage. If
  the endpoint is unavailable, the dashboard shows coverage as unknown instead of hiding the result.
- When synchronous lookup cannot produce an analysis, the dashboard submits a typed
  `prediction_job.v1` request and polls the job until it is completed or fails. The UI does not
  imply that a queued job is an available risk result.

All responses are validated with the TypeScript runtime schemas before they reach dashboard
components. English and `zh-Hant` copy are kept in the typed i18n dictionary.
