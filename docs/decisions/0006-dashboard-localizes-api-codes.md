# 0006: The Dashboard Localizes Stable API Codes

- Status: Accepted
- Date: 2026-10-08 (pull request #138)
- Evidence: Pull request #138

## Context

The dashboard supports English and 正體中文. The trust-status and data-freshness cards showed English
text from the Go API. The trust-summary precedence was implemented twice, in Go and TypeScript, and
the two copies had diverged.

## Decision

- The API returns stable codes, such as `trust.summary_code`, `freshness.reason_code`, and
  `reasons[].code`, next to English text.
- Precedence rules live only in the Go API.
- The dashboard translates codes with its typed i18n dictionaries. It falls back to the API text
  only for unknown codes.

## Consequences

- New user-facing states need a code in Go, an OpenAPI enum value, and an entry in both locale
  dictionaries. Frontend tests check that every code has wording in both locales.
- The locale dictionaries mirror each other by design, so SonarCloud copy-paste detection skips
  `frontend/stock-dashboard/src/lib/i18n.ts`.

## Revisit when

The API serves clients that need server-side localization.
