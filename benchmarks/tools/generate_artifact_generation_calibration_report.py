# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Generate artifact generation calibration reports from benchmark event logs.

This tool reads existing *.events.jsonl files and summarizes artifact parser,
shadow generation, and filter telemetry. It is reporting-only: it does not
execute benchmarks, derive scores, mutate storage, or alter result schemas.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.event_log_utils import read_events  # noqa: E402
from benchmark_adapters.common.result_utils import ensure_output_path_writable  # noqa: E402


PARSER_OUTCOMES = ("valid", "none", "missing", "malformed")
FILTER_VERDICT_ACCEPTED = "accepted"
FILTER_VERDICT_REJECTED = "rejected"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate artifact generation calibration markdown report."
    )
    parser.add_argument(
        "--events",
        nargs="+",
        required=True,
        help="One or more benchmark *.events.jsonl files to aggregate.",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "benchmarks" / "reports" / "artifact_generation_calibration.md"),
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing report.",
    )
    return parser.parse_args()


def load_events_from_paths(event_paths: Sequence[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in event_paths:
        events.extend(read_events(path))
    return events


def build_artifact_generation_calibration(
    events: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    summary = _new_summary()

    for event in events:
        if event.get("event_type") not in {"task_completed", "task_failed"}:
            continue

        summary["total_tasks"] += 1
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            summary["missing_telemetry_count"] += 1
            continue

        _accumulate_generation(summary, payload.get("artifact_generation"))
        _accumulate_shadow_generation(summary, payload.get("artifact_generation_shadow"))
        _accumulate_filter(summary, payload.get("artifact_filter"))
        _accumulate_filter(summary, payload.get("artifact_filter_shadow"))
        _accumulate_mode_breakdown(summary, event, payload)

    _finalize_summary(summary)
    return summary


def render_artifact_generation_calibration_report(
    calibration: Mapping[str, object],
) -> str:
    generation = _require_mapping(calibration, "artifact_generation")
    filter_alignment = _require_mapping(calibration, "filter_alignment")
    shadow = _require_mapping(calibration, "shadow_generation")
    rejection_reasons = _require_mapping(filter_alignment, "rejection_reason_distribution")

    lines = [
        "# Artifact Generation Calibration Report",
        "",
        "## Summary",
        "",
        f"- total_tasks: {calibration['total_tasks']}",
        f"- valid_artifact_count: {generation['valid_artifact_count']}",
        f"- artifact_rate: {_format_rate(generation['artifact_rate'])}",
        f"- filter_acceptance_rate: {_format_rate(filter_alignment['filter_acceptance_rate'])}",
        f"- generator_precision: {_format_rate(filter_alignment['generator_precision'])}",
        "",
        "## Artifact Generation Outcomes",
        "",
        f"- valid_artifact_count: {generation['valid_artifact_count']}",
        f"- none_count: {generation['none_count']}",
        f"- missing_count: {generation['missing_count']}",
        f"- malformed_count: {generation['malformed_count']}",
        f"- missing_telemetry_count: {calibration['missing_telemetry_count']}",
        f"- artifact_rate: {_format_rate(generation['artifact_rate'])}",
        f"- none_rate: {_format_rate(generation['none_rate'])}",
        f"- malformed_rate: {_format_rate(generation['malformed_rate'])}",
        "",
        "## Filter Alignment",
        "",
        f"- evaluated_count: {filter_alignment['evaluated_count']}",
        f"- accepted_count: {filter_alignment['accepted_count']}",
        f"- rejected_count: {filter_alignment['rejected_count']}",
        f"- skipped_count: {filter_alignment['skipped_count']}",
        f"- filter_acceptance_rate: {_format_rate(filter_alignment['filter_acceptance_rate'])}",
        f"- generator_precision: {_format_rate(filter_alignment['generator_precision'])}",
        "",
        "## Shadow Generation",
        "",
        f"- shadow_total_count: {shadow['shadow_total_count']}",
        f"- shadow_valid_count: {shadow['shadow_valid_count']}",
        f"- shadow_none_count: {shadow['shadow_none_count']}",
        f"- shadow_malformed_count: {shadow['shadow_malformed_count']}",
        f"- shadow_missing_count: {shadow['shadow_missing_count']}",
        f"- shadow_artifact_rate: {_format_rate(shadow['shadow_artifact_rate'])}",
        f"- shadow_none_rate: {_format_rate(shadow['shadow_none_rate'])}",
        "",
        "## Rejection Reasons",
        "",
    ]

    if rejection_reasons:
        for reason, count in sorted(rejection_reasons.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Mode Breakdown",
            "",
        ]
    )
    lines.extend(_render_mode_breakdown(calibration))
    lines.extend(
        [
            "",
            "## Calibration Notes",
            "",
            "- This report is generated only from benchmark event telemetry.",
            "- It does not alter benchmark execution, scoring, persistence, or result artifacts.",
            "- Filter verdicts are observational unless a separate future hard-gate is explicitly implemented.",
            "",
            "## Hard-Gate Readiness",
            "",
        ]
    )
    lines.extend(_render_hard_gate_readiness(calibration))
    lines.append("")
    return "\n".join(lines)


def write_artifact_generation_calibration_report(
    event_paths: Sequence[Path],
    *,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    events = load_events_from_paths(event_paths)
    calibration = build_artifact_generation_calibration(events)
    report = render_artifact_generation_calibration_report(calibration)
    ensure_output_path_writable(
        output_path,
        overwrite=overwrite,
        artifact_label="artifact generation calibration report",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return output_path


def _new_summary() -> dict[str, Any]:
    return {
        "total_tasks": 0,
        "missing_telemetry_count": 0,
        "artifact_generation": {
            "valid_artifact_count": 0,
            "none_count": 0,
            "missing_count": 0,
            "malformed_count": 0,
        },
        "filter_alignment": {
            "evaluated_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "skipped_count": 0,
            "rejection_reason_distribution": Counter(),
        },
        "shadow_generation": {
            "shadow_total_count": 0,
            "shadow_valid_count": 0,
            "shadow_none_count": 0,
            "shadow_missing_count": 0,
            "shadow_malformed_count": 0,
        },
        "mode_breakdown": defaultdict(_new_mode_entry),
    }


def _new_mode_entry() -> dict[str, Any]:
    return {
        "total_tasks": 0,
        "valid_artifact_count": 0,
        "none_count": 0,
        "missing_count": 0,
        "malformed_count": 0,
        "filter_evaluated_count": 0,
        "filter_accepted_count": 0,
        "filter_rejected_count": 0,
    }


def _accumulate_generation(summary: dict[str, Any], telemetry: object) -> None:
    if not isinstance(telemetry, Mapping):
        return

    outcome = telemetry.get("parser_outcome")
    generation = summary["artifact_generation"]
    if outcome == "valid":
        generation["valid_artifact_count"] += 1
    elif outcome == "none":
        generation["none_count"] += 1
    elif outcome == "missing":
        generation["missing_count"] += 1
    elif outcome == "malformed":
        generation["malformed_count"] += 1


def _accumulate_shadow_generation(summary: dict[str, Any], telemetry: object) -> None:
    if not isinstance(telemetry, Mapping):
        return

    outcome = telemetry.get("parser_outcome")
    shadow = summary["shadow_generation"]
    shadow["shadow_total_count"] += 1
    if outcome == "valid":
        shadow["shadow_valid_count"] += 1
    elif outcome == "none":
        shadow["shadow_none_count"] += 1
    elif outcome == "missing":
        shadow["shadow_missing_count"] += 1
    elif outcome == "malformed":
        shadow["shadow_malformed_count"] += 1


def _accumulate_filter(summary: dict[str, Any], telemetry: object) -> None:
    if not isinstance(telemetry, Mapping):
        return

    status = telemetry.get("status")
    filter_alignment = summary["filter_alignment"]
    if status == "skipped":
        filter_alignment["skipped_count"] += 1
        return
    if status != "evaluated":
        return

    filter_alignment["evaluated_count"] += 1
    verdict = telemetry.get("verdict")
    if verdict == FILTER_VERDICT_ACCEPTED:
        filter_alignment["accepted_count"] += 1
    elif verdict == FILTER_VERDICT_REJECTED:
        filter_alignment["rejected_count"] += 1
        for reason in _normalize_reasons(telemetry.get("reasons")):
            filter_alignment["rejection_reason_distribution"][reason] += 1


def _accumulate_mode_breakdown(
    summary: dict[str, Any],
    event: Mapping[str, object],
    payload: Mapping[str, object],
) -> None:
    mode = str(event.get("mode", "unknown"))
    execution_source = str(payload.get("execution_source", "unknown"))
    generation_mode = _telemetry_mode(payload.get("artifact_generation"), default="unknown")
    filter_mode = _telemetry_mode(payload.get("artifact_filter"), default=None)
    if filter_mode is None:
        filter_mode = _telemetry_mode(payload.get("artifact_filter_shadow"), default="off")
    key = f"mode={mode}; provider={execution_source}; artifact_generator_mode={generation_mode}; artifact_filter_mode={filter_mode}"
    entry = summary["mode_breakdown"][key]
    entry["total_tasks"] += 1

    generation = payload.get("artifact_generation")
    if isinstance(generation, Mapping):
        outcome = generation.get("parser_outcome")
        if outcome == "valid":
            entry["valid_artifact_count"] += 1
        elif outcome == "none":
            entry["none_count"] += 1
        elif outcome == "missing":
            entry["missing_count"] += 1
        elif outcome == "malformed":
            entry["malformed_count"] += 1

    for filter_key in ("artifact_filter", "artifact_filter_shadow"):
        filter_telemetry = payload.get(filter_key)
        if not isinstance(filter_telemetry, Mapping):
            continue
        if filter_telemetry.get("status") != "evaluated":
            continue
        entry["filter_evaluated_count"] += 1
        if filter_telemetry.get("verdict") == FILTER_VERDICT_ACCEPTED:
            entry["filter_accepted_count"] += 1
        elif filter_telemetry.get("verdict") == FILTER_VERDICT_REJECTED:
            entry["filter_rejected_count"] += 1


def _finalize_summary(summary: dict[str, Any]) -> None:
    total_tasks = summary["total_tasks"]
    generation = summary["artifact_generation"]
    generation["artifact_rate"] = _safe_rate(generation["valid_artifact_count"], total_tasks)
    generation["none_rate"] = _safe_rate(generation["none_count"], total_tasks)
    generation["malformed_rate"] = _safe_rate(generation["malformed_count"], total_tasks)

    filter_alignment = summary["filter_alignment"]
    filter_alignment["filter_acceptance_rate"] = _safe_rate(
        filter_alignment["accepted_count"],
        filter_alignment["evaluated_count"],
    )
    filter_alignment["generator_precision"] = _safe_rate(
        filter_alignment["accepted_count"],
        generation["valid_artifact_count"],
    )
    filter_alignment["rejection_reason_distribution"] = dict(
        filter_alignment["rejection_reason_distribution"]
    )

    shadow = summary["shadow_generation"]
    shadow_total = shadow["shadow_total_count"]
    shadow["shadow_artifact_rate"] = _safe_rate(shadow["shadow_valid_count"], shadow_total)
    shadow["shadow_none_rate"] = _safe_rate(shadow["shadow_none_count"], shadow_total)

    summary["mode_breakdown"] = dict(summary["mode_breakdown"])


def _render_mode_breakdown(calibration: Mapping[str, object]) -> list[str]:
    mode_breakdown = _require_mapping(calibration, "mode_breakdown")
    if not mode_breakdown:
        return ["- none observed"]

    lines = [
        "| Dimension | Total | Valid | NONE | Missing | Malformed | Filter Evaluated | Filter Accepted | Filter Rejected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, raw_entry in sorted(mode_breakdown.items()):
        entry = _require_mapping_value(raw_entry, f"mode_breakdown[{key}]")
        lines.append(
            "| "
            + " | ".join(
                (
                    str(key),
                    str(entry["total_tasks"]),
                    str(entry["valid_artifact_count"]),
                    str(entry["none_count"]),
                    str(entry["missing_count"]),
                    str(entry["malformed_count"]),
                    str(entry["filter_evaluated_count"]),
                    str(entry["filter_accepted_count"]),
                    str(entry["filter_rejected_count"]),
                )
            )
            + " |"
        )
    return lines


def _render_hard_gate_readiness(calibration: Mapping[str, object]) -> list[str]:
    generation = _require_mapping(calibration, "artifact_generation")
    filter_alignment = _require_mapping(calibration, "filter_alignment")
    rejection_reasons = _require_mapping(filter_alignment, "rejection_reason_distribution")

    malformed_rate = _require_number(generation, "malformed_rate")
    none_rate = _require_number(generation, "none_rate")
    filter_acceptance_rate = _require_number(filter_alignment, "filter_acceptance_rate")
    evaluated_count = _require_int(filter_alignment, "evaluated_count")

    return [
        f"- malformed_rate is low: {_readiness_status(malformed_rate <= 0.05)} ({_format_rate(malformed_rate)})",
        f"- filter_acceptance_rate is stable: {_readiness_status(evaluated_count > 0)} ({_format_rate(filter_acceptance_rate)})",
        f"- rejection reasons are understood: {_readiness_status(not rejection_reasons)}",
        f"- none_rate is not extreme: {_readiness_status(none_rate < 0.95)} ({_format_rate(none_rate)})",
        "- no evidence that rejected artifacts are required for persistence behavior: diagnostic review required",
        "- hard-gate readiness is diagnostic only; this report does not enable enforcement.",
    ]


def _telemetry_mode(telemetry: object, *, default: str | None) -> str | None:
    if isinstance(telemetry, Mapping) and isinstance(telemetry.get("mode"), str):
        return str(telemetry["mode"])
    return default


def _normalize_reasons(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _format_rate(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "0.0000"
    return f"{float(value):.4f}"


def _readiness_status(condition: bool) -> str:
    return "observed" if condition else "needs review"


def _require_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    nested = value.get(key)
    return _require_mapping_value(nested, key)


def _require_mapping_value(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _require_number(value: Mapping[str, object], key: str) -> float:
    raw = value.get(key)
    if not isinstance(raw, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(raw)


def _require_int(value: Mapping[str, object], key: str) -> int:
    raw = value.get(key)
    if not isinstance(raw, int):
        raise ValueError(f"{key} must be an integer")
    return raw


def main() -> None:
    args = parse_args()
    event_paths = [Path(path) for path in args.events]
    output_path = Path(args.output)
    written = write_artifact_generation_calibration_report(
        event_paths,
        output_path=output_path,
        overwrite=args.overwrite,
    )
    print(f"artifact generation calibration report written: {written}")


if __name__ == "__main__":
    main()


__all__ = [
    "build_artifact_generation_calibration",
    "load_events_from_paths",
    "render_artifact_generation_calibration_report",
    "write_artifact_generation_calibration_report",
]
