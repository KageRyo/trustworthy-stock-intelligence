# 021 — Public-snapshot universe sensitivity pilot

**Status: partial research evidence for [Issue #29](https://github.com/KageRyo/trustworthy-stock-intelligence/issues/29). This is a weekly observed public-information proxy, not an authoritative historical S&P 100 membership benchmark. The formal benchmark is deferred as an accepted limitation under [ADR 0010](../../docs/decisions/0010-accept-universe-data-limitations.md); this evidence remains partial. No serving model, database or dashboard behavior was changed.**

## Question and result

Can a bounded comparison move beyond synthetic membership fixtures while preserving what was actually observable at each date?

Yes, for a source-limited proxy. A private 2024–2025 input bundle was prepared from historical Wikipedia revisions and Yahoo Finance pilot OHLCV. Both arms completed the existing purged logistic/Platt pipeline with identical folds. The typed comparison accepted their protocol as comparable. That status certifies the comparison contract, not the historical accuracy or licensing completeness of the source.

| Input / evaluation coverage                            | Current-universe control |                                       Weekly observed proxy |
| ------------------------------------------------------ | -----------------------: | ----------------------------------------------------------: |
| Private input securities                               |                      101 |                             110 before membership filtering |
| Securities in the arm's cohort                         |                      101 | 106 over the observation window; 101 per weekly observation |
| Private input OHLCV rows                               |                   50,643 |                          55,161 before membership filtering |
| Trainable rows after the existing preparation pipeline |                   49,128 |                                                      49,112 |
| Test rows across both folds                            |                   12,726 |                                                      12,711 |

There are 12,116 shared test-row keys, 595 added keys and 610 removed keys. The shared raw market observations are identical between the arms. Nine symbols absent from the original current-universe pilot were downloaded to make the observed earlier cohorts evaluable; no raw membership, price or prediction rows are published here.

## Frozen protocol

The execution used the Python source at `1fc85adc608daae90e7bfd7f39595c15775149c8` (v0.11.1). The later Actions-only change does not alter this pipeline. Logistic training ran on CPU; no deep-model training or model deployment took place.

- Input window: 2024-01-01 inclusive to 2026-01-01 exclusive; observed prices start 2024-01-02 and end 2025-12-31.
- Model: existing logistic baseline and its seven default technical features, with Platt calibration.
- Windows: 252 train dates, 63 calibration dates, 63 test dates; step 63 and purge 5.
- Label: next-five-trading-day maximum drawdown below -5%.
- Alert threshold: existing calibration-window F1 selection; no tuning after seeing these comparison results.
- Test fold 0: 2025-05-05 through 2025-08-04. Test fold 1: 2025-08-05 through 2025-10-31.
- Statistics: paired temporal-fold comparison, seed 42, 4,000 resamples. Two folds are too few for reliable significance claims.

| Mean of the two fold metrics | Current control | Observed proxy |
| ---------------------------- | --------------: | -------------: |
| Calibrated ROC AUC           |        0.597961 |       0.601549 |
| Calibrated PR AUC            |        0.109640 |       0.114529 |
| Calibrated Brier score       |        0.075907 |       0.074375 |
| Tuned alert F1               |        0.158732 |       0.143312 |
| Tuned alert recall           |        0.750917 |       0.465836 |
| Tuned alert coverage         |        0.619755 |       0.389205 |

The ranking metrics and tuned alert metrics move in different directions. Cohort changes also change calibration and the selected threshold. This is descriptive cohort sensitivity, not an estimate of pure survivorship-bias magnitude or evidence that the proxy is a better model. At the unmodified 0.5 calibrated threshold, both arms issued no alerts; the tuned rows above use the existing calibration-selected threshold instead.

## Observation reconstruction

The source scan obtained all 47 page revisions between 2023-12-18 and 2025-12-31, without an API continuation. Each source response was retained privately with its revision timestamp and SHA-256. At every Monday 00:00 UTC in 2024–2025, the proxy takes the latest revision published strictly before that cutoff. It does not apply a later page edit to earlier evaluation dates and does not treat an editing timestamp as an official index-effective date.

A new interval starts only when the selected weekly cohort changes. Its `known_at` and `valid_from` are the observation date. Intervals are half-open; open intervals are bounded by the study end, not marked as actual delistings. The manifest validates through the existing v2 membership schema. Current SEC CIK mappings identify companies, with distinct Alphabet share-class identities; they are bookkeeping mappings, not predictor features or certified historical identifier coverage.

| Source snapshot                                                     | Published at UTC    | Role                                          |
| ------------------------------------------------------------------- | ------------------- | --------------------------------------------- |
| [1190636511](https://en.wikipedia.org/w/index.php?oldid=1190636511) | 2023-12-19 01:24:12 | Available before the first weekly observation |
| [1214077543](https://en.wikipedia.org/w/index.php?oldid=1214077543) | 2024-03-16 20:42:50 | First selected by the 2024-03-18 observation  |
| [1281732815](https://en.wikipedia.org/w/index.php?oldid=1281732815) | 2025-03-22 03:20:48 | First selected by the 2025-03-24 observation  |
| [1312508634](https://en.wikipedia.org/w/index.php?oldid=1312508634) | 2025-09-21 02:17:05 | First selected by the 2025-09-22 observation  |
| [1315309322](https://en.wikipedia.org/w/index.php?oldid=1315309322) | 2025-10-05 23:54:07 | Last selected source revision in the window   |

The complete revision audit exposed minute-scale incorrect ticker edits on 2024-07-23 and an early membership change that was reverted in September 2025. Weekly observation avoids selecting those particular transient states, but does not prove that other errors are absent. A different sampling schedule could produce different cohorts. The Wikipedia observations were not replaced with reconstructed official announcement dates.

## Sources and usage constraints

- Wikipedia revision content: [Wikimedia Terms of Use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use), including CC BY-SA attribution requirements. The permanent revision links above provide attribution; this report describes a transformation into weekly observations. Raw revisions and member rows remain local.
- Company identifiers: [SEC company ticker file](https://www.sec.gov/files/company_tickers.json), used as a current identity lookup rather than historical membership evidence.
- Shared OHLCV: the existing `data/raw/sp100` pilot snapshot, retrieved 2026-05-08 from Yahoo Finance. Additional prices were retrieved 2026-10-25 through the existing explicit-ticker downloader. Provider data remain local and are not offered as an official or commercially licensed research archive.
- S&P public announcements were inspected separately as source-quality context. They are not the membership input to this proxy; public access does not establish redistribution rights or provide a reviewed historical archive.
- The [CCU Finance database catalogue](https://deptfin.ccu.edu.tw/p/404-1118-1062.php?Lang=zh-tw) lists Compustat and CRSP. This is a possible institutional route, not confirmation of account entitlement, subscription freshness or specific S&P 100 coverage.
- [Norgate's content table](https://norgatedata.com/data-content-tables.php) explicitly lists historical S&P 100 constituents, while its [trial FAQ](https://norgatedata.com/data-package-faq.php) limits trial history to two years. No account was created or subscription purchased.

## Repeating the comparison

The private source-preparation script, raw snapshots, observation log, original provider metadata and additional price download remain in the local audit bundle. To repeat from the fixed private inputs, set `TSI_PIT_PILOT` to that bundle's `pilot` directory and run:

```bash
python -m scripts.train \
  --input "$TSI_PIT_PILOT/current-control-ohlcv.csv" \
  --train-size 252 --calibration-size 63 --test-size 63 --step-size 63 \
  --purge-size 5 --calibration-method platt \
  --output "$TSI_PIT_PILOT/current-summary.json" \
  --predictions-output "$TSI_PIT_PILOT/current-predictions.csv"

python -m scripts.train \
  --input "$TSI_PIT_PILOT/union-ohlcv.csv" \
  --universe-membership "$TSI_PIT_PILOT/weekly-observation-membership.csv" \
  --universe-schema-version v2 \
  --universe-name sp100_weekly_public_observation_proxy_2024_2025 \
  --membership-source 'Wikipedia revision history sampled each Monday 00:00 UTC; public-information observation proxy, not official effective-date PIT' \
  --membership-source-license 'Wikipedia CC-BY-SA-4.0 with revision attribution; Yahoo prices restricted to private pilot use; raw inputs not redistributed' \
  --train-size 252 --calibration-size 63 --test-size 63 --step-size 63 \
  --purge-size 5 --calibration-method platt \
  --output "$TSI_PIT_PILOT/proxy-summary.json" \
  --predictions-output "$TSI_PIT_PILOT/proxy-predictions.csv"

python -m scripts.compare_universe_benchmarks \
  --baseline-summary "$TSI_PIT_PILOT/current-summary.json" \
  --comparison-summary "$TSI_PIT_PILOT/proxy-summary.json" \
  --baseline-predictions "$TSI_PIT_PILOT/current-predictions.csv" \
  --comparison-predictions "$TSI_PIT_PILOT/proxy-predictions.csv" \
  --output "$TSI_PIT_PILOT/comparison.json" \
  --report "$TSI_PIT_PILOT/comparison.md"
```

The published [comparison](runs/comparison.json) is the existing typed aggregate report with additional source limitations. Its `claim_status: comparable` refers only to protocol comparability. [The membership manifest](runs/membership_manifest.json) records counts, bounds and a fingerprint without raw rows. Repeating from newer provider responses is a new run, not reproduction of these fixed hashes.

## Deferred formal-benchmark acceptance evidence

A reviewed historical constituent archive with actual effective dates, defensible historical security identities, inactive/delisted OHLCV coverage and the corresponding bounded paired benchmark is still required. Weekly observations, successful schema validation and source-local data coverage do not establish that evidence.

The existing preparation pipeline filters membership before rolling features and future labels. Consequently, some entry warm-up rows and exit-boundary label windows are censored. Prices are provider-as-retrieved adjusted data rather than bitemporal quotes. These limitations, mixed retrieval dates and the small fold count prevent stronger historical-performance claims. No production inference result was changed or promoted from this pilot.
