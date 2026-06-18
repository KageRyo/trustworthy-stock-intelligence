"""Streamlit dashboard for trust experiment artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

DEFAULT_RUN_DIR = Path(
    "experiments/005_temporal_transformer_trust/runs/platt_entropy_multiplicative_wr08"
)
DEFAULT_API_BASE_URL = os.getenv("TSI_DASHBOARD_API_BASE_URL", "http://localhost:8080")
API_TIMEOUT_SECONDS = 5.0
METRIC_ORDER = ("auc", "f1", "brier_score", "ece", "precision", "recall")
WARNING_LEVELS = ("alert", "watch", "abstain", "no_alert")
LIVE_WARNING_COLUMNS = [
    "date",
    "ticker",
    "warning_level",
    "calibrated_risk_probability",
    "trust_score",
    "uncertainty_score",
    "reason_codes",
]


@dataclass(frozen=True)
class RunArtifacts:
    """Loaded files for one experiment run."""

    run_dir: Path
    summary: dict[str, Any]
    warning_eval: dict[str, Any]
    diagnostics: dict[str, Any]
    threshold_sweep: pd.DataFrame
    reliability_bins: pd.DataFrame | None = None


@dataclass(frozen=True)
class LiveAPIData:
    """Loaded payloads from the Go warning API."""

    health: dict[str, Any]
    status: dict[str, Any]
    current_model: dict[str, Any]
    alert_warnings: dict[str, Any]
    watch_warnings: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_run_artifacts(run_dir: Path) -> RunArtifacts:
    """Load required dashboard artifacts from an experiment run directory."""

    required = {
        "summary": run_dir / "summary.json",
        "warning_eval": run_dir / "warning_eval.json",
        "diagnostics": run_dir / "diagnostics.json",
        "threshold_sweep": run_dir / "threshold_sweep.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing dashboard artifact(s): {', '.join(missing)}")
    return RunArtifacts(
        run_dir=run_dir,
        summary=load_json(required["summary"]),
        warning_eval=load_json(required["warning_eval"]),
        diagnostics=load_json(required["diagnostics"]),
        threshold_sweep=pd.read_csv(required["threshold_sweep"]),
        reliability_bins=_load_optional_csv(run_dir / "reliability_bins.csv"),
    )


def normalize_api_base_url(base_url: str) -> str:
    """Normalize API base URL text from dashboard input."""

    return base_url.strip().rstrip("/")


def fetch_api_json(
    base_url: str,
    endpoint: str,
    *,
    params: dict[str, object] | None = None,
    timeout: float = API_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch one JSON payload from the Go API."""

    url = f"{normalize_api_base_url(base_url)}/{endpoint.lstrip('/')}"
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def load_live_api_data(
    base_url: str,
    *,
    limit: int = 20,
    timeout: float = API_TIMEOUT_SECONDS,
) -> LiveAPIData:
    """Load dashboard payloads from the Go warning API."""

    return LiveAPIData(
        health=fetch_api_json(base_url, "/health", timeout=timeout),
        status=fetch_api_json(base_url, "/api/v1/status", timeout=timeout),
        current_model=fetch_api_json(base_url, "/api/v1/models/current", timeout=timeout),
        alert_warnings=fetch_api_json(
            base_url,
            "/api/v1/warnings/latest",
            params={"level": "alert", "sort": "trust_score", "order": "desc", "limit": limit},
            timeout=timeout,
        ),
        watch_warnings=fetch_api_json(
            base_url,
            "/api/v1/warnings/latest",
            params={
                "level": "watch",
                "sort": "calibrated_risk_probability",
                "order": "desc",
                "limit": limit,
            },
            timeout=timeout,
        ),
    )


def build_live_warning_frame(batch: dict[str, Any]) -> pd.DataFrame:
    """Build a tabular view from a live API warning batch."""

    records = batch.get("records", [])
    if not isinstance(records, list) or not records:
        return pd.DataFrame(columns=LIVE_WARNING_COLUMNS)
    frame = pd.DataFrame(records)
    if "reason_codes" in frame.columns:
        frame["reason_codes"] = frame["reason_codes"].apply(
            lambda values: ", ".join(values) if isinstance(values, list) else values
        )
    available_columns = [column for column in LIVE_WARNING_COLUMNS if column in frame.columns]
    return frame.loc[:, available_columns]


def build_warning_distribution_frame(overall: dict[str, Any]) -> pd.DataFrame:
    """Build warning-level count/rate rows."""

    return pd.DataFrame(
        {
            "warning_level": list(WARNING_LEVELS),
            "count": [float(overall.get(f"{level}_count", 0.0)) for level in WARNING_LEVELS],
            "rate": [float(overall.get(f"{level}_rate", 0.0)) for level in WARNING_LEVELS],
        }
    )


def build_metric_comparison_frame(summary: dict[str, Any]) -> pd.DataFrame:
    """Build raw/calibrated/tuned metric comparison rows."""

    sections = summary.get("summary", {})
    rows = []
    for metric in METRIC_ORDER:
        rows.append(
            {
                "metric": metric,
                "raw": _metric_value(sections, "raw", metric),
                "calibrated": _metric_value(sections, "calibrated", metric),
                "tuned": _metric_value(sections, "tuned", metric),
            }
        )
    return pd.DataFrame(rows)


def _load_optional_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def select_threshold_tables(sweep: pd.DataFrame, *, limit: int = 10) -> dict[str, pd.DataFrame]:
    """Select threshold policy tables for the dashboard."""

    alerting = sweep[sweep.get("alert_rate", 0.0) > 0.0].copy()
    candidate_source = alerting if not alerting.empty else sweep.copy()
    balanced = candidate_source[
        candidate_source["coverage"].between(0.25, 0.50)
        & candidate_source["alert_rate"].between(0.005, 0.08)
    ]
    if balanced.empty:
        balanced = candidate_source
    conservative = candidate_source[candidate_source["coverage"].between(0.10, 0.30)]
    if conservative.empty:
        conservative = candidate_source
    broad = candidate_source[candidate_source["coverage"].between(0.50, 0.70)]
    if broad.empty:
        broad = candidate_source

    return {
        "balanced": _rank_policy_table(balanced, ("selective_risk", "alert_false_alarm_rate"), limit),
        "conservative": _rank_policy_table(
            conservative,
            ("alert_false_alarm_rate", "selective_risk"),
            limit,
        ),
        "broad": _rank_policy_table(broad, ("alert_miss_rate", "selective_risk"), limit),
        "top_by_selective_risk": _rank_policy_table(
            candidate_source,
            ("selective_risk", "alert_false_alarm_rate"),
            limit,
        ),
        "top_by_alert_precision": _rank_policy_table(
            candidate_source,
            ("alert_precision", "alert_false_alarm_rate"),
            limit,
            ascending=(False, True),
        ),
    }


def _metric_value(sections: Any, section: str, metric: str) -> float | None:
    if not isinstance(sections, dict):
        return None
    values = sections.get(section, {})
    if not isinstance(values, dict) or metric not in values:
        return None
    return float(values[metric])


def _rank_policy_table(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    limit: int,
    *,
    ascending: tuple[bool, ...] | None = None,
) -> pd.DataFrame:
    sort_columns = [column for column in columns if column in frame.columns]
    if not sort_columns:
        return frame.head(limit).reset_index(drop=True)
    sort_ascending = list(ascending) if ascending is not None else [True] * len(sort_columns)
    sort_ascending = sort_ascending[: len(sort_columns)]
    return frame.sort_values(sort_columns, ascending=sort_ascending).head(limit).reset_index(drop=True)


def _diagnostic_quantile_frame(diagnostics: dict[str, Any]) -> pd.DataFrame:
    rows = []
    columns = diagnostics.get("columns", {})
    if not isinstance(columns, dict):
        return pd.DataFrame()
    for column, summary in columns.items():
        if not isinstance(summary, dict):
            continue
        quantiles = summary.get("quantiles", {})
        if not isinstance(quantiles, dict):
            continue
        row = {"column": column, "mean": summary.get("mean"), "std": summary.get("std")}
        row.update(quantiles)
        rows.append(row)
    return pd.DataFrame(rows)


def _load_predictions(path: Path) -> pd.DataFrame:
    columns = [
        "date",
        "ticker",
        "risk_label",
        "risk_probability",
        "calibrated_risk_probability",
        "uncertainty_score",
        "trust_score",
        "alert_threshold",
        "warning_level",
    ]
    frame = pd.read_csv(path, usecols=lambda column: column in columns)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values(["ticker", "date"]).reset_index(drop=True)


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _format_number(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "n/a"


def _first_present(*values: Any, default: str = "n/a") -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return default


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="TSI Trust Dashboard", layout="wide")
    st.title("Trust Experiment Viewer")

    run_dir = Path(st.sidebar.text_input("Run directory", str(DEFAULT_RUN_DIR)))
    api_base_url = st.sidebar.text_input("API Base URL", DEFAULT_API_BASE_URL)
    api_limit = int(st.sidebar.number_input("API warning limit", min_value=1, max_value=100, value=20))
    try:
        artifacts = load_run_artifacts(run_dir)
    except FileNotFoundError as error:
        st.error(str(error))
        return

    summary = artifacts.summary
    overall = artifacts.warning_eval.get("overall", {})
    diagnostics = artifacts.diagnostics
    training_config = summary.get("training_config", {})
    trust_config = summary.get("trust_config", {})

    st.caption(str(artifacts.run_dir))
    overview_cols = st.columns(6)
    overview_cols[0].metric("Model", "Temporal Transformer")
    overview_cols[1].metric("Calibration", str(trust_config.get("calibration_method", "n/a")))
    overview_cols[2].metric("Uncertainty", str(trust_config.get("uncertainty_method", "n/a")))
    overview_cols[3].metric("Trust Score", str(trust_config.get("trust_score_method", "n/a")))
    overview_cols[4].metric("GPU Count", _format_number(training_config.get("max_gpu_count")))
    overview_cols[5].metric("Rows", _format_number(diagnostics.get("row_count")))

    tabs = st.tabs(["Overview", "Diagnostics", "Thresholds", "Ticker View", "Live API", "Report"])

    with tabs[0]:
        metric_cols = st.columns(8)
        metric_cols[0].metric("Alert Rate", _format_percent(overall.get("alert_rate")))
        metric_cols[1].metric("Watch Rate", _format_percent(overall.get("watch_rate")))
        metric_cols[2].metric("No Alert Rate", _format_percent(overall.get("no_alert_rate")))
        metric_cols[3].metric("Alert Precision", _format_percent(overall.get("alert_precision")))
        metric_cols[4].metric("False Alarm Rate", _format_percent(overall.get("alert_false_alarm_rate")))
        metric_cols[5].metric("Coverage", _format_percent(overall.get("coverage")))
        metric_cols[6].metric("Alert Recall", _format_percent(overall.get("alert_recall")))
        metric_cols[7].metric("Positive Rate", _format_percent(diagnostics.get("positive_rate")))

        left, right = st.columns([1, 1])
        warning_distribution = build_warning_distribution_frame(overall)
        with left:
            st.subheader("Warning Distribution")
            st.bar_chart(warning_distribution.set_index("warning_level")["count"])
            st.dataframe(warning_distribution, hide_index=True, width="stretch")
        with right:
            st.subheader("Calibration Comparison")
            comparison = build_metric_comparison_frame(summary)
            st.dataframe(comparison, hide_index=True, width="stretch")
            chart = comparison[comparison["metric"].isin(["brier_score", "ece"])].set_index("metric")
            st.bar_chart(chart[["raw", "calibrated"]])
            if artifacts.reliability_bins is not None:
                st.subheader("Reliability Bins")
                reliability_bins = artifacts.reliability_bins
                st.dataframe(reliability_bins, hide_index=True, width="stretch")
                if {
                    "bin_upper",
                    "mean_predicted_probability",
                    "observed_positive_rate",
                }.issubset(reliability_bins.columns):
                    st.line_chart(
                        reliability_bins.set_index("bin_upper")[
                            ["mean_predicted_probability", "observed_positive_rate"]
                        ]
                    )

    with tabs[1]:
        st.subheader("Probability And Trust Diagnostics")
        diagnostic_frame = _diagnostic_quantile_frame(diagnostics)
        st.dataframe(diagnostic_frame, hide_index=True, width="stretch")
        readiness = diagnostics.get("decision_readiness", {})
        st.json(readiness)

    with tabs[2]:
        st.subheader("Threshold Sweep")
        tables = select_threshold_tables(artifacts.threshold_sweep)
        selected = st.selectbox("Policy view", list(tables.keys()))
        st.dataframe(tables[selected], hide_index=True, width="stretch")

    with tabs[3]:
        predictions_path = artifacts.run_dir / "predictions.csv"
        if not predictions_path.exists():
            st.info(
                "Prediction CSV is not committed. Place predictions.csv under the run folder "
                "to enable ticker-level views."
            )
        else:
            predictions = _load_predictions(predictions_path)
            ticker = st.selectbox("Ticker", sorted(predictions["ticker"].dropna().unique()))
            ticker_frame = predictions[predictions["ticker"] == ticker].copy()
            latest = ticker_frame.tail(10).sort_values("date", ascending=False)
            st.dataframe(latest, hide_index=True, width="stretch")
            series = ticker_frame.set_index("date")[
                [
                    "calibrated_risk_probability",
                    "uncertainty_score",
                    "trust_score",
                    "alert_threshold",
                ]
            ]
            st.line_chart(series)
            st.bar_chart(ticker_frame.set_index("date")["warning_level"].value_counts())

    with tabs[4]:
        st.subheader("Live API")
        try:
            live_api = load_live_api_data(api_base_url, limit=api_limit)
        except requests.RequestException as error:
            st.error(f"API request failed: {error}")
        except ValueError as error:
            st.error(str(error))
        else:
            health = live_api.health
            status = live_api.status
            current_model = live_api.current_model

            st.subheader("API Health")
            api_cols = st.columns(6)
            api_cols[0].metric("API Health", str(health.get("status", "n/a")))
            api_cols[1].metric("Warnings Loaded", str(status.get("warnings_loaded", "n/a")))
            api_cols[2].metric("Generated At", _first_present(status.get("generated_at")))
            api_cols[3].metric("Record Count", _format_number(status.get("record_count")))
            api_cols[4].metric("Last Loaded At", _first_present(status.get("last_loaded_at")))
            last_error = _first_present(status.get("last_error"), health.get("last_error"), default="none")
            api_cols[5].metric("Last Error", last_error)
            if last_error != "none":
                st.warning(last_error)

            st.subheader("Current Model")
            model_cols = st.columns(4)
            model_cols[0].metric("Model", str(current_model.get("model", "n/a")))
            model_cols[1].metric("Model Bundle", str(current_model.get("model_bundle", "n/a")))
            model_cols[2].metric("Generated At", _first_present(current_model.get("generated_at")))
            model_cols[3].metric("Record Count", _format_number(current_model.get("record_count")))

            alert_frame = build_live_warning_frame(live_api.alert_warnings)
            watch_frame = build_live_warning_frame(live_api.watch_warnings)

            st.subheader("Latest Alerts")
            st.dataframe(alert_frame, hide_index=True, width="stretch")
            st.subheader("Latest Watches")
            st.dataframe(watch_frame, hide_index=True, width="stretch")

            with st.expander("Raw API payloads"):
                st.json(
                    {
                        "health": live_api.health,
                        "status": live_api.status,
                        "current_model": live_api.current_model,
                    }
                )

    with tabs[5]:
        report_path = artifacts.run_dir / "report.md"
        if report_path.exists():
            st.markdown(report_path.read_text(encoding="utf-8"))
        else:
            st.warning("report.md not found for this run.")


if __name__ == "__main__":
    main()
