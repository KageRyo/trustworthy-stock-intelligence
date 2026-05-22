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
