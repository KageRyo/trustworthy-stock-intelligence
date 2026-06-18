"""Select warning-policy candidates from a threshold sweep artifact."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


OBJECTIVES = ("recall", "precision", "conservative")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, required=True, help="Threshold sweep CSV input.")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report output.")
    parser.add_argument("--objective", choices=OBJECTIVES, default="recall")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-alert-rate", type=float, default=0.005)
    parser.add_argument("--max-alert-rate", type=float, default=0.25)
    parser.add_argument("--max-false-alarm-rate", type=float, default=0.25)
    parser.add_argument("--max-coverage", type=float, default=0.75)
    return parser.parse_args(argv)


def select_policy_candidates(
    sweep: pd.DataFrame,
    *,
    objective: str,
    limit: int = 10,
    min_alert_rate: float = 0.005,
    max_alert_rate: float = 0.25,
    max_false_alarm_rate: float = 0.25,
    max_coverage: float = 0.75,
) -> pd.DataFrame:
    """Select ranked policy candidates for a chosen warning objective."""

    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {', '.join(OBJECTIVES)}")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    candidates = sweep.copy()
    for column in ("alert_rate", "alert_false_alarm_rate", "coverage"):
        if column not in candidates.columns:
            raise ValueError(f"Missing required column: {column}")
    candidates = candidates[
        candidates["alert_rate"].between(min_alert_rate, max_alert_rate)
        & (candidates["alert_false_alarm_rate"] <= max_false_alarm_rate)
        & (candidates["coverage"] <= max_coverage)
    ]
    if candidates.empty:
        candidates = sweep.copy()

    sort_columns, ascending = _ranking(objective, candidates)
    if not sort_columns:
        return candidates.head(limit).reset_index(drop=True)
    return candidates.sort_values(sort_columns, ascending=ascending).head(limit).reset_index(drop=True)


def render_policy_report(candidates: pd.DataFrame, *, objective: str) -> str:
    columns = [
        "trust_score_method",
        "watch_threshold_ratio",
        "trust_threshold",
        "uncertainty_threshold",
        "uncertainty_penalty",
        "alert_rate",
        "watch_rate",
        "coverage",
        "alert_precision",
        "alert_recall",
        "alert_false_alarm_rate",
        "selective_risk",
    ]
    return (
        f"# {objective.title()}-Oriented Trust Policy Candidates\n\n"
        "These candidates are selected from an existing threshold sweep. They are "
        "policy diagnostics, not new model-training results.\n\n"
        f"{_markdown_table(candidates, columns)}\n\n"
        "## Notes\n\n"
        "- Use recall-oriented policies to study the cost of catching more risk events.\n"
        "- Compare alert recall against false alarm rate before presenting a policy as useful.\n"
        "- Keep the v1 framing conservative: this is risk alerting, not trading advice.\n"
    )


def run_selection(args: argparse.Namespace) -> str:
    sweep = pd.read_csv(args.sweep)
    candidates = select_policy_candidates(
        sweep,
        objective=args.objective,
        limit=args.limit,
        min_alert_rate=args.min_alert_rate,
        max_alert_rate=args.max_alert_rate,
        max_false_alarm_rate=args.max_false_alarm_rate,
        max_coverage=args.max_coverage,
    )
    report = render_policy_report(candidates, objective=args.objective)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return report


def _ranking(objective: str, frame: pd.DataFrame) -> tuple[list[str], list[bool]]:
    if objective == "recall":
        return _available_ranking(
            frame,
            ["alert_recall", "alert_false_alarm_rate", "coverage"],
            [False, True, True],
        )
    if objective == "precision":
        return _available_ranking(
            frame,
            ["alert_precision", "alert_false_alarm_rate", "coverage"],
            [False, True, True],
        )
    return _available_ranking(
        frame,
        ["alert_false_alarm_rate", "selective_risk", "alert_precision"],
        [True, True, False],
    )


def _available_ranking(
    frame: pd.DataFrame,
    columns: Sequence[str],
    ascending: Sequence[bool],
) -> tuple[list[str], list[bool]]:
    available_columns = []
    available_ascending = []
    for column, is_ascending in zip(columns, ascending, strict=True):
        if column in frame.columns:
            available_columns.append(column)
            available_ascending.append(is_ascending)
    return available_columns, available_ascending


def _format_cell(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    available_columns = [column for column in columns if column in frame.columns]
    lines = [
        "| " + " | ".join(available_columns) + " |",
        "| " + " | ".join(["---"] * len(available_columns)) + " |",
    ]
    for _, row in frame.loc[:, available_columns].iterrows():
        lines.append("| " + " | ".join(_format_cell(row[column]) for column in available_columns) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    report = run_selection(args)
    print(report)


if __name__ == "__main__":
    main()
