# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Review and selectively seed runtime benchmark artifacts into the seeded benchmark brain.

This tool is a controlled manual preparation utility.

It may:
- inspect runtime benchmark artifact cards
- validate artifact schema before promotion
- copy selected artifact files from the runtime benchmark brain into the seeded benchmark brain

It does not:
- run benchmark scenarios
- mutate canonical project reasoning state outside benchmark brain roots
- overwrite existing seeded artifacts silently
- perform automatic seeding as part of normal benchmark execution

Usage patterns:
- review only:
    python benchmarks/tools/review_and_seed_runtime_artifacts.py --list
    python benchmarks/tools/review_and_seed_runtime_artifacts.py --artifact-id decision_example

- apply selected seeding:
    python benchmarks/tools/review_and_seed_runtime_artifacts.py --artifact-id decision_example --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Temporary PoC import bootstrap.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.benchmark_paths import (  # noqa: E402
    BenchmarkPaths,
    get_benchmark_paths,
    validate_required_benchmark_roots,
)
from core.validation import validate_artifact_schema  # noqa: E402


ARTIFACT_DIR_NAMES = (
    "tasks",
    "decisions",
    "constraints",
    "procedures",
    "issues",
)


@dataclass(frozen=True)
class RuntimeArtifactRecord:
    artifact_id: str
    artifact_type: str
    category: str
    source_path: Path
    target_path: Path


@dataclass(frozen=True)
class ReviewResult:
    artifact_id: str
    artifact_type: str | None
    source_path: Path | None
    target_path: Path | None
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review and selectively seed runtime benchmark artifacts."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all validated runtime benchmark artifacts and exit.",
    )
    parser.add_argument(
        "--artifact-id",
        action="append",
        default=[],
        help="Artifact id to review or seed. May be provided multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Select all validated runtime artifacts for review or seeding.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy selected runtime artifacts into the seeded benchmark brain.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Optional repository root override.",
    )
    return parser.parse_args()


def validate_cli_args(args: argparse.Namespace) -> None:
    if args.list and args.apply:
        raise ValueError("--list must not be combined with --apply")
    if args.list and args.all:
        raise ValueError("--list must not be combined with --all")
    if args.list and args.artifact_id:
        raise ValueError("--list must not be combined with --artifact-id")


def discover_runtime_artifacts(paths: BenchmarkPaths) -> list[RuntimeArtifactRecord]:
    runtime_brain = paths.runtime_brain_root / "brain"
    seeded_brain = paths.seeded_brain_root / "brain"

    discovered: list[RuntimeArtifactRecord] = []
    seen_ids: set[str] = set()

    for category in ARTIFACT_DIR_NAMES:
        category_dir = runtime_brain / category
        if not category_dir.exists():
            continue
        if not category_dir.is_dir():
            raise ValueError(f"runtime artifact category path is not a directory: {category_dir}")

        for source_path in sorted(category_dir.glob("*.json")):
            _ensure_path_within_root(source_path, runtime_brain, "runtime artifact source path")

            artifact = load_artifact_json(source_path)
            validate_artifact_schema(artifact)

            artifact_id = _require_string_field(artifact, "id", str(source_path))
            artifact_type = _require_string_field(artifact, "type", str(source_path))

            if artifact_id in seen_ids:
                raise ValueError(f"duplicate runtime artifact id detected: {artifact_id}")
            seen_ids.add(artifact_id)

            target_path = seeded_brain / category / source_path.name
            _ensure_path_within_root(target_path, seeded_brain, "seeded artifact target path")

            discovered.append(
                RuntimeArtifactRecord(
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    category=category,
                    source_path=source_path,
                    target_path=target_path,
                )
            )

    return discovered


def load_artifact_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact file not found: {path}")
    if not path.is_file():
        raise ValueError(f"artifact path is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"artifact json must contain an object: {path}")

    return data


def build_runtime_artifact_index(
    records: list[RuntimeArtifactRecord],
) -> dict[str, RuntimeArtifactRecord]:
    index: dict[str, RuntimeArtifactRecord] = {}

    for record in records:
        if record.artifact_id in index:
            raise ValueError(f"duplicate artifact id in runtime index: {record.artifact_id}")
        index[record.artifact_id] = record

    return index


def review_selected_artifacts(
    records: list[RuntimeArtifactRecord],
    *,
    selected_ids: list[str],
) -> list[ReviewResult]:
    index = build_runtime_artifact_index(records)

    review_results: list[ReviewResult] = []
    seen_selected: set[str] = set()

    for artifact_id in selected_ids:
        cleaned_id = _normalize_required_text(artifact_id, "artifact_id")
        if cleaned_id in seen_selected:
            raise ValueError(f"duplicate selected artifact_id: {cleaned_id}")
        seen_selected.add(cleaned_id)

        record = index.get(cleaned_id)
        if record is None:
            review_results.append(
                ReviewResult(
                    artifact_id=cleaned_id,
                    artifact_type=None,
                    source_path=None,
                    target_path=None,
                    status="missing",
                    note="artifact id not found in runtime benchmark brain",
                )
            )
            continue

        if record.target_path.exists():
            review_results.append(
                ReviewResult(
                    artifact_id=record.artifact_id,
                    artifact_type=record.artifact_type,
                    source_path=record.source_path,
                    target_path=record.target_path,
                    status="already_seeded",
                    note="target artifact already exists in seeded benchmark brain",
                )
            )
            continue

        review_results.append(
            ReviewResult(
                artifact_id=record.artifact_id,
                artifact_type=record.artifact_type,
                source_path=record.source_path,
                target_path=record.target_path,
                status="ready",
                note="artifact is valid and ready to be seeded",
            )
        )

    return review_results


def apply_seeding(review_results: list[ReviewResult]) -> list[ReviewResult]:
    applied: list[ReviewResult] = []

    for result in review_results:
        if result.status != "ready":
            applied.append(result)
            continue

        if result.source_path is None or result.target_path is None or result.artifact_type is None:
            raise ValueError(f"incomplete review result for artifact: {result.artifact_id}")

        result.target_path.parent.mkdir(parents=True, exist_ok=True)

        if result.target_path.exists():
            raise ValueError(
                f"refusing to overwrite existing seeded artifact: {result.target_path}"
            )

        shutil.copy2(result.source_path, result.target_path)

        applied.append(
            ReviewResult(
                artifact_id=result.artifact_id,
                artifact_type=result.artifact_type,
                source_path=result.source_path,
                target_path=result.target_path,
                status="seeded",
                note="artifact copied into seeded benchmark brain",
            )
        )

    return applied


def print_runtime_artifact_listing(records: list[RuntimeArtifactRecord]) -> None:
    print("runtime benchmark artifacts:")
    if not records:
        print("- none")
        return

    for record in records:
        print(
            f"- id={record.artifact_id} "
            f"type={record.artifact_type} "
            f"category={record.category} "
            f"source={record.source_path}"
        )


def print_review_summary(
    review_results: list[ReviewResult],
    *,
    title: str = "review summary",
) -> None:
    print(f"{title}:")
    if not review_results:
        print("- none")
        return

    for result in review_results:
        print(
            f"- id={result.artifact_id} "
            f"status={result.status} "
            f"note={result.note}"
        )

    summary_counts: dict[str, int] = {}
    for result in review_results:
        summary_counts[result.status] = summary_counts.get(result.status, 0) + 1

    print("status counts:")
    for status in sorted(summary_counts):
        print(f"- {status}: {summary_counts[status]}")


def resolve_selected_ids(
    records: list[RuntimeArtifactRecord],
    *,
    selected_ids: list[str],
    select_all: bool,
) -> list[str]:
    if select_all and selected_ids:
        raise ValueError("use either --all or --artifact-id, not both")

    if select_all:
        return [record.artifact_id for record in records]

    if not selected_ids:
        raise ValueError("provide --list, --all, or at least one --artifact-id")

    return selected_ids


def _ensure_path_within_root(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} is outside expected root: {path}") from exc


def _require_string_field(data: dict[str, Any], field_name: str, label: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{label} field '{field_name}' must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} field '{field_name}' must not be empty")
    return cleaned


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def main() -> None:
    """
    Run manual review or selective seeding for runtime benchmark artifacts.
    """
    args = parse_args()
    validate_cli_args(args)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    paths = get_benchmark_paths(repo_root)
    validate_required_benchmark_roots(paths)

    runtime_records = discover_runtime_artifacts(paths)

    if args.list:
        print_runtime_artifact_listing(runtime_records)
        return

    selected_ids = resolve_selected_ids(
        runtime_records,
        selected_ids=args.artifact_id,
        select_all=args.all,
    )

    review_results = review_selected_artifacts(
        runtime_records,
        selected_ids=selected_ids,
    )
    print_review_summary(review_results, title="review summary")

    if not args.apply:
        print("dry-run only: no seeded benchmark artifacts were modified")
        return

    print("applying selected artifact seeding...")
    applied_results = apply_seeding(review_results)
    print_review_summary(applied_results, title="apply summary")


if __name__ == "__main__":
    main()