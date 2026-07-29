# Raw-Versus-Platt AUC Invariance Audit

## Status

Completed targeted audit of the committed Experiment 007 evidence. The audit
explains the AUC difference without changing the original predictions, summary,
calibration comparison, or reported experiment values.

## Question

For the same test samples, a Platt mapping has the form:

```text
calibrated_probability = sigmoid(
    coefficient * raw_probability + intercept
)
```

A positive coefficient is strictly increasing and must preserve within-fold
ranking and AUC. A negative coefficient reverses ranking and, including ties,
must satisfy:

```text
calibrated_auc = 1 - raw_auc
```

Experiment 007 reported mean fold AUC `0.615325` for raw logistic probabilities
and `0.608615` after Platt calibration. This audit determines why.

## Method

The audit uses the ignored, provider-derived prediction CSV identified by the
existing run manifest. For each fold it independently filters valid raw and
calibrated rows, then hashes sorted sample keys constructed as:

```text
fold_id | ticker | date | risk_label
```

It reconstructs the Platt parameters from paired predictions with:

```text
logit(calibrated_probability)
    = coefficient * raw_probability + intercept
```

The reconstructed mappings have maximum absolute logit residual below
`1e-14`, compared with the audit tolerance of `1e-10`.
Sample-key digests use the explicit `sha256:<hex>` representation.

The following invariants are executable and covered by unit tests:

1. Raw and calibrated variants use identical sample keys.
2. Positive coefficients preserve within-fold AUC to `1e-12`.
3. Negative coefficients satisfy `calibrated_auc = 1 - raw_auc`.
4. Single-class folds mark AUC unavailable in both variants.

The audit also rejects duplicate sample keys, checks ranking inversions and
Spearman correlation, and verifies the stored mean-fold and pooled AUC values
against independent recomputation.

## Finding

The difference is fully explained by one negative calibrator coefficient.

| Diagnostic | Result |
| --- | ---: |
| Folds | 39 |
| Positive-coefficient folds | 38 |
| Negative-coefficient folds | 1 |
| Sample-key mismatches | 0 |
| Single-class test folds | 0 |
| Failed invariants | 0 |

Fold 8 is the sole ranking reversal:

| Field | Value |
| --- | ---: |
| Calibration window | 2018-01-25 to 2018-04-25 |
| Calibration event rate | 0.172822 |
| Test window | 2018-05-03 to 2018-08-01 |
| Test event rate | 0.047781 |
| Test rows / positives | 6,174 / 295 |
| Platt coefficient | -0.798373 |
| Platt intercept | -1.097655 |
| Raw test AUC | 0.630840 |
| Calibrated test AUC | 0.369160 |
| AUC delta | -0.261680 |
| Spearman rank correlation | -1.0 |
| Strict ranking inversions | 19,056,051 |

The fold satisfies `0.369160 = 1 - 0.630840`. Its contribution divided by 39
is `-0.0067097`, exactly explaining the reported mean-fold AUC change. All 38
positive-coefficient folds preserve AUC within `1e-12`.

This is not the COVID failure documented for fold 15. Fold 8 shows a separate
failure mode: unconstrained Platt fitting can learn a negative slope when the
calibration window associates higher raw scores with lower event risk. That
mapping then reverses otherwise useful test ranking.

## Aggregation Definitions

The audit makes three distinct quantities explicit:

| Aggregation | Raw AUC | Calibrated AUC | Delta |
| --- | ---: | ---: | ---: |
| Unweighted mean-fold AUC | 0.615325 | 0.608615 | -0.006710 |
| Sample-weighted mean-fold AUC | 0.615444 | 0.608830 | -0.006614 |
| Pooled AUC | 0.667797 | 0.611803 | -0.055994 |

The Experiment 007 main table reports the unweighted mean and sample standard
deviation across folds. The calibration-comparison artifact also contains a
pooled AUC over all rows. Pooled AUC is allowed to change even for positive
within-fold mappings because each fold has a different coefficient and
intercept, which can reorder samples across folds. It must not be labeled as
the same statistic as mean-fold AUC.

## Reproduce

```bash
python -m scripts.audit_auc_invariance \
  --input experiments/007_research_evidence/runs/sp100_logistic_platt_purged/predictions.csv \
  --summary experiments/007_research_evidence/runs/sp100_logistic_platt_purged/summary.json \
  --comparison experiments/007_research_evidence/runs/sp100_logistic_platt_purged/calibration_comparison.json \
  --output-dir experiments/007_research_evidence/audit
```

The command exits unsuccessfully if any invariant fails.

## Artifact Provenance

Inputs:

```text
predictions.csv SHA-256:
ce5cf9e63e445af12da449e1f398914064989879c680e35bbf87ae611414529e

summary.json SHA-256:
265f5a9d10d36cde4c19fc3350d89fd89779be811b79e76286a615d6bc1ad65e

calibration_comparison.json SHA-256:
bc7fb825bd539084612f28371a7a9990f830cfabd5f2e45346742a23d3b68a0e
```

Committed audit outputs:

```text
auc_invariance.json SHA-256:
7807fd8006439a201d968a098c8375fc781961c6de8defcb102c4360078216e8

fold_calibrator_diagnostics.json SHA-256:
1ffaeec1a365b65a25aa4983ff659bc7631eb2029ae908440b11c2d38caaf96a
```

## Interpretation And Follow-Up

The stored Experiment 007 numbers are internally consistent; no evidence
correction or artifact replacement is required. The smaller calibrated
mean-fold AUC is not a sample-alignment or metric-implementation bug.

The negative coefficient remains a policy risk. A future calibration policy
should detect non-positive slopes and choose an explicit response, such as
retaining the raw ranking, lowering trust, or abstaining. Future training
artifacts should persist native calibrator coefficients rather than requiring
their exact reconstruction from paired predictions.
