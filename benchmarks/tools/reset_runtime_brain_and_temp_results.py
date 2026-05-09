# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Reset the runtime benchmark brain and optionally clean temporary benchmark result artifacts.

This tool is a controlled maintenance utility for benchmark runs.

It may:
- remove the current benchmarks-runtime-reasoning-brain directory
- recreate it from benchmarks-empty-reasoning-brain
- optionally remove temporary benchmark artifacts from benchmarks/results/

It does not:
- run benchmark scenarios
- modify the seeded benchmark brain
- delete benchmark reports
- silently clean artifacts without explicit operator intent

Result cleanup removes artifact files only.
Mode result directories intentionally remain in place.

Usage examples:
- reset runtime brain only:
    python benchmarks/tools/reset_runtime_brain_and_temp_results.py --reset-runtime-brain

- reset runtime brain and remove result artifacts:
    python benchmarks/tools/reset_runtime_brain_and_temp_results.py --reset-runtime-brain --clean-results

- dry-run preview:
    python benchmarks/tools/reset_runtime_brain_and_temp_results.py --reset-runtime-brain --clean-results --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


# Temporary PoC import bootstrap.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.benchmark_modes import (  # noqa: E402
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmark_adapters.common.benchmark_paths import (  # noqa: E402
    BenchmarkPaths,
    RESULT_CLEANUP_SUFFIXES,
    get_benchmark_paths,
    validate_required_benchmark_roots,
)


@dataclass(frozen=True)
class PlannedAction:
    action_type: str
    path: Path
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset runtime benchmark brain and optionally clean temporary benchmark result artifacts."
    )
    parser.add_argument(
        "--reset-runtime-brain",
        action="store_true",
        help="Remove benchmarks-runtime-reasoning-brain and recreate it from benchmarks-empty-reasoning-brain.",
    )
    parser.add_argument(
        "--clean-results",
        action="store_true",
        help="Remove benchmark result artifacts from benchmarks/results/ for all modes.",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="Optional scenario id filter for result cleanup. May be provided multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned actions without modifying the filesystem.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Optional repository root override.",
    )
    return parser.parse_args()


def validate_cli_args(args: argparse.Namespace) -> None:
    if not args.reset_runtime_brain and not args.clean_results:
        raise ValueError(
            "provide at least one action: --reset-runtime-brain or --clean-results"
        )

    if args.scenario_id and not args.clean_results:
        raise ValueError(
            "--scenario-id may only be used together with --clean-results"
        )

    if args.scenario_id:
        cleaned_ids = [value.strip() for value in args.scenario_id]
        if len(cleaned_ids) != len(set(cleaned_ids)):
            raise ValueError("duplicate values detected in --scenario-id arguments")


def build_runtime_brain_reset_actions(paths: BenchmarkPaths) -> list[PlannedAction]:
    actions: list[PlannedAction] = []

    runtime_root = paths.runtime_brain_root
    empty_root = paths.empty_brain_root

    _ensure_path_within_root(runtime_root, paths.repo_root, "runtime benchmark brain root")
    _ensure_path_within_root(empty_root, paths.repo_root, "empty benchmark brain root")

    if not empty_root.exists():
        raise FileNotFoundError(f"empty benchmark brain root not found: {empty_root}")
    if not empty_root.is_dir():
        raise ValueError(f"empty benchmark brain root is not a directory: {empty_root}")

    if runtime_root.exists():
        actions.append(
            PlannedAction(
                action_type="remove_runtime_brain",
                path=runtime_root,
                note="remove existing runtime benchmark brain directory",
            )
        )

    actions.append(
        PlannedAction(
            action_type="copy_empty_to_runtime",
            path=runtime_root,
            note="recreate runtime benchmark brain from empty benchmark brain",
        )
    )

    return actions


def build_result_cleanup_actions(
    paths: BenchmarkPaths,
    *,
    scenario_ids: list[str],
) -> list[PlannedAction]:
    actions: list[PlannedAction] = []

    cleaned_ids = [_normalize_required_text(value, "scenario_id") for value in scenario_ids]
    selected_ids = set(cleaned_ids)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        mode_dir = paths.results_root / mode
        _ensure_path_within_root(mode_dir, paths.results_root, "benchmark results mode directory")

        if not mode_dir.exists():
            continue
        if not mode_dir.is_dir():
            raise ValueError(f"results mode path is not a directory: {mode_dir}")

        for artifact_path in sorted(mode_dir.iterdir()):
            if not artifact_path.is_file():
                continue

            matched_suffix = _match_allowed_result_suffix(artifact_path.name)
            if matched_suffix is None:
                continue

            scenario_id = artifact_path.name[: -len(matched_suffix)]
            if selected_ids and scenario_id not in selected_ids:
                continue

            actions.append(
                PlannedAction(
                    action_type="remove_result_artifact",
                    path=artifact_path,
                    note=f"remove benchmark result artifact for mode '{mode}'",
                )
            )

    return actions


def build_preparation_reset_actions(paths: BenchmarkPaths) -> list[PlannedAction]:
    """
    Build the canonical benchmark preparation reset action set.

    Preparation reset must:
    - recreate the runtime benchmark brain from the empty benchmark brain
    - remove temporary benchmark result artifacts across all modes
    """
    actions: list[PlannedAction] = []
    actions.extend(build_runtime_brain_reset_actions(paths))
    actions.extend(build_result_cleanup_actions(paths, scenario_ids=[]))
    return actions


def apply_actions(
    actions: list[PlannedAction],
    *,
    paths: BenchmarkPaths,
    dry_run: bool,
) -> None:
    if dry_run:
        print("dry-run: no filesystem changes will be applied")
        return

    print("applying actions...")

    for action in actions:
        if action.action_type == "remove_runtime_brain":
            if action.path.exists():
                shutil.rmtree(action.path)
            continue

        if action.action_type == "copy_empty_to_runtime":
            if action.path.exists():
                raise ValueError(
                    f"refusing to overwrite existing runtime benchmark brain: {action.path}"
                )
            shutil.copytree(paths.empty_brain_root, action.path)
            continue

        if action.action_type == "remove_result_artifact":
            if action.path.exists():
                action.path.unlink()
            continue

        raise ValueError(f"unsupported planned action type: {action.action_type}")


def print_action_summary(actions: list[PlannedAction]) -> None:
    print("planned actions:")
    if not actions:
        print("- none")
        return

    for action in actions:
        print(
            f"- action={action.action_type} "
            f"path={action.path} "
            f"note={action.note}"
        )

    counts: dict[str, int] = {}
    for action in actions:
        counts[action.action_type] = counts.get(action.action_type, 0) + 1

    print("action counts:")
    for action_type in sorted(counts):
        print(f"- {action_type}: {counts[action_type]}")


def _match_allowed_result_suffix(filename: str) -> str | None:
    for suffix in RESULT_CLEANUP_SUFFIXES:
        if filename.endswith(suffix):
            return suffix
    return None


def _ensure_path_within_root(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} is outside expected root: {path}") from exc


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def prepare_clean_benchmark_runtime(
    repo_root: Path | None = None,
    *,
    dry_run: bool = False,
) -> list[PlannedAction]:
    """
    Execute the canonical benchmark preparation reset.

    This is the preparation-phase entrypoint for full benchmark runs.
    """
    resolved_repo_root = repo_root.resolve() if repo_root else REPO_ROOT
    paths = get_benchmark_paths(resolved_repo_root)
    validate_required_benchmark_roots(paths)

    actions = build_preparation_reset_actions(paths)
    print_action_summary(actions)
    apply_actions(actions, paths=paths, dry_run=dry_run)
    return actions


def clean_temporary_benchmark_results(
    repo_root: Path | None = None,
    *,
    scenario_ids: list[str] | None = None,
    dry_run: bool = False,
) -> list[PlannedAction]:
    """
    Remove temporary benchmark result artifacts without changing brain state.

    This helper keeps benchmark artifact cleanup separate from storage-owned
    runtime brain lifecycle operations.
    """
    resolved_repo_root = repo_root.resolve() if repo_root else REPO_ROOT
    paths = get_benchmark_paths(resolved_repo_root)
    validate_required_benchmark_roots(paths)

    actions = build_result_cleanup_actions(paths, scenario_ids=scenario_ids or [])
    print_action_summary(actions)
    apply_actions(actions, paths=paths, dry_run=dry_run)
    return actions


def main() -> None:
    """
    Run controlled runtime benchmark brain reset and temporary result cleanup.
    """
    args = parse_args()
    validate_cli_args(args)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    paths = get_benchmark_paths(repo_root)
    validate_required_benchmark_roots(paths)

    actions: list[PlannedAction] = []

    if args.reset_runtime_brain and args.clean_results and not args.scenario_id:
        actions = build_preparation_reset_actions(paths)
    else:
        if args.reset_runtime_brain:
            actions.extend(build_runtime_brain_reset_actions(paths))

        if args.clean_results:
            actions.extend(
                build_result_cleanup_actions(
                    paths,
                    scenario_ids=args.scenario_id,
                )
            )

    print_action_summary(actions)
    apply_actions(actions, paths=paths, dry_run=args.dry_run)

    if args.dry_run:
        print("dry-run complete")
    else:
        print("runtime benchmark reset/cleanup complete")


if __name__ == "__main__":
    main()
