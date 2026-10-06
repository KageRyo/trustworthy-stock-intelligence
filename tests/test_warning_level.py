"""Tests for warning-threshold selection."""

from __future__ import annotations

import numpy as np

from tsi.labeling.warning_level import assign_warning_levels, select_alert_threshold


def test_threshold_selection_can_move_below_default_half() -> None:
    labels = np.array([1, 1, 0, 0, 0])
    probabilities = np.array([0.42, 0.38, 0.25, 0.15, 0.05])

    result = select_alert_threshold(labels, probabilities, objective="f1")

    assert result.threshold < 0.5
    assert result.metrics["f1"] >= 0.79


def test_warning_level_mapping_respects_alert_and_watch_thresholds() -> None:
    levels = assign_warning_levels(
        np.array([0.2, 0.45, 0.8]),
        alert_threshold=0.7,
        watch_threshold=0.4,
    )

    assert levels.tolist() == ["no_alert", "watch", "alert"]


def _ranked_rows() -> tuple[np.ndarray, np.ndarray]:
    # Ten rows ranked by probability; precision falls as the threshold drops.
    probabilities = np.array([0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2])
    labels = np.array([1, 1, 1, 0, 1, 0, 0, 1, 0, 0])
    return labels, probabilities


def test_target_precision_policy_picks_lowest_threshold_meeting_target() -> None:
    from tsi.labeling.warning_level import AlertPolicy, select_alert_threshold_by_policy

    labels, probabilities = _ranked_rows()

    result = select_alert_threshold_by_policy(
        labels,
        probabilities,
        AlertPolicy(kind="target_precision", target=0.8, min_alerts=1),
    )

    assert result.target_met
    assert result.threshold == 0.7
    assert result.metrics["precision"] >= 0.8
    assert result.metrics["recall"] == 0.8


def test_target_precision_policy_falls_back_when_target_is_unreachable() -> None:
    from tsi.labeling.warning_level import AlertPolicy, select_alert_threshold_by_policy

    labels = np.array([1, 0, 1, 0, 0, 0])
    probabilities = np.array([0.9, 0.85, 0.6, 0.55, 0.3, 0.1])

    result = select_alert_threshold_by_policy(
        labels,
        probabilities,
        AlertPolicy(kind="target_precision", target=0.9, min_alerts=2),
    )

    assert not result.target_met
    assert result.metrics["prediction_rate"] >= 2 / 6
    assert result.metrics["precision"] == 2 / 3


def test_target_precision_policy_requires_minimum_alert_support() -> None:
    from tsi.labeling.warning_level import AlertPolicy, select_alert_threshold_by_policy

    labels, probabilities = _ranked_rows()

    result = select_alert_threshold_by_policy(
        labels,
        probabilities,
        AlertPolicy(kind="target_precision", target=1.0, min_alerts=4),
    )

    assert not result.target_met
    assert result.metrics["prediction_rate"] * len(labels) >= 4


def test_alert_rate_policy_caps_calibration_alert_rate() -> None:
    from tsi.labeling.warning_level import AlertPolicy, select_alert_threshold_by_policy

    labels, probabilities = _ranked_rows()

    result = select_alert_threshold_by_policy(
        labels,
        probabilities,
        AlertPolicy(kind="alert_rate", target=0.3),
    )

    assert result.target_met
    assert result.metrics["prediction_rate"] <= 0.3
    assert result.threshold == 0.85


def test_f1_policy_matches_existing_objective() -> None:
    from tsi.labeling.warning_level import AlertPolicy, select_alert_threshold_by_policy

    labels, probabilities = _ranked_rows()

    result = select_alert_threshold_by_policy(labels, probabilities, AlertPolicy(kind="f1"))

    assert result.threshold == select_alert_threshold(labels, probabilities).threshold
    assert result.target_met


def test_alert_policy_validates_targets() -> None:
    import pytest

    from tsi.labeling.warning_level import AlertPolicy

    with pytest.raises(ValueError, match="target"):
        AlertPolicy(kind="target_precision")
    with pytest.raises(ValueError, match="target"):
        AlertPolicy(kind="alert_rate", target=1.5)
    with pytest.raises(ValueError, match="min_alerts"):
        AlertPolicy(kind="target_precision", target=0.3, min_alerts=0)


def test_parse_alert_policy_reads_kind_and_target() -> None:
    import pytest

    from tsi.labeling.warning_level import parse_alert_policy

    assert parse_alert_policy("f1").label == "f1"
    policy = parse_alert_policy(" alert_rate:0.05 ", min_alerts=5)
    assert (policy.kind, policy.target, policy.min_alerts) == ("alert_rate", 0.05, 5)
    with pytest.raises(ValueError, match="Unsupported alert policy"):
        parse_alert_policy("top_k:3")
