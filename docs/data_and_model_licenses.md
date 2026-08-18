# Data And Model Licenses

Last reviewed: 2026-07-29.

This document distinguishes repository licensing from the rights attached to external market data.
It is a project policy, not legal advice.

## Repository Code

Source code and repository-authored documentation are licensed under Apache License 2.0 as stated in
`LICENSE`.

Third-party Python, Go, npm, container, and GitHub Actions dependencies keep their own licenses.
Review dependency licenses before redistribution or a commercial release; Apache-2.0 on this
repository does not relicense them.

## Market Data

Downloaded market data is not covered by this repository's Apache-2.0 license. Raw OHLCV, provider
payloads, DB snapshots, and prediction rows derived from those inputs are gitignored by default.

| Source                       | Repository use                            | Rights boundary                                                                                                                                                               |
| ---------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Yahoo Finance via `yfinance` | Pilot research and pipeline validation    | `yfinance` is an independent open-source client. Yahoo data remains subject to Yahoo and upstream data-provider terms. Do not assume redistribution or commercial rights.     |
| TWSE endpoints               | Taiwan ingestion fallback                 | TWSE website terms reserve rights except material authorized through the Government Open Data Platform; trading-information use may require a separate agreement.             |
| TPEx endpoints               | Listed/emerging Taiwan ingestion fallback | TPEx terms reserve rights except material authorized for public use through the Government Open Data Platform. Do not publish raw provider responses without a rights review. |

Official terms:

- [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
- [TWSE Terms and Conditions of Use](https://www.twse.com.tw/en/terms/use.html)
- [TWSE trading-information use rules](https://www.twse.com.tw/en/products/information/use.html)
- [TPEx Website Terms and Conditions](https://www.tpex.org.tw/en-us/gtsm_disclaimer.html)
- [TPEx E-Data Shop Terms](https://eshop.tpex.org.tw/en/useTerms/index)

Provider terms can change. Recheck them before distributing data, publishing a dataset, offering a
hosted commercial service, or using real-time information.

## Models And Artifacts

The repository does not grant a blanket license to model weights trained on third-party data. Before
publishing a bundle, confirm:

- training-data rights allow the intended use and redistribution
- the model does not embed sensitive or proprietary inputs
- dependency and base-model licenses are compatible
- the model card identifies data sources, snapshot hashes, intended use, and limitations

Aggregate metrics and synthetic schema examples are the preferred public research artifacts. Local
prediction CSVs, DB dumps, raw data, and model bundles remain private unless their rights and
disclosure risk are explicitly cleared.
