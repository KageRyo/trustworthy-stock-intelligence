# Experiment 004: Explainability

## Purpose

This experiment track evaluates explanation factors for risk warnings.

## Initial Scope

The first milestone focuses on tabular technical and market features. Explanations should identify
which features contributed to a warning decision.

## Candidate Methods

```text
model coefficients for Logistic Regression
feature importance for tree models
SHAP for tree-based baselines
```

## Reporting

Explanations should be reported together with:

```text
risk probability
calibrated confidence
uncertainty estimate
warning level
```
