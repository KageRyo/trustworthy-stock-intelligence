"""Public Python API for trustworthy stock drawdown-risk analysis.

The package contains reusable research and serving primitives.  The Go API,
dashboard, PostgreSQL schema, and operational workers remain separate parts of
the repository and are not hidden behind this import surface.
"""

from tsi.data.csv import file_sha256, read_ohlcv_csv
from tsi.evaluation.metrics import classification_metrics, expected_calibration_error
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.labeling.drawdown import add_future_drawdown_label
from tsi.labeling.warning_level import assign_warning_levels, select_alert_threshold
from tsi.models import LogisticRiskModel, TreeRiskModel
from tsi.serving.schema import PredictionBatch, PredictionRecord, build_prediction_batch
from tsi.trust.trust_score import compute_trust_score
from tsi.trust.uncertainty import binary_entropy_uncertainty, margin_uncertainty

__version__ = "0.4.1"

__all__ = [
    "DEFAULT_FEATURE_COLUMNS",
    "LogisticRiskModel",
    "PredictionBatch",
    "PredictionRecord",
    "TreeRiskModel",
    "__version__",
    "add_future_drawdown_label",
    "assign_warning_levels",
    "binary_entropy_uncertainty",
    "build_prediction_batch",
    "build_technical_features",
    "classification_metrics",
    "compute_trust_score",
    "expected_calibration_error",
    "file_sha256",
    "margin_uncertainty",
    "read_ohlcv_csv",
    "select_alert_threshold",
]
