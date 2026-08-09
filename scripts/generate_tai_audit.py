"""Generate a schema-first Trustworthy AI audit artifact for one model run."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from tsi.trust.tai_audit import build_tai_audit, render_tai_audit_markdown


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True, help="Training summary JSON.")
    parser.add_argument("--output", type=Path, required=True, help="TAI audit JSON output.")
    parser.add_argument("--data-manifest", type=Path, help="Optional downloader metadata JSON.")
    parser.add_argument("--warning-eval", type=Path, help="Optional warning-evaluation JSON.")
    parser.add_argument("--markdown-output", type=Path, help="Optional human-readable audit output.")
    parser.add_argument("--run-id", help="Optional stable run identifier.")
    parser.add_argument("--data-as-of", help="Optional provider data timestamp or date.")
    parser.add_argument("--feature-interval", default="1d", help="Feature interval, for example 1d.")
    parser.add_argument(
        "--known-limitation",
        action="append",
        default=[],
        help="Known limitation to preserve in the audit; repeat for multiple values.",
    )
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def run(args: argparse.Namespace) -> dict[str, object]:
    audit = build_tai_audit(
        _read_json(args.summary),
        data_manifest=_read_json(args.data_manifest) if args.data_manifest else None,
        warning_evaluation=_read_json(args.warning_eval) if args.warning_eval else None,
        run_id=args.run_id,
        data_as_of=args.data_as_of,
        feature_interval=args.feature_interval,
        known_limitations=args.known_limitation,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_tai_audit_markdown(audit), encoding="utf-8")
    return audit.model_dump(mode="json")


def main() -> None:
    result = run(parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
