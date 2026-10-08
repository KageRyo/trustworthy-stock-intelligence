"""Tests for the Markdown link and path reference checker."""

from __future__ import annotations

from pathlib import Path

from scripts.check_markdown_links import broken_references, check_repository, known_paths

KNOWN = known_paths(
    ["README.md", "docs/README.md", "docs/guides/user_guide.md", "scripts/train.py"]
)


def _targets(source: str, text: str) -> list[str]:
    return [reference.target for reference in broken_references(source, text, KNOWN)]


def test_relative_links_resolve_from_the_source_directory() -> None:
    text = "[Guide](guides/user_guide.md#start) [Home](../README.md) [Dir](guides/)"

    assert _targets("docs/README.md", text) == []
    assert _targets("docs/README.md", "[Old](user_guide.md)") == ["user_guide.md"]


def test_links_escaping_the_repository_are_broken() -> None:
    assert _targets("README.md", "[Up](../outside.md)") == ["../outside.md"]


def test_external_links_anchors_and_fenced_blocks_are_ignored() -> None:
    text = (
        "[Site](https://example.com) [Mail](mailto:a@b.c) [Top](#intro)\n"
        "```bash\ncat [x](missing.md) `docs/missing.md`\n```\n"
    )

    assert _targets("README.md", text) == []


def test_inline_repository_paths_must_be_tracked() -> None:
    text = "Run `scripts/train.py`, see `docs/guides/`, not `docs/old_guide.md`."

    assert _targets("README.md", text) == ["docs/old_guide.md"]


def test_branch_like_names_are_not_treated_as_paths() -> None:
    assert _targets("CONTRIBUTING.md", "Use `docs/development-environment` as a branch.") == []


def test_repository_markdown_references_resolve() -> None:
    root = Path(__file__).resolve().parents[1]

    assert [str(reference) for reference in check_repository(root)] == []
