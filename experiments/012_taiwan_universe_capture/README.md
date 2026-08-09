# Experiment 012: Taiwan Current-Universe Capture

## Status

This is a dated current-catalogue capture that advances the universe and
provider-snapshot prerequisite of Issue #23. It is not a Taiwan historical
evaluation and does not close Issue #23.

The capture queries the official TWSE listed-company endpoint and the TPEx
mainboard and emerging-company endpoints. It writes the provider-derived member
catalogue outside the repository and commits only a hash/count manifest. This
keeps raw provider records out of Git while retaining a reproducibility anchor.

## 2026-08-08 Capture

| Market | Members | Provider symbol convention |
| --- | ---: | --- |
| TWSE | 1,093 | `code.TW` |
| TPEx mainboard | 890 | `code.TWO` |
| TPEx emerging | 360 | `code.EMERGING` |
| Total | 2,343 | market-qualified |

The current catalogue SHA-256 is
`5084ffde87af1855635dbd2c531993a08c74ac512c50335a7b342b0a7111d8c3`.
Endpoint response hashes and limitations are recorded in
[`run_manifest.json`](run_manifest.json).

## Reproduce

Use a private, untracked destination. The manifest can be reviewed separately
after checking current provider rights.

```bash
PYTHONPATH=src python -m scripts.capture_taiwan_universe \
  --members-output /secure/tsi/taiwan-current-members.csv \
  --manifest-output /secure/tsi/taiwan-current-manifest.json
```

## What This Does Not Establish

- Current membership is not point-in-time membership. It cannot infer prior
  removals, delistings, suspensions, or historical information availability.
- This catalogue alone does not provide a legally cleared OHLCV history or a
  complete historical research universe.
- No purged Taiwan -> Taiwan model result is added here. The six-symbol pilot
  remains the only reported Taiwan performance result until a historical
  universe and matching OHLCV snapshot are selected.
