"""Named feature sets and one builder that computes only the columns they need."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from tsi.data.market_reference import MarketReference
from tsi.data.twse_chips import ChipTables
from tsi.features.chips import (
    CHIP_FEATURE_COLUMNS,
    FLOW_FEATURE_COLUMNS,
    MARGIN_FEATURE_COLUMNS,
    build_chip_features,
)
from tsi.features.market import (
    MARKET_FEATURE_COLUMNS,
    REGIME_FEATURE_COLUMNS,
    RELATIVE_FEATURE_COLUMNS,
    build_market_features,
)
from tsi.features.technical import DEFAULT_FEATURE_COLUMNS, build_technical_features
from tsi.features.volatility import RANGE_FEATURE_COLUMNS, build_range_features

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "technical": tuple(DEFAULT_FEATURE_COLUMNS),
    "technical_range": (*DEFAULT_FEATURE_COLUMNS, *RANGE_FEATURE_COLUMNS),
    "technical_market": (*DEFAULT_FEATURE_COLUMNS, *MARKET_FEATURE_COLUMNS),
    "technical_range_market": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *MARKET_FEATURE_COLUMNS,
    ),
    "technical_range_beta": (*DEFAULT_FEATURE_COLUMNS, *RANGE_FEATURE_COLUMNS, "beta_60d"),
    "technical_range_relative": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *RELATIVE_FEATURE_COLUMNS,
    ),
    "technical_range_regime": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *REGIME_FEATURE_COLUMNS,
    ),
    "technical_range_chips": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *CHIP_FEATURE_COLUMNS,
    ),
    "technical_range_flows": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *FLOW_FEATURE_COLUMNS,
    ),
    "technical_range_margin": (
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *MARGIN_FEATURE_COLUMNS,
    ),
}
DEFAULT_FEATURE_SET = "technical"


def resolve_feature_set(name: str) -> list[str]:
    """Return the ordered feature columns for a named feature set."""

    if name not in FEATURE_SETS:
        raise ValueError(f"Unknown feature set {name!r}; choose one of {', '.join(FEATURE_SETS)}")
    return list(FEATURE_SETS[name])


def feature_set_requires_market_reference(columns: Sequence[str]) -> bool:
    """Return whether any column needs reference index or sector series."""

    return any(column in MARKET_FEATURE_COLUMNS for column in columns)


def feature_set_requires_chips(columns: Sequence[str]) -> bool:
    """Return whether any column needs TWSE institutional-flow or margin data."""

    return any(column in CHIP_FEATURE_COLUMNS for column in columns)


def build_feature_frame(
    ohlcv: pd.DataFrame,
    columns: Sequence[str],
    *,
    market_reference: MarketReference | None = None,
    same_session_reference: bool = True,
    chip_tables: ChipTables | None = None,
    chip_publication_lag: int = 1,
) -> pd.DataFrame:
    """Build technical features plus any range, market, or chip columns in ``columns``.

    Rows are sorted by ticker and date, as with :func:`build_technical_features`.
    """

    known = {
        *DEFAULT_FEATURE_COLUMNS,
        *RANGE_FEATURE_COLUMNS,
        *MARKET_FEATURE_COLUMNS,
        *CHIP_FEATURE_COLUMNS,
    }
    unknown = [column for column in columns if column not in known]
    if unknown:
        raise ValueError(f"Unknown feature columns: {', '.join(unknown)}")

    frame = build_technical_features(ohlcv)
    if any(column in RANGE_FEATURE_COLUMNS for column in columns):
        frame = build_range_features(frame)
    if feature_set_requires_market_reference(columns):
        if market_reference is None:
            raise ValueError("Market-relative features require a market reference dataset")
        frame = build_market_features(
            frame,
            market_reference.ohlcv,
            market_symbol=market_reference.market_symbol,
            volatility_symbol=market_reference.volatility_symbol,
            sector_etf_by_ticker=market_reference.sector_etf_by_ticker,
            same_session_reference=same_session_reference,
        )
    if feature_set_requires_chips(columns):
        if chip_tables is None:
            raise ValueError("Chip features require TWSE institutional and margin tables")
        frame = build_chip_features(frame, chip_tables, publication_lag=chip_publication_lag)
    return frame
