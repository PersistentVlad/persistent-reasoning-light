# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from pathlib import Path

from core.artifact_cards import TaskCard
from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    RELATION_BLOCKS,
    RELATION_DEPENDS_ON,
    TASK_CARD,
    WORKING_CONTEXT_FILE,
    get_prefix_for_artifact_type,
)
from core.relations import RelationEdge, load_all_relations
from core.storage import list_canonical_artifacts


def build_working_context(brain_root: Path | str) -> dict[str, object]:
    tasks = list_canonical_artifacts(brain_root, TASK_CARD)
    active_task = _find_active_task(tasks)
    if active_task is None:
        return {
            "active_task": None,
            "constraints": [],
            "decisions": [],
            "open_issues": [],
        }

    relations = load_all_relations(brain_root)
    return {
        "active_task": active_task.id,
        "constraints": _collect_constraint_ids(active_task, relations),
        "decisions": _collect_decision_ids(active_task, relations),
        "open_issues": _collect_issue_ids(active_task),
    }


def write_working_context(brain_root: Path | str) -> Path:
    brain_root_path = _ensure_brain_root(brain_root)
    working_context = build_working_context(brain_root_path)
    working_context_path = brain_root_path / WORKING_CONTEXT_FILE
    _ensure_parent_directory_exists(working_context_path)
    _write_json_file(working_context_path, working_context)
    return working_context_path


def _find_active_task(tasks: list[TaskCard]) -> TaskCard | None:
    for task in tasks:
        if task.status == "active":
            return task
    return None


def _collect_decision_ids(
    active_task: TaskCard,
    relations: dict[str, list[RelationEdge]],
) -> list[str]:
    context_ids = _filter_context_ids(active_task.context, DECISION_CARD)
    relation_ids = _collect_relation_targets(
        relations.get(RELATION_DEPENDS_ON, []),
        active_task.id,
    )
    return sorted(set(context_ids) | set(relation_ids))


def _collect_constraint_ids(
    active_task: TaskCard,
    relations: dict[str, list[RelationEdge]],
) -> list[str]:
    context_ids = _filter_context_ids(active_task.context, CONSTRAINT_CARD)
    relation_ids = _collect_relation_sources(
        relations.get(RELATION_BLOCKS, []),
        active_task.id,
    )
    return sorted(set(context_ids) | set(relation_ids))


def _collect_issue_ids(active_task: TaskCard) -> list[str]:
    return _filter_context_ids(active_task.context, ISSUE_CARD)


def _filter_context_ids(artifact_ids: list[str], artifact_type: str) -> list[str]:
    filtered_ids: list[str] = []
    for artifact_id in artifact_ids:
        if _matches_artifact_type(artifact_id, artifact_type):
            filtered_ids.append(artifact_id)
    return sorted(filtered_ids)


def _collect_relation_targets(edges: list[RelationEdge], source_id: str) -> list[str]:
    targets: list[str] = []
    for edge in edges:
        if edge.from_id == source_id:
            targets.append(edge.to_id)
    return sorted(targets)


def _collect_relation_sources(edges: list[RelationEdge], target_id: str) -> list[str]:
    sources: list[str] = []
    for edge in edges:
        if edge.to_id == target_id:
            sources.append(edge.from_id)
    return sorted(sources)


def _matches_artifact_type(artifact_id: str, artifact_type: str) -> bool:
    prefix = get_prefix_for_artifact_type(artifact_type)
    return artifact_id.startswith(f"{prefix}_")


def _write_json_file(path: Path, data: dict[str, object]) -> None:
    json_text = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
    path.write_text(f"{json_text}\n", encoding="utf-8")


def _ensure_brain_root(brain_root: Path | str) -> Path:
    path = Path(brain_root)
    if not path.exists():
        raise FileNotFoundError(f"reasoning brain root does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"reasoning brain root is not a directory: {path}")
    return path


def _ensure_parent_directory_exists(path: Path) -> None:
    parent = path.parent
    if not parent.exists():
        raise FileNotFoundError(f"parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise ValueError(f"parent path is not a directory: {parent}")


__all__ = [
    "build_working_context",
    "write_working_context",
]
