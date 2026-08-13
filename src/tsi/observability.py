"""Small structured logging helpers shared by local pipeline services."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any


def log_event(event: str, **fields: Any) -> None:
    """Write one JSON event to stderr without exposing connection strings."""

    safe_fields = {
        key: value
        for key, value in fields.items()
        if not any(secret in key.lower() for secret in ("password", "token", "secret", "credential", "database_url"))
    }
    payload = {
        "schema_version": "tsi_log.v1",
        "event": event,
        "observed_at": datetime.now(UTC).isoformat(),
        **safe_fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True), file=sys.stderr, flush=True)
