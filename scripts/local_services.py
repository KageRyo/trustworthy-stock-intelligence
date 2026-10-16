"""Install and run WSL user services; PostgreSQL uses Docker Desktop exclusively."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "trustworthy-stock-intelligence-postgres-1"
VOLUME = "trustworthy-stock-intelligence_postgres-data"


def start_postgres() -> None:
    """Start only the existing project database, after proving Desktop and volume identity."""
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker Desktop WSL integration is required")
    system = subprocess.check_output(
        [docker, "info", "--format", "{{.OperatingSystem}}"], text=True, timeout=30,
    ).strip()
    if "docker desktop" not in system.lower():
        raise RuntimeError("Docker Desktop is required; native Docker Engine is unsupported here")
    info = json.loads(subprocess.check_output(
        [docker, "inspect", CONTAINER], text=True, timeout=30,
    ))[0]
    if not any(m["Type"] == "volume" and m["Name"] == VOLUME
               and m["Destination"] == "/var/lib/postgresql/data" for m in info["Mounts"]):
        raise RuntimeError("Existing PostgreSQL volume identity mismatch; refusing to start")
    if info.get("HostConfig", {}).get("RestartPolicy", {}).get("Name") != "unless-stopped":
        subprocess.run([docker, "update", "--restart", "unless-stopped", CONTAINER],
                       check=True, timeout=30, stdout=subprocess.DEVNULL)
    if info.get("State", {}).get("Running"):
        return
    subprocess.run([docker, "start", CONTAINER], check=True, timeout=90)


def supervise_postgres() -> None:
    """Recover the same Desktop container after engine/container interruptions."""
    while True:
        start_postgres()
        time.sleep(30)


def wait_database() -> None:
    """Fail fast; systemd retries startup without exposing the database DSN."""
    from tsi.data.postgres import connect_database

    with connect_database(os.environ.get("TSI_DATABASE_URL", "")) as conn:
        conn.execute("SELECT 1")


def install() -> None:
    """Render portable unit templates for this checkout and the current toolchain."""
    if not (ROOT / ".env").is_file():
        raise ValueError("Configure .env before installing services")
    # Quoted unit values support spaces. Percent signs must be escaped for systemd specifiers.
    tools = {name: shutil.which(name) for name in ("go", "node")}
    if not all(tools.values()):
        raise ValueError("Go and Node must be installed")
    unit_root = Path.home() / ".config/systemd/user"
    unit_root.mkdir(parents=True, exist_ok=True)
    path = os.pathsep.join([str(Path(p).parent) for p in tools.values()] + [
        str(Path.home() / ".local/bin"), "/usr/local/bin", "/usr/bin", "/bin",
    ])
    replacements = {"@ROOT@": str(ROOT), "@PATH@": path}
    for template in (ROOT / "infra/systemd").glob("tsi-*"):
        text = template.read_text()
        for key, value in replacements.items():
            text = text.replace(key, value.replace("%", "%%").replace('"', '\\"'))
        (unit_root / template.name).write_text(text)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(f"Installed units in {unit_root}; enable with the documented systemctl commands")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "postgres", "supervise-postgres", "check-db"])
    args = parser.parse_args()
    try:
        {"install": install, "postgres": start_postgres,
         "supervise-postgres": supervise_postgres, "check-db": wait_database}[args.action]()
    except Exception as exc:
        print(f"Local service {args.action} failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
