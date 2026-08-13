from __future__ import annotations

import json

from tsi.observability import log_event


def test_log_event_emits_schema_first_json_without_database_credentials(capsys) -> None:
    log_event("test_event", service="scheduler", status="success", database_url="must-not-be-forwarded")

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload["schema_version"] == "tsi_log.v1"
    assert payload["event"] == "test_event"
    assert payload["service"] == "scheduler"
    assert "database_url" not in payload
