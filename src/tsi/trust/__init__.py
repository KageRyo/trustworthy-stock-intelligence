"""Uncertainty, trust-score, and human-over-the-loop decision utilities."""

from tsi.trust.decision import TrustDecisionConfig, assign_trust_decisions
from tsi.trust.trust_score import compute_trust_score
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty

__all__ = [
    "TrustDecisionConfig",
    "assign_trust_decisions",
    "binary_entropy_uncertainty",
    "compute_trust_score",
    "margin_uncertainty",
]
