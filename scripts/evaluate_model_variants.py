"""Compare model families and training windows with purged walk-forward evaluation.

Folds are built with the longest fixed training window, so every variant is scored on the same
calibration and test windows. A shorter window trains on the most recent dates of the same fold's
training window, and the ``all`` window adds every earlier labeled row, as serving does. Each
variant fits its model on its train rows, calibrates on the calibration window, picks the serving
alert and watch thresholds on the calibration window, and scores the later test window for ranking
(AUC, PR-AUC), calibration (Brier, ECE), and alert quality. Brier skill uses the longest fixed
window's event rate as the shared reference. Comparisons use paired fold-level bootstrap intervals.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, field
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

# cuBLAS needs a fixed workspace before its first use for deterministic GPU matrix products.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch  # noqa: E402
from torch import nn  # noqa: E402

from scripts.evaluate_feature_sets import (  # noqa: E402
    PAIRED_METRICS,
    compare_to_baseline,
    score_probabilities,
    summarize_set,
)
from scripts.walk_forward_experiment import (  # noqa: E402
    FoldFrames,
    RiskModel,
    WalkForwardFolds,
    add_walk_forward_arguments,
    fit_calibrated_model,
    load_walk_forward_folds,
    resolve_output_dir,
    walk_forward_protocol,
)
from tsi.data.csv import file_sha256  # noqa: E402
from tsi.labeling.warning_level import AlertPolicy, parse_alert_policy  # noqa: E402
from tsi.evaluation.metrics import classification_metrics  # noqa: E402
from tsi.models.logistic import LogisticRiskModel  # noqa: E402
from tsi.training.trainer import resolve_training_device  # noqa: E402
from tsi.trust.calibration import PlattCalibrator, ProbabilityCalibrator  # noqa: E402

RANDOM_STATE = 42
EXPANDING_WINDOW = "all"
HIST_GRADIENT_BOOSTING_PARAMETERS: dict[str, float | int] = {
    "learning_rate": 0.05,
    "max_iter": 200,
    "max_leaf_nodes": 8,
    "min_samples_leaf": 200,
    "l2_regularization": 1.0,
}
MLP_HIDDEN_SIZES = (64, 32)
MLP_PARAMETERS: dict[str, object] = {
    "hidden_sizes": list(MLP_HIDDEN_SIZES),
    "activation": "relu",
    "dropout": 0.1,
    "optimizer": "AdamW",
    "learning_rate": 1e-3,
    "weight_decay": 1e-4,
    "batch_size": 1024,
    "loss": "binary cross-entropy with positive weight negatives / positives",
    "early_stopping": False,
}
MODEL_PARAMETERS: dict[str, dict[str, object]] = {
    "logistic": {"model": "tsi.models.logistic.LogisticRiskModel"},
    "logistic_quadratic": {
        "steps": "median impute, standardize, degree-2 polynomial terms, standardize",
        "classifier": "LogisticRegression(C=1.0, class_weight='balanced', max_iter=2000)",
    },
    "hist_gradient_boosting": {
        **HIST_GRADIENT_BOOSTING_PARAMETERS,
        "early_stopping": False,
        "class_weight": "balanced",
    },
    "mlp": {"steps": "median impute, standardize", **MLP_PARAMETERS},
}
MODEL_FAMILIES = tuple(MODEL_PARAMETERS)
BASELINE_FAMILY = "logistic"


@dataclass
class SklearnRiskModel:
    """Adapter that returns the positive-class probability of an sklearn pipeline."""

    pipeline: Pipeline

    def fit(self, features: np.ndarray, labels: np.ndarray) -> SklearnRiskModel:
        self.pipeline.fit(features, labels)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return self.pipeline.predict_proba(features)[:, 1]


@dataclass
class MLPRiskModel:
    """Small feed-forward network trained with a fixed seed and a fixed number of epochs."""

    device: torch.device
    epochs: int = 20
    seed: int = RANDOM_STATE
    _preprocess: Pipeline = field(init=False, repr=False)
    _network: nn.Module = field(init=False, repr=False)

    def fit(self, features: np.ndarray, labels: np.ndarray) -> MLPRiskModel:
        self._preprocess = Pipeline(
            steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
        )
        inputs = self._tensor(self._preprocess.fit_transform(features))
        targets = torch.as_tensor(labels.astype(np.float32), device=self.device)
        positives = float(targets.sum())
        negatives = float(len(targets)) - positives
        loss_function = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor(
                negatives / positives if positives and negatives else 1.0, device=self.device
            )
        )
        previous_determinism = torch.are_deterministic_algorithms_enabled()
        torch.use_deterministic_algorithms(True)
        try:
            torch.manual_seed(self.seed)
            self._network = self._build_network(inputs.shape[1]).to(self.device)
            optimizer = torch.optim.AdamW(
                self._network.parameters(),
                lr=float(MLP_PARAMETERS["learning_rate"]),
                weight_decay=float(MLP_PARAMETERS["weight_decay"]),
            )
            shuffle = torch.Generator().manual_seed(self.seed)
            batch_size = int(MLP_PARAMETERS["batch_size"])
            self._network.train()
            for _ in range(self.epochs):
                order = torch.randperm(len(inputs), generator=shuffle).to(self.device)
                for start in range(0, len(order), batch_size):
                    batch = order[start : start + batch_size]
                    optimizer.zero_grad(set_to_none=True)
                    logits = self._network(inputs[batch]).squeeze(-1)
                    loss_function(logits, targets[batch]).backward()
                    optimizer.step()
        finally:
            torch.use_deterministic_algorithms(previous_determinism)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        self._network.eval()
        with torch.no_grad():
            logits = self._network(self._tensor(self._preprocess.transform(features)))
        return torch.sigmoid(logits.squeeze(-1)).cpu().numpy().astype(np.float64)

    def _tensor(self, values: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(values, dtype=torch.float32, device=self.device)

    @staticmethod
    def _build_network(input_size: int) -> nn.Module:
        layers: list[nn.Module] = []
        width = input_size
        for hidden in MLP_HIDDEN_SIZES:
            layers.extend(
                [nn.Linear(width, hidden), nn.ReLU(), nn.Dropout(float(MLP_PARAMETERS["dropout"]))]
            )
            width = hidden
        layers.append(nn.Linear(width, 1))
        return nn.Sequential(*layers)


def calibration_slope(calibrator: ProbabilityCalibrator) -> float:
    """Platt slope on the raw probability; negative means calibration reverses the ranking."""

    if isinstance(calibrator, PlattCalibrator):
        return float(calibrator.model.coef_[0][0])
    return float("nan")


def build_model(
    family: str, *, device: torch.device | None = None, mlp_epochs: int = 20
) -> RiskModel:
    """Return an unfitted model for ``family`` with its fixed, recorded parameters."""

    if family == "logistic":
        return LogisticRiskModel(random_state=RANDOM_STATE)
    if family == "logistic_quadratic":
        return SklearnRiskModel(
            Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    ("terms", PolynomialFeatures(degree=2, include_bias=False)),
                    ("term_scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE
                        ),
                    ),
                ]
            )
        )
    if family == "hist_gradient_boosting":
        return SklearnRiskModel(
            Pipeline(
                steps=[
                    (
                        "classifier",
                        HistGradientBoostingClassifier(
                            **HIST_GRADIENT_BOOSTING_PARAMETERS,
                            early_stopping=False,
                            class_weight="balanced",
                            random_state=RANDOM_STATE,
                        ),
                    )
                ]
            )
        )
    if family == "mlp":
        if device is None:
            raise ValueError("The mlp family needs a training device")
        return MLPRiskModel(device=device, epochs=mlp_epochs)
    raise ValueError(f"Unknown model family: {family}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_walk_forward_arguments(parser)
    parser.set_defaults(feature_set="technical_range", train_size=756)
    parser.add_argument(
        "--train-windows",
        default=f"252,756,{EXPANDING_WINDOW}",
        help="Comma-separated training windows in trading dates, plus 'all' for every earlier "
        "labeled row. The longest number must equal --train-size.",
    )
    parser.add_argument("--models", default=",".join(MODEL_FAMILIES))
    parser.add_argument("--alert-policy", default="alert_rate:0.05")
    parser.add_argument("--watch-policy", default="alert_rate:0.2")
    parser.add_argument("--min-alerts", type=int, default=20)
    parser.add_argument("--bootstrap-resamples", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda", help="Training device for the mlp family.")
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow CPU training for the mlp family; for tests only.",
    )
    parser.add_argument("--mlp-epochs", type=int, default=20)
    parser.add_argument(
        "--reuse-per-fold",
        action="store_true",
        help="Rebuild summary.json from the per_fold.csv in --output-dir without refitting.",
    )
    return parser.parse_args(argv)


def parse_train_windows(text: str, *, train_size: int) -> list[str]:
    """Window labels, shortest first and ``all`` last; the longest number must be train_size."""

    items = {item.strip() for item in text.split(",") if item.strip()}
    sizes = sorted(int(item) for item in items if item != EXPANDING_WINDOW)
    if any(size < 1 for size in sizes):
        raise ValueError("--train-windows must contain positive integers")
    if not sizes or sizes[-1] != train_size:
        raise ValueError("The longest numeric --train-windows value must equal --train-size")
    return [str(size) for size in sizes] + (
        [EXPANDING_WINDOW] if EXPANDING_WINDOW in items else []
    )


def parse_model_families(text: str) -> list[str]:
    """Requested families in registry order, always including the logistic baseline."""

    names = {name.strip() for name in text.split(",") if name.strip()}
    unknown = names.difference(MODEL_FAMILIES)
    if unknown:
        raise ValueError(f"Unknown model family: {', '.join(sorted(unknown))}")
    return [name for name in MODEL_FAMILIES if name in names or name == BASELINE_FAMILY]


def variant_name(family: str, window: str) -> str:
    return f"{family}@{window}"


def train_rows_for_window(item: FoldFrames, window: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Training rows for ``window``: the fold's last N dates, or all labeled history for ``all``."""

    if window == EXPANDING_WINDOW:
        dates = pd.to_datetime(frame["date"])
        history = frame[dates < item.fold.train_dates[0]]
        return pd.concat([history, item.train])
    size = int(window)
    if size >= len(item.fold.train_dates):
        return item.train
    recent_dates = pd.DatetimeIndex(item.fold.train_dates[-size:])
    return item.train[pd.to_datetime(item.train["date"]).isin(recent_dates)]


def variant_pairs(families: Sequence[str], windows: Sequence[str]) -> list[tuple[str, str]]:
    """Every variant against the baseline, then each family against logistic at its window."""

    baseline = variant_name(BASELINE_FAMILY, windows[0])
    variants = [variant_name(family, window) for family in families for window in windows]
    pairs = [(variant, baseline) for variant in variants if variant != baseline]
    pairs.extend(
        (variant_name(family, window), variant_name(BASELINE_FAMILY, window))
        for window in windows[1:]
        for family in families
        if family != BASELINE_FAMILY
    )
    return list(dict.fromkeys(pairs))


def fit_variants(
    args: argparse.Namespace,
    walk_forward: WalkForwardFolds,
    *,
    windows: Sequence[str],
    families: Sequence[str],
    device: torch.device | None,
    alert_policy: AlertPolicy,
    watch_policy: AlertPolicy,
) -> pd.DataFrame:
    """Fit and score every variant on every fold whose training windows hold both classes."""

    assert walk_forward.frame is not None
    columns = walk_forward.feature_columns
    fold_rows: list[dict[str, object]] = []
    for item in walk_forward.folds:
        train_by_window = {
            window: train_rows_for_window(item, window, walk_forward.frame) for window in windows
        }
        if any(train["risk_label"].nunique() < 2 for train in train_by_window.values()):
            continue
        reference_labels = item.train["risk_label"].to_numpy()
        for family in families:
            for window, train in train_by_window.items():
                fit = fit_calibrated_model(
                    build_model(family, device=device, mlp_epochs=args.mlp_epochs),
                    train,
                    item.calibration,
                    item.test,
                    feature_columns=columns,
                    calibration_method=args.calibration_method,
                )
                metrics = score_probabilities(
                    item,
                    fit.calibration_probabilities,
                    fit.test_probabilities,
                    reference_labels=reference_labels,
                    alert_policy=alert_policy,
                    watch_policy=watch_policy,
                )
                fold_rows.append(
                    {
                        "fold_id": item.fold.fold_id,
                        "test_start": str(item.fold.test_dates[0].date()),
                        "variant": variant_name(family, window),
                        "model_family": family,
                        "train_window": window,
                        "train_rows": float(len(train)),
                        "rows": float(len(item.test)),
                        "positives": float(item.test["risk_label"].sum()),
                        **metrics,
                        "raw_auc": classification_metrics(
                            item.test["risk_label"].to_numpy(), fit.raw_test_probabilities
                        )["auc"],
                        "calibration_slope": calibration_slope(fit.calibrator),
                    }
                )
    if not fold_rows:
        raise ValueError("No fold had both classes in every training window")
    return pd.DataFrame(fold_rows)


def run(args: argparse.Namespace) -> dict[str, object]:
    output_dir = resolve_output_dir(args.output_dir, root=args.output_root)
    windows = parse_train_windows(args.train_windows, train_size=args.train_size)
    families = parse_model_families(args.models)
    device = (
        resolve_training_device(args.device, allow_cpu=args.allow_cpu)
        if "mlp" in families
        else None
    )
    alert_policy = parse_alert_policy(args.alert_policy, min_alerts=args.min_alerts)
    watch_policy = parse_alert_policy(args.watch_policy, min_alerts=args.min_alerts)
    walk_forward = load_walk_forward_folds(args)

    if args.reuse_per_fold:
        per_fold = pd.read_csv(
            output_dir / "per_fold.csv",
            dtype={"train_window": str},
            float_precision="round_trip",
        )
    else:
        per_fold = fit_variants(
            args,
            walk_forward,
            windows=windows,
            families=families,
            device=device,
            alert_policy=alert_policy,
            watch_policy=watch_policy,
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    per_fold.to_csv(output_dir / "per_fold.csv", index=False)
    skipped_short_window = len(walk_forward.folds) - int(per_fold["fold_id"].nunique())
    baseline = variant_name(BASELINE_FAMILY, windows[0])
    first_variant = per_fold[per_fold["variant"] == baseline]
    parameters = {family: dict(MODEL_PARAMETERS[family]) for family in families}
    if "mlp" in parameters:
        parameters["mlp"]["epochs"] = args.mlp_epochs
    summary = {
        "input": str(args.input),
        "input_sha256": file_sha256(args.input),
        "protocol": walk_forward_protocol(
            args,
            walk_forward,
            feature_set=args.feature_set,
            train_windows=windows,
            model_families=families,
            model_parameters=parameters,
            mlp_device=None if device is None else device.type,
            brier_skill_reference="event rate of the longest fixed training window",
            alert_policy=alert_policy.label,
            watch_policy=watch_policy.label,
            min_alerts=args.min_alerts,
            skipped_short_window_folds=skipped_short_window,
        ),
        "baseline_variant": baseline,
        "rows": int(first_variant["rows"].sum()),
        "fold_count": int(first_variant["fold_id"].nunique()),
        "event_rate": float(first_variant["positives"].sum() / first_variant["rows"].sum()),
        "variants": {
            name: {
                "train_rows_mean": float(rows["train_rows"].mean()),
                **summarize_set(rows),
                "raw_auc_mean": float(rows["raw_auc"].mean()),
                "inverted_calibration_folds": int((rows["calibration_slope"] < 0).sum()),
            }
            for name, rows in per_fold.groupby("variant", sort=False)
        },
        "paired_comparisons": {
            f"{comparison} vs {reference}": compare_to_baseline(
                per_fold,
                baseline=reference,
                comparison=comparison,
                resamples=args.bootstrap_resamples,
                seed=args.seed,
                group_column="variant",
                metrics=(*PAIRED_METRICS, "raw_auc"),
            )
            for comparison, reference in variant_pairs(families, windows)
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    summary = run(parse_args())
    variants = summary["variants"]
    assert isinstance(variants, dict)
    for name, metrics in variants.items():
        print(
            f"{name:30s} AUC={metrics['auc_mean']:.4f} PR-AUC={metrics['pr_auc_mean']:.4f} "
            f"BSS={metrics['brier_skill_score_mean']:.4f} ECE={metrics['ece_mean']:.4f} "
            f"alert prec={metrics['alert_precision']:.3f} recall={metrics['alert_recall']:.3f} "
            f"watch recall={metrics['watch_recall']:.3f} raw AUC={metrics['raw_auc_mean']:.4f} "
            f"inverted folds={metrics['inverted_calibration_folds']}"
        )


if __name__ == "__main__":
    main()
