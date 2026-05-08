# Experiment 003: Calibration

## Purpose

This experiment track evaluates whether calibrated probabilities improve the reliability of stock risk warnings.

## Methods

Candidate methods:

```text
raw probability
Platt scaling
isotonic calibration
```

## Metrics

```text
Brier Score
Expected Calibration Error
Reliability Diagram
Calibration Curve
High-Confidence Precision
```

## Notes

Calibration must be fit on a calibration window that occurs after training and before testing.
