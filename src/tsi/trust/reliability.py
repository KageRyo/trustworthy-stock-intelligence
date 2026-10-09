"""Model- and data-based reliability signals for serving trust scores.

The served ``uncertainty_score`` and ``trust_score`` come from evidence that does
not depend on the risk level itself:

- bootstrap ensemble disagreement (how much the fit changes across resampled dates),
- feature novelty (how far the input sits from the training distribution),
- per-ticker data quality (history depth and staleness).

Disagreement and novelty are ranked against the calibration window, so an
uncertainty of 0.5 means "as uncertain as a typical recent labeled row".

By default the trust score uses data quality only (``epistemic_trust_weight=0``).
Experiment 015 on S&P 100 walk-forward folds found that high-uncertainty rows have
roughly twice the drawdown rate and that alerts blocked by epistemic trust were
more precise than alerts that passed, so epistemic uncertainty must not suppress
alerts. It is still served as ``uncertainty_score``, where it moves low-risk rows to
abstain instead of an overconfident no-alert.
Class-conditional conformal sets are reported as reason codes only. They are a
function of the calibrated probability, so they stay out of the trust score.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict

from tsi.models.ensemble import DateBootstrapEnsemble, ProbabilityModel
from tsi.models.linear import LinearLogitModel, LinearLogitParams, linear_logit_params
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import (
    CalibratorParams,
    ProbabilityCalibrator,
    StoredCalibrator,
    calibrator_params,
)
from tsi.trust.trust_score import combine_epistemic_uncertainty, compute_reliability_trust
from tsi.trust.uncertainty import (
    ClassConditionalConformal,
    ConformalParams,
    FeatureNoveltyScorer,
    NoveltyParams,
    empirical_percentile,
    ensemble_disagreement,
)


@dataclass(frozen=True)
class ReliabilityConfig:
    """Settings for reliability scoring and its reason-code cutoffs."""

    n_members: int = 10
    random_state: int = 42
    conformal_alpha: float = 0.1
    epistemic_trust_weight: float = 0.0
    high_disagreement_percentile: float = 0.9
    out_of_distribution_percentile: float = 0.95
    limited_data_quality: float = 0.75


class ReliabilityParams(BaseModel):
    """Everything a fitted ``ReliabilityAssessor`` needs to score new rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_members: int
    random_state: int
    conformal_alpha: float
    epistemic_trust_weight: float
    high_disagreement_percentile: float
    out_of_distribution_percentile: float
    limited_data_quality: float
    members: list[LinearLogitParams]
    calibrator: CalibratorParams
    novelty: NoveltyParams
    disagreement_reference: list[float]
    novelty_reference: list[float]
    conformal: ConformalParams | None = None


class _MemberEnsemble(Protocol):
    def predict_member_proba(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class _StoredEnsemble:
    members: Sequence[LinearLogitModel]

    def predict_member_proba(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=float)
        return np.vstack([member.predict_proba(values) for member in self.members])


def _member_params(member: object) -> LinearLogitParams:
    if isinstance(member, LinearLogitModel):
        return member.params
    if isinstance(member, LogisticRiskModel):
        return linear_logit_params(member)
    raise ValueError(f"{type(member).__name__} ensemble members cannot be stored")


@dataclass(frozen=True)
class ReliabilityScores:
    """Per-row reliability outputs aligned with the scored feature rows."""

    disagreement: np.ndarray
    disagreement_percentile: np.ndarray
    novelty_percentile: np.ndarray
    uncertainty: np.ndarray
    trust: np.ndarray
    reason_codes: list[list[str]]
    conformal_sets: np.ndarray | None = None


class ReliabilityAssessor:
    """Fit reliability references on train/calibration rows and score new rows."""

    def __init__(
        self,
        config: ReliabilityConfig | None = None,
        *,
        model_factory: Callable[[], ProbabilityModel] = LogisticRiskModel,
    ) -> None:
        self.config = config or ReliabilityConfig()
        self.model_factory = model_factory
        self._ensemble: _MemberEnsemble | None = None
        self._calibrator: ProbabilityCalibrator | None = None
        self._novelty = FeatureNoveltyScorer()
        self._conformal = ClassConditionalConformal(alpha=self.config.conformal_alpha)
        self._disagreement_reference: np.ndarray | None = None
        self._novelty_reference: np.ndarray | None = None
        self._conformal_ready = False

    def fit(
        self,
        *,
        train_features: np.ndarray,
        train_labels: np.ndarray,
        train_groups: np.ndarray,
        calibration_features: np.ndarray,
        calibration_labels: np.ndarray,
        calibrated_calibration_probabilities: np.ndarray,
        calibrator: ProbabilityCalibrator,
    ) -> "ReliabilityAssessor":
        """Fit references; conformal thresholds use the serving model's calibrated outputs.

        The calibrator is fitted on the same calibration rows, so conformal coverage is
        approximate rather than a strict split-conformal guarantee.
        """

        self._calibrator = calibrator
        self._ensemble = DateBootstrapEnsemble(
            self.model_factory,
            n_members=self.config.n_members,
            random_state=self.config.random_state,
        ).fit(train_features, train_labels, groups=train_groups)
        self._novelty.fit(train_features)
        self._disagreement_reference = self._disagreement(calibration_features)
        self._novelty_reference = self._novelty.distance(calibration_features)

        labels = np.asarray(calibration_labels).astype(int)
        self._conformal_ready = np.unique(labels).size == 2
        if self._conformal_ready:
            self._conformal.fit(calibrated_calibration_probabilities, labels)
        return self

    def params(self) -> ReliabilityParams:
        """Export the fitted references so the assessor can be stored and restored."""

        if (
            self._ensemble is None
            or self._calibrator is None
            or self._disagreement_reference is None
            or self._novelty_reference is None
        ):
            raise ValueError("ReliabilityAssessor must be fit before exporting params")
        members = (
            self._ensemble.members_
            if isinstance(self._ensemble, DateBootstrapEnsemble)
            else getattr(self._ensemble, "members", [])
        )
        config = self.config
        return ReliabilityParams(
            n_members=config.n_members,
            random_state=config.random_state,
            conformal_alpha=config.conformal_alpha,
            epistemic_trust_weight=config.epistemic_trust_weight,
            high_disagreement_percentile=config.high_disagreement_percentile,
            out_of_distribution_percentile=config.out_of_distribution_percentile,
            limited_data_quality=config.limited_data_quality,
            members=[_member_params(member) for member in members],
            calibrator=calibrator_params(self._calibrator),
            novelty=self._novelty.params(),
            disagreement_reference=self._disagreement_reference.tolist(),
            novelty_reference=self._novelty_reference.tolist(),
            conformal=self._conformal.params() if self._conformal_ready else None,
        )

    @classmethod
    def from_params(cls, params: ReliabilityParams) -> "ReliabilityAssessor":
        """Rebuild a fitted assessor from exported references, without refitting."""

        assessor = cls(
            ReliabilityConfig(
                n_members=params.n_members,
                random_state=params.random_state,
                conformal_alpha=params.conformal_alpha,
                epistemic_trust_weight=params.epistemic_trust_weight,
                high_disagreement_percentile=params.high_disagreement_percentile,
                out_of_distribution_percentile=params.out_of_distribution_percentile,
                limited_data_quality=params.limited_data_quality,
            )
        )
        assessor._ensemble = _StoredEnsemble(
            [LinearLogitModel(member) for member in params.members]
        )
        assessor._calibrator = StoredCalibrator(params.calibrator)
        assessor._novelty = FeatureNoveltyScorer.from_params(params.novelty)
        assessor._disagreement_reference = np.asarray(params.disagreement_reference, dtype=float)
        assessor._novelty_reference = np.asarray(params.novelty_reference, dtype=float)
        if params.conformal is not None:
            assessor._conformal = ClassConditionalConformal.from_params(params.conformal)
            assessor._conformal_ready = True
        return assessor

    def score(
        self,
        features: np.ndarray,
        *,
        calibrated_probabilities: np.ndarray,
        data_quality: np.ndarray,
    ) -> ReliabilityScores:
        if self._ensemble is None or self._disagreement_reference is None:
            raise ValueError("ReliabilityAssessor must be fit before scoring")
        assert self._novelty_reference is not None
        disagreement = self._disagreement(features)
        disagreement_percentile = empirical_percentile(disagreement, self._disagreement_reference)
        novelty_percentile = empirical_percentile(
            self._novelty.distance(features), self._novelty_reference
        )
        uncertainty = combine_epistemic_uncertainty(
            disagreement_percentile=disagreement_percentile,
            novelty_percentile=novelty_percentile,
        )
        quality = np.asarray(data_quality, dtype=float)
        trust = compute_reliability_trust(
            epistemic_uncertainty=uncertainty,
            data_quality=quality,
            epistemic_weight=self.config.epistemic_trust_weight,
        )
        conformal_sets = (
            self._conformal.prediction_sets(np.asarray(calibrated_probabilities, dtype=float))
            if self._conformal_ready
            else None
        )
        reason_codes = [
            self._row_reason_codes(
                disagreement_percentile[index],
                novelty_percentile[index],
                quality[index],
                None if conformal_sets is None else conformal_sets[index],
            )
            for index in range(len(disagreement))
        ]
        return ReliabilityScores(
            disagreement=disagreement,
            disagreement_percentile=disagreement_percentile,
            novelty_percentile=novelty_percentile,
            uncertainty=uncertainty,
            trust=trust,
            reason_codes=reason_codes,
            conformal_sets=conformal_sets,
        )

    @staticmethod
    def unavailable(rows: int) -> ReliabilityScores:
        """Fail-closed scores when no model could be fitted (for example single-class data)."""

        return ReliabilityScores(
            disagreement=np.ones(rows),
            disagreement_percentile=np.ones(rows),
            novelty_percentile=np.ones(rows),
            uncertainty=np.ones(rows),
            trust=np.zeros(rows),
            reason_codes=[["reliability_unavailable"] for _ in range(rows)],
        )

    def _calibrated_members(self, features: np.ndarray) -> np.ndarray:
        assert self._ensemble is not None and self._calibrator is not None
        members = self._ensemble.predict_member_proba(features)
        return np.vstack([self._calibrator.predict(member) for member in members])

    def _disagreement(self, features: np.ndarray) -> np.ndarray:
        return ensemble_disagreement(self._calibrated_members(features))

    def _row_reason_codes(
        self,
        disagreement_percentile: float,
        novelty_percentile: float,
        data_quality: float,
        conformal_set: np.ndarray | None,
    ) -> list[str]:
        codes: list[str] = []
        if disagreement_percentile >= self.config.high_disagreement_percentile:
            codes.append("ensemble_disagreement_high")
        if novelty_percentile >= self.config.out_of_distribution_percentile:
            codes.append("input_out_of_distribution")
        if data_quality < self.config.limited_data_quality:
            codes.append("limited_data_quality")
        if conformal_set is None:
            codes.append("conformal_set_unavailable")
        elif conformal_set.all():
            codes.append("conformal_set_ambiguous")
        elif conformal_set[1]:
            codes.append("conformal_set_drawdown_only")
        elif conformal_set[0]:
            codes.append("conformal_set_no_drawdown_only")
        else:
            codes.append("conformal_set_empty")
        return codes
