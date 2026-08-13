from __future__ import annotations

import json

import pytest

from tsi import (
    DEFAULT_FEATURE_COLUMNS,
    LogisticRiskModel,
    __version__,
    build_technical_features,
    classification_metrics,
)
from tsi.cli import main


def test_public_package_api_exposes_version_and_reusable_primitives() -> None:
    assert __version__ == "0.4.1"
    assert DEFAULT_FEATURE_COLUMNS
    assert LogisticRiskModel
    assert callable(build_technical_features)
    assert callable(classification_metrics)


def test_cli_version_is_available(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert capsys.readouterr().out.strip() == "tsi 0.4.1"


def test_cli_inspect_csv_preserves_numeric_ticker_symbols(tmp_path, capsys) -> None:
    path = tmp_path / "ohlcv.csv"
    path.write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-01,0050,100,1000\n"
        "2026-01-02,2330,101,1100\n",
        encoding="utf-8",
    )

    assert main(["inspect-csv", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "dataset_summary.v1"
    assert payload["tickers"] == ["0050", "2330"]
    assert payload["row_count"] == 2


def test_cli_evaluate_emits_typed_metric_summary(tmp_path, capsys) -> None:
    path = tmp_path / "predictions.csv"
    path.write_text(
        "ticker,risk_label,calibrated_risk_probability\n"
        "2330,0,0.10\n"
        "2330,1,0.90\n",
        encoding="utf-8",
    )

    assert main(["evaluate", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "evaluation_summary.v1"
    assert payload["metrics"]["auc"] == 1.0
    assert payload["metrics"]["support"] == 2.0
