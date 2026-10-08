"""Check that relative links and repository path references in tracked Markdown resolve.

Two kinds of references are checked against the files Git tracks, so a link to a
gitignored local file fails here exactly as it would for a reader of the public
repository:

- Markdown links and images with a relative target, such as ``[Guide](guides/x.md)``.
- Inline code spans that name a repository path, such as ``docs/release.md``. A span
  is treated as a path when it ends with ``/``, has a file extension, or has at least
  three segments, so branch names such as ``docs/new-guide`` are not checked.

Fenced code blocks are skipped because they hold commands and example output.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess

LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
PATH_ROOTS = (
    "docs",
    "experiments",
    "scripts",
    "src",
    "configs",
    "services",
    "frontend",
    "infra",
    "tests",
    "dashboard",
)
CODE_PATH_PATTERN = re.compile(
    r"`((?:" + "|".join(PATH_ROOTS) + r")/[A-Za-z0-9_./-]+)`"
)
FENCE_PATTERN = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


@dataclass(frozen=True)
class BrokenReference:
    source: str
    target: str
    kind: str

    def __str__(self) -> str:
        return f"{self.source}: broken {self.kind} -> {self.target}"


def tracked_files(root: Path) -> list[str]:
    """Return repository-relative POSIX paths tracked by Git."""

    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return [path for path in output.decode("utf-8").split("\0") if path]


def known_paths(files: Iterable[str]) -> set[str]:
    """Tracked files plus every directory that contains one."""

    paths: set[str] = set()
    for file in files:
        path = PurePosixPath(file)
        paths.add(str(path))
        paths.update(str(parent) for parent in path.parents if str(parent) != ".")
    return paths


def _normalize(path: PurePosixPath) -> str | None:
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return "/".join(parts)


def _looks_like_path(target: str) -> bool:
    """Skip names like ``docs/new-guide`` that read as branch names rather than paths."""

    last = target.rstrip("/").rsplit("/", 1)[-1]
    return target.endswith("/") or "." in last or target.count("/") >= 2


def broken_references(source: str, text: str, known: set[str]) -> list[BrokenReference]:
    """Return unresolved references in one Markdown document."""

    body = FENCE_PATTERN.sub("", text)
    base = PurePosixPath(source).parent
    broken: list[BrokenReference] = []
    for target in LINK_PATTERN.findall(body):
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        relative = target.split("#", 1)[0].split("?", 1)[0]
        if not relative:
            continue
        resolved = _normalize(base / relative)
        if resolved is None or resolved.rstrip("/") not in known:
            broken.append(BrokenReference(source, target, "link"))
    for target in CODE_PATH_PATTERN.findall(body):
        if not _looks_like_path(target):
            continue
        path = target.rstrip(".,:;/")
        if path not in known:
            broken.append(BrokenReference(source, target, "path"))
    return broken


def check_repository(root: Path) -> list[BrokenReference]:
    files = tracked_files(root)
    known = known_paths(files)
    broken: list[BrokenReference] = []
    for source in sorted(file for file in files if file.endswith(".md")):
        text = (root / source).read_text(encoding="utf-8")
        broken.extend(broken_references(source, text, known))
    return broken


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    return parser.parse_args(argv)


def main() -> None:
    broken = check_repository(parse_args().root)
    for reference in broken:
        print(reference)
    if broken:
        raise SystemExit(f"{len(broken)} broken Markdown reference(s)")
    print("All Markdown references resolve.")


if __name__ == "__main__":
    main()
