"""Tests for the calibration-drift trust gate."""

from __future__ import annotations

import pytest

from tsi.evaluation.drift import CalibrationDriftConfig, assess_calibration_drift


def _metrics(*, positive_rate: float, ece: float, brier_score: float) -> dict[str, float]:
    return {
        "positive_rate": positive_rate,
        "ece": ece,
        "brier_score": brier_score,
    }


def test_stable_metrics_do_not_lower_trust() -> None:
    assessment = assess_calibration_drift(
        _metrics(positive_rate=0.1, ece=0.03, brier_score=0.08),
        _metrics(positive_rate=0.12, ece=0.04, brier_score=0.09),
    )

    assert assessment.degraded is False
    assert assessment.abstain is False
    assert assessment.trust_multiplier == 1.0


def test_two_drift_signals_trigger_low_trust_and_abstention() -> None:
    assessment = assess_calibration_drift(
        _metrics(positive_rate=0.04, ece=0.01, brier_score=0.04),
        _metrics(positive_rate=0.4, ece=0.3, brier_score=0.35),
    )

    assert assessment.signals == ("event_rate_shift", "ece_increase", "brier_increase")
    assert assessment.low_trust is True
    assert assessment.abstain is True
    assert assessment.trust_multiplier == 0.5


def test_invalid_metrics_fail_closed() -> None:
    with pytest.raises(ValueError, match="positive_rate"):
        assess_calibration_drift({}, _metrics(positive_rate=0.1, ece=0.1, brier_score=0.1))


def test_config_rejects_invalid_abstain_count() -> None:
    with pytest.raises(ValueError, match="abstain_signal_count"):
        assess_calibration_drift(
            _metrics(positive_rate=0.1, ece=0.1, brier_score=0.1),
            _metrics(positive_rate=0.1, ece=0.1, brier_score=0.1),
            config=CalibrationDriftConfig(abstain_signal_count=0),
        )
