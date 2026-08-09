"""Tests for schema-first Trustworthy AI audit artifacts."""

from __future__ import annotations

import argparse
import json

from scripts.generate_tai_audit import run
from tsi.trust.tai_audit import build_tai_audit, render_tai_audit_markdown


def _summary() -> dict[str, object]:
    return {
        "input": "/secure/ohlcv.csv",
        "input_sha256": "a" * 64,
        "model_type": "logistic",
        "feature_columns": ["return_1d", "volume_ratio_5d"],
        "fold_count": 39,
        "horizon": 5,
        "purge_size": 5,
        "calibration_method": "platt",
        "threshold_objective": "f1",
        "universe_membership": {"status": "not_supplied"},
        "summary": {
            "calibrated": {"auc": 0.61, "pr_auc": 0.16, "brier_score": 0.09, "ece": 0.04},
            "tuned": {"false_discovery_rate": 0.82, "f1": 0.21},
        },
    }


def _manifest() -> dict[str, object]:
    return {"downloaded_at_utc": "2026-08-09T00:00:00+00:00", "downloaded_ticker_count": 6, "row_count": 16920}


def test_build_tai_audit_exposes_missing_membership_and_high_fdr() -> None:
    audit = build_tai_audit(
        _summary(),
        data_manifest=_manifest(),
        known_limitations=["Current-universe pilot."],
    )

    assert audit.data.data_as_of == "2026-08-09T00:00:00+00:00"
    assert audit.dimensions["transparency"].status == "met"
    assert audit.dimensions["accuracy"].status == "partial"
    assert audit.dimensions["safety"].status == "open"
    assert audit.dimensions["fairness"].status == "open"
    assert any("Point-in-time universe" in risk for risk in audit.open_risks)
    assert any("0.8200" in risk for risk in audit.open_risks)


def test_build_tai_audit_marks_missing_freshness_visible() -> None:
    audit = build_tai_audit(_summary(), feature_interval="5m")

    assert audit.data.data_as_of is None
    assert audit.data.feature_interval == "5m"
    assert any("freshness is unknown" in risk for risk in audit.open_risks)
    rendered = render_tai_audit_markdown(audit)
    assert "| transparency | met |" in rendered
    assert "Data as of: `unknown`" in rendered


def test_generate_tai_audit_writes_json_and_markdown(tmp_path) -> None:
    summary_path = tmp_path / "summary.json"
    manifest_path = tmp_path / "metadata.json"
    output_path = tmp_path / "audit.json"
    markdown_path = tmp_path / "audit.md"
    summary_path.write_text(json.dumps(_summary()), encoding="utf-8")
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    result = run(
        argparse.Namespace(
            summary=summary_path,
            output=output_path,
            data_manifest=manifest_path,
            warning_eval=None,
            markdown_output=markdown_path,
            run_id="tai-fixture",
            data_as_of=None,
            feature_interval="1d",
            known_limitation=["Fixture-only."],
        )
    )

    assert result["run_id"] == "tai-fixture"
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "tai_audit.v1"
    assert markdown_path.read_text(encoding="utf-8").startswith("# Trustworthy AI Audit")
