"""CSV loading helpers for market data artifacts."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd


def read_ohlcv_csv(path: Path | str) -> pd.DataFrame:
    """Read OHLCV CSV while preserving ticker symbols exactly as strings."""

    frame = pd.read_csv(path, dtype={"ticker": "string"})
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper()
    return frame


def file_sha256(path: Path | str) -> str:
    """Return a stable SHA-256 fingerprint for a local research artifact."""

    digest = sha256()
    with Path(path).open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path_label(path: Path | str) -> str:
    """Name an input in published provenance without exposing host directories.

    Relative paths are kept. An absolute path becomes relative to the working directory when it
    is inside it; otherwise only the file name is kept.
    """

    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    if candidate.is_relative_to(Path.cwd()):
        return candidate.relative_to(Path.cwd()).as_posix()
    return candidate.name
