"""Local recovery must never start native Docker or another database volume."""
import json

import pytest

from scripts import local_services


def test_refuse_native_engine_before_starting_container(monkeypatch):
    monkeypatch.setattr(local_services.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(local_services.subprocess, "check_output", lambda *a, **kw: "Ubuntu")
    with pytest.raises(RuntimeError, match="Docker Desktop"):
        local_services.start_postgres()


def test_refuse_wrong_volume_before_starting_container(monkeypatch):
    monkeypatch.setattr(local_services.shutil, "which", lambda name: "/usr/bin/docker")
    values = iter(["Docker Desktop", json.dumps([{"Mounts": [{
        "Type": "volume", "Name": "unrelated", "Destination": "/var/lib/postgresql/data",
    }]}])])
    monkeypatch.setattr(local_services.subprocess, "check_output", lambda *a, **kw: next(values))
    with pytest.raises(RuntimeError, match="volume identity"):
        local_services.start_postgres()
