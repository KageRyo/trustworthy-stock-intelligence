"""Replay the served training and calibration scheme at past as-of dates.

At each as-of date the replay uses only labels observable by then and applies the serving split
from ``predict_latest_baseline``: Platt calibration on ``--calibration-size`` dates before a
``--drift-size`` drift window, and training on every earlier labeled date. It fits one pooled model
on all tickers and one single-ticker model per ticker, as on-demand analysis does, then scores the
next ``--test-size`` dates with raw, Platt, and monotone Platt probabilities.

The per-ticker history AUC scores each row once, with the latest model fit before it (the next
``--step-size`` dates of every as-of date), and compares pooled and single-ticker rankings of one
ticker's own dates.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

import pandas as pd

from scripts.predict_latest_baseline import (
    fit_baseline_model,
    prepare_frames,
    split_train_calibration_recent,
)
from scripts.walk_forward_experiment import resolve_output_dir
from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.evaluation.metrics import classification_metrics
from tsi.features.sets import FEATURE_SETS, resolve_feature_set
from tsi.models.logistic import LogisticRiskModel
from tsi.trust.calibration import PlattCalibrator, fit_probability_calibrator

CALIBRATIONS = ("platt", "platt_monotone")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="OHLCV CSV input.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--feature-set", choices=list(FEATURE_SETS), default="technical_range")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--drawdown-threshold", type=float, default=-0.05)
    parser.add_argument("--calibration-size", type=int, default=63)
    parser.add_argument("--drift-size", type=int, default=21)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--step-size", type=int, default=21)
    parser.add_argument(
        "--min-history-dates",
        type=int,
        default=400,
        help="Labeled dates required before the first as-of date, for pooled and single models.",
    )
    return parser.parse_args(argv)


def as_of_positions(date_count: int, *, min_history: int, test_size: int, step: int) -> list[int]:
    """Date positions to replay; each leaves ``test_size`` later dates for scoring."""

    if step < 1 or test_size < 1:
        raise ValueError("step and test_size must be positive")
    return list(range(min_history, date_count - test_size, step))


def _fit(
    known: pd.DataFrame, args: argparse.Namespace, columns: list[str]
) -> tuple[LogisticRiskModel, pd.DataFrame] | None:
    """Serving split and model fit, or None when a window lacks both classes."""

    if known["date"].nunique() <= args.calibration_size + args.drift_size:
        return None
    train, calibration, _ = split_train_calibration_recent(
        known,
        calibration_size=args.calibration_size,
        drift_size=args.drift_size,
        train_size=None,
    )
    if train["risk_label"].nunique() < 2 or calibration["risk_label"].nunique() < 2:
        return None
    model, _ = fit_baseline_model(train, columns)
    assert isinstance(model, LogisticRiskModel)
    return model, calibration


def _score(
    model: LogisticRiskModel, calibration: pd.DataFrame, test: pd.DataFrame, columns: list[str]
) -> dict[str, float]:
    raw_calibration = model.predict_proba(calibration[columns].to_numpy())
    raw_test = model.predict_proba(test[columns].to_numpy())
    labels = test["risk_label"].to_numpy()
    row: dict[str, float] = {
        "calibration_rows": float(len(calibration)),
        "calibration_positives": float(calibration["risk_label"].sum()),
        "calibration_auc_raw": classification_metrics(
            calibration["risk_label"].to_numpy(), raw_calibration
        )["auc"],
        "test_rows": float(len(test)),
        "test_positives": float(labels.sum()),
        "auc_raw": classification_metrics(labels, raw_test)["auc"],
    }
    for method in CALIBRATIONS:
        calibrator = fit_probability_calibrator(
            raw_calibration, calibration["risk_label"].to_numpy(), method=method
        )
        if method == "platt" and isinstance(calibrator, PlattCalibrator):
            row["platt_slope"] = float(calibrator.model.coef_[0][0])
        metrics = classification_metrics(labels, calibrator.predict(raw_test))
        row[f"auc_{method}"] = metrics["auc"]
        row[f"brier_{method}"] = metrics["brier_score"]
        row[f"ece_{method}"] = metrics["ece"]
    return row


def _summarize(rows: pd.DataFrame) -> dict[str, float | int]:
    nonpositive = rows["platt_slope"] <= 0
    summary: dict[str, float | int] = {
        "nonpositive_slope": int(nonpositive.sum()),
        "nonpositive_share": float(nonpositive.mean()),
        "median_calibration_positives": float(rows["calibration_positives"].median()),
    }
    for metric in ("auc_raw", *(f"{m}_{c}" for m in ("auc", "brier", "ece") for c in CALIBRATIONS)):
        summary[f"{metric}_mean"] = float(rows[metric].mean())
    for calibration in CALIBRATIONS:
        summary[f"auc_{calibration}_mean_when_nonpositive"] = (
            float(rows.loc[nonpositive, f"auc_{calibration}"].mean()) if nonpositive.any() else None
        )
    return summary


def run(args: argparse.Namespace) -> dict[str, object]:
    output_dir = resolve_output_dir(args.output_dir, root=args.output_root)
    columns = resolve_feature_set(args.feature_set)
    frame, _ = prepare_frames(
        read_ohlcv_csv(args.input),
        horizon=args.horizon,
        drawdown_threshold=args.drawdown_threshold,
        feature_columns=columns,
    )
    frame["date"] = pd.to_datetime(frame["date"])
    dates = pd.Index(sorted(frame["date"].unique()))

    pooled_rows: list[dict[str, object]] = []
    single_rows: list[dict[str, object]] = []
    history: list[pd.DataFrame] = []
    positions = as_of_positions(
        len(dates),
        min_history=args.min_history_dates,
        test_size=args.test_size,
        step=args.step_size,
    )
    for position in positions:
        as_of = dates[position]
        known = frame[frame["date"] <= dates[position - args.horizon]]
        test = frame[(frame["date"] > as_of) & (frame["date"] <= dates[position + args.test_size])]
        next_step = test[test["date"] <= dates[position + args.step_size]]
        pooled = _fit(known, args, columns)
        if pooled is None or test["risk_label"].nunique() < 2:
            continue
        pooled_model, pooled_calibration = pooled
        pooled_rows.append(
            {"as_of": str(as_of.date()), **_score(pooled_model, pooled_calibration, test, columns)}
        )
        for ticker, ticker_test in test.groupby("ticker", sort=True):
            ticker_known = known[known["ticker"] == ticker]
            if ticker_known["date"].nunique() < args.min_history_dates:
                continue
            single = _fit(ticker_known, args, columns)
            if single is None:
                continue
            single_model, single_calibration = single
            ticker_next = next_step[next_step["ticker"] == ticker]
            history.append(
                ticker_next[["ticker", "date", "risk_label"]].assign(
                    pooled=pooled_model.predict_proba(ticker_next[columns].to_numpy()),
                    single=single_model.predict_proba(ticker_next[columns].to_numpy()),
                )
            )
            if ticker_test["risk_label"].nunique() < 2:
                continue
            single_rows.append(
                {
                    "as_of": str(as_of.date()),
                    "ticker": ticker,
                    **_score(single_model, single_calibration, ticker_test, columns),
                }
            )
    if not pooled_rows or not single_rows:
        raise ValueError("No as-of date had enough labeled history in every window")
    pooled_frame = pd.DataFrame(pooled_rows)
    single_frame = pd.DataFrame(single_rows)

    per_ticker = [
        {
            "ticker": ticker,
            "pooled": classification_metrics(rows["risk_label"].to_numpy(), rows["pooled"])["auc"],
            "single": classification_metrics(rows["risk_label"].to_numpy(), rows["single"])["auc"],
        }
        for ticker, rows in pd.concat(history).groupby("ticker", sort=True)
        if rows["risk_label"].nunique() == 2
    ]
    history_auc = pd.DataFrame(per_ticker)

    output_dir.mkdir(parents=True, exist_ok=True)
    pooled_frame.to_csv(output_dir / "pooled_as_of.csv", index=False)
    single_frame.to_csv(output_dir / "single_as_of.csv", index=False)
    history_auc.to_csv(output_dir / "per_ticker_history_auc.csv", index=False)
    reversed_pooled = pooled_frame[pooled_frame["platt_slope"] <= 0]
    summary = {
        "input": str(args.input),
        "input_sha256": file_sha256(args.input),
        "protocol": {
            "feature_interval": "1d",
            "feature_set": args.feature_set,
            "feature_columns": columns,
            "horizon": args.horizon,
            "drawdown_threshold": args.drawdown_threshold,
            "train_window": "every labeled date before calibration (serving default)",
            "calibration_size": args.calibration_size,
            "drift_size": args.drift_size,
            "test_size": args.test_size,
            "step_size": args.step_size,
            "min_history_dates": args.min_history_dates,
            "calibrations": list(CALIBRATIONS),
        },
        "pooled": {
            "as_of_dates": len(pooled_frame),
            **_summarize(pooled_frame),
            "nonpositive_as_of": reversed_pooled[
                ["as_of", "platt_slope", "calibration_auc_raw", "auc_raw", "auc_platt"]
            ].to_dict("records"),
        },
        "single_ticker": {
            "tickers": int(single_frame["ticker"].nunique()),
            "ticker_dates": len(single_frame),
            "tickers_ever_nonpositive": int(
                single_frame.loc[single_frame["platt_slope"] <= 0, "ticker"].nunique()
            ),
            **_summarize(single_frame),
        },
        "per_ticker_history_auc": {
            "tickers": len(history_auc),
            "pooled": float(history_auc["pooled"].mean()),
            "pooled_median": float(history_auc["pooled"].median()),
            "single": float(history_auc["single"].mean()),
            "single_median": float(history_auc["single"].median()),
            "pooled_better_share": float((history_auc["pooled"] > history_auc["single"]).mean()),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    summary = run(parse_args())
    sections = ("pooled", "single_ticker", "per_ticker_history_auc")
    print(json.dumps({key: summary[key] for key in sections}, indent=2))


if __name__ == "__main__":
    main()
