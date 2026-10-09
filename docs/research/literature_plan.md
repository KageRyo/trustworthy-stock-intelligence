# Literature Plan

## Reading Topic

```text
Trustworthy Stock Risk Alerting
```

The first research milestone focuses on trustworthy risk early-warning rather than full multimodal stock prediction. Multimodal modeling, candlestick images, and LLM-based event reasoning are treated as later extensions.

## Reading Spine

The literature review should support this path:

```text
financial time-series prediction
stock risk warning
probability calibration
uncertainty estimation
selective prediction
explainable AI
auditable deployment
```

## Priority Themes

### 1. Financial Time-Series XAI

Purpose:

```text
Understand how financial time-series models can provide explanations that are useful and auditable.
```

Questions:

- What explanation methods are commonly used for financial time series?
- Which explanations are stable enough for risk warning?
- How should explanations be reported with warning outputs?

### 2. Uncertainty and Calibration

Purpose:

```text
Support calibrated confidence, reliability diagrams, ECE, and uncertainty-aware warning decisions.
```

Questions:

- Are raw model probabilities reliable?
- Which calibration methods work under class imbalance?
- How should uncertainty affect alert/watch/abstain decisions?

### 3. Stock Prediction Baselines

Purpose:

```text
Establish baseline model families and avoid overclaiming deep learning novelty.
```

Questions:

- How do classical baselines compare with tree-based models?
- What feature sets are commonly used?
- How do prior works avoid or fail to avoid temporal leakage?

### 4. Risk Warning and Selective Prediction

Purpose:

```text
Move the thesis away from forced prediction and toward trustworthy warning decisions.
```

Questions:

- When should a model abstain?
- How should coverage and selective risk be reported?
- Does abstention reduce false alarms while preserving useful recall?

### 5. Explainability and Auditability

Purpose:

```text
Connect model outputs to a reproducible risk-warning record.
```

Questions:

- What should be logged for each warning?
- How should feature explanations be attached to calibrated probabilities?
- What metadata is required for reproducibility?

## Initial Must-Read Papers

The first reading list should prioritize:

```text
A Survey of Explainable Artificial Intelligence in Financial Time Series Forecasting
A Survey on Uncertainty Estimation in Deep Learning Classification Systems
Temporal Relational Ranking for Stock Prediction
DeepLOB
Stock Movement Prediction Based on Bi-Typed Hybrid-Relational Market Knowledge Graph
Stock Movement Prediction and Portfolio Management via Multimodal Learning with Transformer
Follow the Will of the Market: A Context-Informed Drift-Aware Method for Stock Prediction
Datasheets for Datasets
```

## Deferred Reading

The following themes are deferred until Milestone 1 is stable:

- candlestick image modeling
- full multimodal fusion
- LLM event reasoning
- social-media sentiment
- high-frequency limit order book modeling

These topics are relevant, but they should not drive the first implementation phase.
