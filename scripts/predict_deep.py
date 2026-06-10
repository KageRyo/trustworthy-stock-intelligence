"""Run batch inference from a saved Temporal Transformer model bundle."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from tsi.artifacts.model_bundle import load_model_bundle
from tsi.features.technical import build_technical_features
from tsi.models.temporal_transformer import TemporalTransformerRiskModel
from tsi.serving.schema import build_prediction_batch, write_prediction_batch_json
from tsi.training.dataset import SequenceDataset, build_sequence_dataset
from tsi.training.trainer import (
    predict_probabilities,
    transform_sequence_features,
)
from tsi.trust.decision import TrustDecisionConfig, assign_trust_decisions
from tsi.trust.reason_codes import build_reason_codes
from tsi.trust.trust_score import compute_trust_score
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="OHLCV CSV input.")
    parser.add_argument("--model-bundle", type=Path, required=True, help="Saved model bundle directory.")
    parser.add_argument("--output", type=Path, required=True, help="Prediction CSV output.")
    parser.add_argument("--json-output", type=Path, default=None, help="Optional serving JSON output.")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--latest-only", action="store_true", help="Keep only the latest row per ticker.")
    return parser.parse_args(argv)


def build_inference_frame(
    ohlcv: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
) -> pd.DataFrame:
    """Build feature rows for inference without future-label requirements."""

    featured = build_technical_features(ohlcv)
    frame = featured.dropna(subset=list(feature_columns)).copy()
    frame["risk_label"] = 0
    return frame.sort_values(["date", "ticker"]).reset_index(drop=True)


def select_latest_per_ticker(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the most recent prediction row for each ticker."""

    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"])
    return (
        working.sort_values(["ticker", "date"])
        .groupby("ticker", as_index=False, sort=True)
        .tail(1)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )


def build_latest_sequence_dataset(
    frame: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    lookback: int,
) -> SequenceDataset:
    """Build one latest inference window per ticker."""

    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if not feature_columns:
        raise ValueError("feature_columns must not be empty")

    feature_columns_tuple = tuple(feature_columns)
    required_columns = ["date", "ticker", *feature_columns_tuple]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    source_index_col = "__tsi_source_index"
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"])
    working[source_index_col] = frame.index
    working = working.sort_values(["ticker", "date", source_index_col]).reset_index(drop=True)

    windows: list[np.ndarray] = []
    metadata_rows: list[dict[str, object]] = []

    for ticker, group in working.groupby("ticker", sort=True):
        if len(group) < lookback:
            continue

        window_rows = group.tail(lookback)
        window = window_rows.loc[:, feature_columns_tuple].to_numpy(dtype=float)
        if not np.isfinite(window).all():
            continue

        start_row = window_rows.iloc[0]
        target_row = window_rows.iloc[-1]
        windows.append(window)
        metadata_rows.append(
            {
                "ticker": ticker,
                "date": target_row["date"],
                "source_index": int(target_row[source_index_col]),
                "window_start_date": start_row["date"],
                "window_end_date": target_row["date"],
            }
        )

    if windows:
        x = np.stack(windows).astype(np.float32)
    else:
        x = np.empty((0, lookback, len(feature_columns_tuple)), dtype=np.float32)

    return SequenceDataset(
        x=x,
        y=np.zeros(x.shape[0], dtype=np.float32),
        metadata=pd.DataFrame(
            metadata_rows,
            columns=["ticker", "date", "source_index", "window_start_date", "window_end_date"],
        ),
        feature_columns=feature_columns_tuple,
        lookback=lookback,
    )


def select_latest_sequence_dataset(dataset: SequenceDataset) -> SequenceDataset:
    """Keep only the latest sequence sample per ticker before model inference."""

    metadata = dataset.metadata.copy()
    metadata["date"] = pd.to_datetime(metadata["date"])
    selected_positions = (
        metadata.reset_index()
        .sort_values(["ticker", "date", "index"])
        .groupby("ticker", as_index=False, sort=True)
        .tail(1)["index"]
        .to_numpy()
    )
    selected_positions = np.sort(selected_positions)
    return SequenceDataset(
        x=dataset.x[selected_positions],
        y=dataset.y[selected_positions],
        metadata=dataset.metadata.iloc[selected_positions].reset_index(drop=True),
        feature_columns=dataset.feature_columns,
        lookback=dataset.lookback,
    )


def _resolve_inference_device(name: str) -> torch.device:
    requested = name.lower()
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return torch.device(requested)


def _uncertainty_scores(probabilities: np.ndarray, *, method: str) -> np.ndarray:
    if method == "entropy":
        return binary_entropy_uncertainty(probabilities)
    if method == "margin":
        return margin_uncertainty(probabilities)
    raise ValueError(f"Unsupported uncertainty method: {method}")


def _build_model(metadata) -> TemporalTransformerRiskModel:
    if metadata.model_type != "temporal_transformer":
        raise ValueError(f"Unsupported model type: {metadata.model_type}")
    return TemporalTransformerRiskModel(**metadata.model_config)


def run_prediction(args: argparse.Namespace) -> pd.DataFrame:
    """Run inference and write prediction CSV."""

    device = _resolve_inference_device(args.device)
    bundle = load_model_bundle(args.model_bundle, map_location=device)
    model = _build_model(bundle.metadata)
    model.load_state_dict(bundle.model_state_dict)
    model = model.to(device)

    ohlcv = pd.read_csv(args.input)
    inference_frame = build_inference_frame(
        ohlcv,
        feature_columns=bundle.metadata.feature_columns,
    )
    if args.latest_only:
        dataset = build_latest_sequence_dataset(
            inference_frame,
            feature_columns=bundle.metadata.feature_columns,
            lookback=bundle.metadata.lookback,
        )
    else:
        dataset = build_sequence_dataset(
            inference_frame,
            feature_columns=bundle.metadata.feature_columns,
            lookback=bundle.metadata.lookback,
        )
    if len(dataset.y) == 0:
        raise ValueError("No inference sequences were created; check lookback and input data")

    features = transform_sequence_features(dataset.x, bundle.standardizer)
    probabilities = predict_probabilities(
        model,
        features,
        batch_size=args.batch_size,
        device=device,
        num_workers=args.num_workers,
    )
    calibrated_probabilities = bundle.calibrator.predict(probabilities)

    trust_config = bundle.metadata.trust_config
    uncertainty = _uncertainty_scores(
        calibrated_probabilities,
        method=str(trust_config.get("uncertainty_method", "entropy")),
    )
    trust_scores = compute_trust_score(
        calibrated_probabilities,
        uncertainty,
        uncertainty_penalty=float(trust_config.get("uncertainty_penalty", 0.5)),
        method=trust_config.get("trust_score_method", "subtractive"),
    )
    decision_config = TrustDecisionConfig(
        alert_threshold=bundle.metadata.alert_threshold,
        watch_threshold=bundle.metadata.watch_threshold,
        trust_threshold=float(trust_config.get("trust_threshold", 0.5)),
        uncertainty_threshold=float(trust_config.get("uncertainty_threshold", 0.8)),
    )
    warning_levels = assign_trust_decisions(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        config=decision_config,
    )
    reason_codes = build_reason_codes(
        calibrated_probabilities=calibrated_probabilities,
        uncertainty_scores=uncertainty,
        trust_scores=trust_scores,
        warning_levels=warning_levels,
        config=decision_config,
    )
    predictions = dataset.metadata.loc[:, ["date", "ticker"]].assign(
        model=bundle.metadata.model_type,
        risk_probability=probabilities,
        calibrated_risk_probability=calibrated_probabilities,
        calibration_method=bundle.metadata.calibration_method,
        uncertainty_score=uncertainty,
        trust_score=trust_scores,
        alert_threshold=bundle.metadata.alert_threshold,
        watch_threshold=bundle.metadata.watch_threshold,
        warning_level=warning_levels,
        model_bundle=str(args.model_bundle),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    if args.json_output is not None:
        serving_frame = predictions.assign(reason_codes=reason_codes)
        write_prediction_batch_json(build_prediction_batch(serving_frame), args.json_output)
    return predictions


def main() -> None:
    args = parse_args()
    predictions = run_prediction(args)
    print(f"Wrote {len(predictions)} prediction rows to {args.output}")
    if args.json_output is not None:
        print(f"Wrote serving JSON to {args.json_output}")


if __name__ == "__main__":
    main()
