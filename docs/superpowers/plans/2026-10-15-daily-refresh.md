# Daily refresh and local service recovery

Goal: refresh the existing US and Taiwan pooled daily models automatically and restore the local PostgreSQL → Go → Vite serving path using Docker Desktop exclusively.

Design: one Python command per market obtains the seed universe from the existing OHLCV snapshot without changing research inputs. Download complete adjusted daily history (including provider revisions), exclude unfinished market dates, audit coverage, freshness and OHLCV invariants, ingest PostgreSQL, and train from the persisted bars. Candidate model and warnings live in a unique run directory. Validate both schemas and prediction coverage, commit warnings to PostgreSQL, then atomically replace only that market's serving bundle. A per-market process lock prevents overlapping runs. Typed, credential-free status artifacts record stage, dates, hashes and failures; failed candidates never replace the active bundle.

Use systemd user services and market-specific persistent timers on this WSL machine. PostgreSQL stays on Docker Desktop with its existing populated volume. No native Docker daemon. The API fails closed without DB and retries startup after Docker Desktop becomes available. Dashboard uses its existing Vite proxy. Authentication, queue redesign, model changes and GitHub pushes are outside scope.

## Work and acceptance

- [x] Add tests for successful publication, DB failure preserving active model, missing/stale/invalid bars, numeric and alphanumeric Taiwan symbols, and process overlap. Observe failures before implementation.
- [x] Implement `scripts.refresh_daily_models` and `tsi.data.daily_refresh` with typed configuration/status, quality checks, DB-backed training and atomic publication. Reuse existing prediction and ingestion helpers.
- [x] Add a reproducible local service installer and checked-in systemd templates for API, dashboard and per-market timers. Preserve the existing Docker volume, configure restart behavior and Docker Desktop prerequisite checks.
- [x] Update environment examples, local operations guide, roadmap and changelog.
- [x] Run Python suite and Ruff; Go suite; frontend install, tests, build and audit. Validate systemd units.
- [x] Run real US and Taiwan refreshes, inspect DB batches/bars and bundle hashes, verify timer installation, restart recovery, and GET analysis through Vite proxy for real US and Taiwan tickers. Record runtime evidence and any environmental limitation.

Implementation branch: `feat/daily-model-refresh`. Use targeted behavioral regression tests, not presentation-lock tests.

## Implementation rulings

- Add a recoverable per-market publication journal rather than claiming PostgreSQL and filesystem writes are one atomic transaction. A DB-committed candidate is completed on retry; an older fetch cutoff does not replace the current daily refresh.
- Supervise the existing Desktop container continuously and retry transient daily failures without a start-limit cutoff. Quality failures exit 65 and wait for correction or the next daily timer.
- Real Taiwan history exposed 11 OHLC violations. Daily-only yfinance repair resolved nine; two residual TPEx closes require official OHL scale agreement and preceding adjustment-factor agreement, with typed evidence. No row is silently dropped or clamped.
- Coverage detection in the existing quality audit was quadratic in row count. Reuse one valid-timestamp mask; existing quality tests retain the audit semantics. A 151,094-row Taiwan audit now completes in about 1.5 seconds.
- Browser verification exposed a selected-ticker provenance bug: the trust panel preferred the latest global model and timestamps. Use selected analysis metadata consistently, with a regression test covering different US/Taiwan batches.

Completion evidence: [local refresh validation](../../operations/local_refresh_validation.md). All acceptance items above are verified; future regular timer firing and a full host reboot remain observation limits, not claims of this session.
