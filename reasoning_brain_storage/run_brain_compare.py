# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Storage-domain brain inspection and comparison entry point.

This entry point is intentionally thin:
- it does not execute benchmarks
- it does not mutate brain state
- it delegates inspection/comparison to reasoning_brain_storage.tools
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))


from reasoning_brain_storage.tools import (  # noqa: E402
    compare_brain_snapshots,
    inspect_brain_snapshot,
)


DEFAULT_COMPARE_REPORTS_ROOT = REPO_ROOT / "reasoning_brain_storage" / "compare_reports"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or compare governed reasoning brain roots."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect one governed reasoning brain root.",
    )
    inspect_parser.add_argument("--brain", required=True, help="Brain root to inspect.")
    inspect_parser.add_argument(
        "--label",
        default="inspect",
        help="Short label used in the report directory name.",
    )
    inspect_parser.add_argument(
        "--output-root",
        default=str(DEFAULT_COMPARE_REPORTS_ROOT),
        help="Root directory for generated compare/inspect reports.",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two governed reasoning brain roots.",
    )
    compare_parser.add_argument("--brain-a", required=True, help="First brain root.")
    compare_parser.add_argument("--brain-b", required=True, help="Second brain root.")
    compare_parser.add_argument(
        "--label",
        default="brain_compare",
        help="Short label used in the report directory name.",
    )
    compare_parser.add_argument(
        "--output-root",
        default=str(DEFAULT_COMPARE_REPORTS_ROOT),
        help="Root directory for generated compare/inspect reports.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.command == "inspect":
        report_root = _create_report_root(output_root=output_root, label=args.label)
        inspection = inspect_brain_snapshot(root=Path(args.brain))
        inspection_payload = _build_inspection_payload(inspection)
        _write_json(report_root / "inspection_summary.json", inspection_payload)
        (report_root / "inspection.md").write_text(
            _build_inspection_markdown(inspection_payload),
            encoding="utf-8",
        )
        print(f"saved brain inspection summary: {report_root / 'inspection_summary.json'}")
        print(f"saved brain inspection markdown: {report_root / 'inspection.md'}")
        return

    if args.command == "compare":
        report_root = _create_report_root(output_root=output_root, label=args.label)
        comparison = compare_brain_snapshots(
            snapshot_a_root=Path(args.brain_a),
            snapshot_b_root=Path(args.brain_b),
        )
        summary_payload = _build_comparison_summary_payload(
            comparison=comparison,
            report_root=report_root,
            label=args.label,
        )
        diff_payload = _build_diff_payload(comparison)
        intersect_payload = _build_intersect_payload(comparison)

        _write_json(report_root / "comparison_summary.json", summary_payload)
        _write_json(report_root / "diff.json", diff_payload)
        _write_json(report_root / "intersect.json", intersect_payload)
        (report_root / "diff.md").write_text(
            _build_diff_markdown(diff_payload, summary_payload),
            encoding="utf-8",
        )
        (report_root / "intersect.md").write_text(
            _build_intersect_markdown(intersect_payload, summary_payload),
            encoding="utf-8",
        )
        print(f"saved brain comparison summary: {report_root / 'comparison_summary.json'}")
        print(f"saved brain diff report: {report_root / 'diff.md'}")
        print(f"saved brain intersection report: {report_root / 'intersect.md'}")
        return

    raise ValueError(f"unsupported command: {args.command}")


def _create_report_root(*, output_root: Path, label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_root = output_root / f"{timestamp}_{_sanitize_label(label)}"
    if report_root.exists():
        raise FileExistsError(f"compare report root already exists: {report_root}")
    report_root.mkdir(parents=True, exist_ok=False)
    return report_root


def _build_inspection_payload(inspection: Any) -> dict[str, Any]:
    return {
        "brain_root": str(inspection.brain_root),
        "working_context": _serialize(inspection.working_context),
        "artifact_count_total": inspection.artifact_count_total,
        "artifact_count_by_type": _serialize(inspection.artifact_count_by_type),
        "artifact_ids_by_type": _serialize(inspection.artifact_ids_by_type),
    }


def _build_comparison_summary_payload(
    *,
    comparison: Any,
    report_root: Path,
    label: str,
) -> dict[str, Any]:
    return {
        "report_root": str(report_root),
        "brain_a_root": str(comparison.snapshot_a_root),
        "brain_b_root": str(comparison.snapshot_b_root),
        "label": label,
        "artifact_count_total": {
            "a": comparison.artifact_count_total.a,
            "b": comparison.artifact_count_total.b,
            "shared": len(comparison.artifact_ids["shared"]),
            "added": len(comparison.artifact_ids["added"]),
            "removed": len(comparison.artifact_ids["removed"]),
            "mismatched": len(comparison.artifact_ids["mismatched"]),
        },
        "artifact_count_by_type": {
            artifact_type: {
                "a": counts.a,
                "b": counts.b,
                "shared": len(comparison.artifact_ids_by_type[artifact_type]["shared"]),
                "added": len(comparison.artifact_ids_by_type[artifact_type]["added"]),
                "removed": len(comparison.artifact_ids_by_type[artifact_type]["removed"]),
                "mismatched": len(comparison.artifact_ids_by_type[artifact_type]["mismatched"]),
            }
            for artifact_type, counts in comparison.artifact_count_by_type.items()
        },
        "working_context_diff": _serialize(comparison.working_context_diff),
        "brain_diff_summary": _serialize(comparison.brain_diff_summary),
        "notes": [
            "duplicate_candidates_count and contradiction_candidates_count are v1 structural placeholders.",
            "intersect is shared persisted core under conservative identity rules, not truth.",
            "mismatch is structural payload mismatch for the same id, not semantic contradiction.",
        ],
    }


def _build_diff_payload(comparison: Any) -> dict[str, Any]:
    return {
        "brain_a_root": str(comparison.snapshot_a_root),
        "brain_b_root": str(comparison.snapshot_b_root),
        "artifact_ids": {
            "added": list(comparison.artifact_ids["added"]),
            "removed": list(comparison.artifact_ids["removed"]),
            "mismatched": list(comparison.artifact_ids["mismatched"]),
        },
        "artifacts_by_type": {
            artifact_type: {
                "added": list(values["added"]),
                "removed": list(values["removed"]),
                "mismatched": list(values["mismatched"]),
            }
            for artifact_type, values in comparison.artifact_ids_by_type.items()
        },
        "working_context_diff": _serialize(comparison.working_context_diff),
    }


def _build_intersect_payload(comparison: Any) -> dict[str, Any]:
    return {
        "brain_a_root": str(comparison.snapshot_a_root),
        "brain_b_root": str(comparison.snapshot_b_root),
        "artifact_ids": {
            "shared": list(comparison.artifact_ids["shared"]),
        },
        "artifacts_by_type": {
            artifact_type: {
                "shared": list(values["shared"]),
            }
            for artifact_type, values in comparison.artifact_ids_by_type.items()
        },
        "working_context_intersection": _serialize(
            comparison.working_context_intersection
        ),
    }


def _build_inspection_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Brain Inspection",
        "",
        f"- brain_root: {payload['brain_root']}",
        f"- artifact_count_total: {payload['artifact_count_total']}",
        "",
        "## Working Context",
        "",
        f"- active_task: {payload['working_context']['active_task']}",
        f"- constraints: {payload['working_context']['constraints']}",
        f"- decisions: {payload['working_context']['decisions']}",
        f"- open_issues: {payload['working_context']['open_issues']}",
        "",
        "## Artifact Counts By Type",
        "",
    ]
    for artifact_type, count in payload["artifact_count_by_type"].items():
        lines.append(f"- {artifact_type}: {count}")
    return "\n".join(lines) + "\n"


def _build_diff_markdown(
    diff_payload: dict[str, Any],
    summary_payload: dict[str, Any],
) -> str:
    lines = [
        "# Brain Diff",
        "",
        f"- brain_a_root: {diff_payload['brain_a_root']}",
        f"- brain_b_root: {diff_payload['brain_b_root']}",
        "",
        "## Totals",
        "",
        f"- added: {summary_payload['artifact_count_total']['added']}",
        f"- removed: {summary_payload['artifact_count_total']['removed']}",
        f"- mismatched: {summary_payload['artifact_count_total']['mismatched']}",
        "",
        "## Artifact Ids",
        "",
        f"- added: {diff_payload['artifact_ids']['added']}",
        f"- removed: {diff_payload['artifact_ids']['removed']}",
        f"- mismatched: {diff_payload['artifact_ids']['mismatched']}",
        "",
        "## Working Context Diff",
        "",
    ]
    for key, value in diff_payload["working_context_diff"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- mismatch is structural same-id payload mismatch in v1",
            "- duplicate/contradiction counts remain structural placeholders in v1",
            "",
        ]
    )
    return "\n".join(lines)


def _build_intersect_markdown(
    intersect_payload: dict[str, Any],
    summary_payload: dict[str, Any],
) -> str:
    lines = [
        "# Brain Intersection",
        "",
        f"- brain_a_root: {intersect_payload['brain_a_root']}",
        f"- brain_b_root: {intersect_payload['brain_b_root']}",
        "",
        "## Shared Artifact Totals",
        "",
        f"- shared: {summary_payload['artifact_count_total']['shared']}",
        "",
        "## Shared Artifact Ids",
        "",
        f"- shared: {intersect_payload['artifact_ids']['shared']}",
        "",
        "## Working Context Intersection",
        "",
    ]
    for key, value in intersect_payload["working_context_intersection"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- intersect is shared persisted core under conservative identity rules",
            "- intersect is not truth and does not imply union semantics",
            "",
        ]
    )
    return "\n".join(lines)


def _sanitize_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", label.strip())
    return cleaned or "brain_compare"


def _serialize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _serialize(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
