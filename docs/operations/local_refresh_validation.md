# Local refresh validation: 2026-10-15

Checked at 2026-10-15T06:32:23.949614+00:00. These are local workstation results, not evidence of long-term unattended operation.

| Market | Run                                       | Daily data date | DB warnings | Active bundle SHA-256                                            |
| ------ | ----------------------------------------- | --------------- | ----------- | ---------------------------------------------------------------- |
| us     | daily_us_20261015T061851_232c82f2436d     | 2026-10-14      | 100         | 2671798862e3fcea7a07d551773d1ca1ebe718278ffc76e5cc395e23d4d86965 |
| taiwan | daily_taiwan_20261015T062416_f1aa553aad48 | 2026-10-14      | 53          | 5f3c5c1877651315d1917832013fc02a43b590be6c3272cf96b08cc884a4d967 |

- Both active bundles and warning artifacts passed their Pydantic schemas. Active file hashes and persisted training-input hashes match the published run reports; PostgreSQL warning counts match each universe.
- Taiwan daily refresh used provider price repair plus two official TPEx close reconciliations (3260 on 2017-07-03 and 8069 on 2015-11-23). Run reports retain original/corrected prices, official OHL scale and preceding adjustment-factor evidence. Earlier invalid snapshots failed quality checks without replacing serving models.
- Python: 432 passed, 1 skipped; Ruff passed. Go: all packages passed. Frontend: 40 passed, 1 skipped; typecheck/build passed; npm audit found 0 vulnerabilities. The existing Transformer nested-tensor and frontend chunk-size warnings remain non-failing.
- `make docs-check`, `git diff --check`, and systemd unit validation passed.
- Real Chromium browser searches for NVDA and 2330 through Vite rendered completed, fresh daily analyses with each market's own model provenance. English and 正體中文 were checked. Zod validated real proxied responses; the existing stale 5240 result remains visibly blocked by freshness policy.
- Forced API main-process termination recovered automatically (NRestarts=1). Stopping only the project PostgreSQL container produced DB-not-ready responses, then the supervisor recovered the same container and volume; readiness returned after about 15 seconds. No other project containers were stopped.
- Docker reports Docker Desktop. Native docker.service and docker.socket are disabled and inactive.
- Enabled persistent weekday timers: Taiwan 19:15 Asia/Taipei; US 18:15 America/New_York, with up to 120 seconds jitter. Both service invocations were exercised; the first regular future timer firing and a full Windows/WSL reboot were not observed in this session.
- PostgreSQL/bundle publication uses a recoverable journal and eventual consistency; fault-injection tests cover DB failure, publication failure, and recovery across a later daily cutoff.

See [local operations](../guides/local_operations.md) for setup, scope and recovery steps.
