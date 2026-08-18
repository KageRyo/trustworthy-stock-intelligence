# Supported Market and Provider Coverage

This matrix describes the repository's current provider paths and the boundaries of the local
dashboard and ingestion pipeline. It is a coverage contract, not a claim that every symbol or
interval is available from every provider. Provider availability, exchange calendars, rate limits,
historical retention, and licensing terms can change; recheck the provider terms before
redistributing data or relying on a result.

## Coverage Matrix

| Market / symbol class                     | Accepted examples                          | Primary provider path                                 | Fallback provider path                      | Intervals                                                                                 | Current status and limits                                                                                                                                                                                 |
| ----------------------------------------- | ------------------------------------------ | ----------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| US-listed stocks                          | `NVDA`, `AAPL`, `MSFT`                     | Yahoo Finance through `yfinance` (`NVDA`)             | None in the default adapter                 | `1m`, `5m`, `1d` when the provider returns them                                           | Supported for provider-backed ingestion. Availability and intraday retention are provider-dependent. The current risk model remains a daily model; `1m`/`5m` bars do not imply intraday model validation. |
| TWSE-listed stocks and Taiwan local codes | `2330`, `0050`, `00981A`, `02001L`         | Yahoo Finance with a `.TW` query symbol (`2330.TW`)   | Official TWSE daily `STOCK_DAY` endpoint    | `1d` through the official fallback; `1m`/`5m` only when `.TW` provider data is available  | Supported for daily provider fallback and typed Taiwan symbol resolution. Current-universe and provider-history limits remain; alphanumeric codes are stored as strings.                                  |
| TPEx-listed stocks                        | `6488.TWO`, `02001L` when resolved as TPEx | Yahoo Finance with a `.TWO` query symbol (`6488.TWO`) | Official TPEx listed daily trading endpoint | `1d` through the official fallback; `1m`/`5m` only when `.TWO` provider data is available | Supported for explicit TPEx resolution and daily fallback. A numeric code must not be assumed to be TPEx without provider/catalogue evidence.                                                             |
| TPEx emerging stocks                      | `5240`, `5240.EMERGING`                    | Yahoo Finance `.EMERGING` when available              | Official TPEx emerging historical endpoint  | `1d` only through the official fallback; intraday is unsupported by the official fallback | Supported as a typed `emerging` market fallback after listed-provider misses. Emerging history and OHLCV semantics are partial; Experiment 014 does not make a broad emerging-market coverage claim.      |

## Resolution and Fallback Rules

For a Taiwan local code received through the on-demand analysis path, the daily fallback order is:

```text
Yahoo Finance (.TW / .TWO when the market is known)
-> official TWSE daily endpoint
-> official TPEx listed daily endpoint
-> official TPEx emerging historical endpoint
```

The resolved market is retained in the ticker metadata. An official emerging response is recorded as
`emerging`, not as `twse` or a generic Taiwan market. Ticker symbols remain strings so leading
zeroes and suffix letters are not lost.

Provider payloads cross an explicit schema boundary before they become OHLCV rows. A successful
provider response does not guarantee sufficient history for a calibrated prediction; the API may
return a typed `abstain` result instead.

## Interval and Model Boundaries

The ingestion command accepts `1m`, `5m`, and `1d` intervals. The near-real-time target is
five-minute freshness, but the current drawdown-risk model is trained and described as a daily
model. Until an intraday training/evaluation protocol exists, five-minute bars are an
ingestion/freshness capability only and must not be presented as five-minute prediction validation.

The official TWSE, TPEx listed, and TPEx emerging fallback adapters currently provide daily data.
Intraday availability in this repository therefore depends on the upstream Yahoo Finance query for
the resolved symbol and its retention rules.

## Coverage, History, and Licensing Limits

- Provider coverage is not complete market coverage. Unsupported, delisted, halted, newly listed, or
  thinly traded symbols may have no usable response.
- The current research pilots use current-universe or selected-symbol samples; this does not remove
  survivorship, sector, liquidity, market-cap, or provider availability bias. See
  [research readiness](research_readiness.md) and
  [issue #29](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/29).
- Official exchange responses and Yahoo Finance data have separate terms and redistribution
  constraints. See [data and model licenses](data_and_model_licenses.md) before publishing raw bars
  or provider payloads.
- Coverage metadata should be treated as a point-in-time observation. It must be refreshed when
  provider adapters, symbol catalogues, or exchange rules change.

## Related Runbooks and Contracts

- [User guide](user_guide.md) for ticker input and Taiwan fallback behavior.
- [Data store](data_store.md) for PostgreSQL market-bar persistence.
- [Local demo](demo/local_demo.md) for running the DB-backed serving path.
- [Roadmap](project_roadmap.md) for the planned provider health, freshness, and scheduled-ingestion
  work in `v0.4.0`.
