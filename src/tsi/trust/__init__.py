"""Uncertainty, trust-score, and human-over-the-loop decision utilities."""

from tsi.trust.decision import TrustDecisionConfig, assign_trust_decisions
from tsi.trust.trust_score import (
    combine_epistemic_uncertainty,
    compute_reliability_trust,
    compute_trust_score,
    data_quality_scores,
)
from tsi.trust.uncertainty import (
    ClassConditionalConformal,
    FeatureNoveltyScorer,
    binary_entropy_uncertainty,
    empirical_percentile,
    ensemble_disagreement,
    margin_uncertainty,
)

__all__ = [
    "ClassConditionalConformal",
    "FeatureNoveltyScorer",
    "TrustDecisionConfig",
    "assign_trust_decisions",
    "binary_entropy_uncertainty",
    "combine_epistemic_uncertainty",
    "compute_reliability_trust",
    "compute_trust_score",
    "data_quality_scores",
    "empirical_percentile",
    "ensemble_disagreement",
    "margin_uncertainty",
]
