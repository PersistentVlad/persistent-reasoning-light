# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from dataclasses import dataclass
from pathlib import Path

from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    RELATION_BLOCKS,
    RELATION_DEPENDS_ON,
    RELATIONS_DIRECTORY,
    SUPPORTED_RELATION_FILES,
    TASK_CARD,
    get_artifact_type_for_prefix,
)
from core.storage import list_canonical_artifact_ids
from core.validation import validate_artifact_id


RELATION_TYPE_RULES = {
    RELATION_DEPENDS_ON: (TASK_CARD, DECISION_CARD),
    RELATION_BLOCKS: (CONSTRAINT_CARD, TASK_CARD),
}


@dataclass(frozen=True)
class RelationEdge:
    relation_file: str
    from_id: str
    to_id: str


def load_relation_file(
    brain_root: Path | str,
    relation_file: str,
) -> list[RelationEdge]:
    _ensure_brain_root(brain_root)
    relation_path = resolve_relation_path(brain_root, relation_file)
    if not relation_path.exists():
        return []
    if not relation_path.is_file():
        raise ValueError(f"relation path is not a file: {relation_path}")

    canonical_ids = set(list_canonical_artifact_ids(brain_root))
    edges: list[RelationEdge] = []
    for line_number, line in enumerate(
        relation_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        edge = _parse_relation_line(
            relation_file,
            line,
            line_number,
            canonical_ids,
        )
        if edge is not None:
            edges.append(edge)
    return sorted(edges, key=lambda edge: (edge.from_id, edge.to_id))


def load_all_relations(brain_root: Path | str) -> dict[str, list[RelationEdge]]:
    relations: dict[str, list[RelationEdge]] = {}
    for relation_file in SUPPORTED_RELATION_FILES:
        relations[relation_file] = load_relation_file(brain_root, relation_file)
    return relations


def find_outgoing_relations(
    edges: list[RelationEdge],
    artifact_id: str,
) -> list[RelationEdge]:
    validate_artifact_id(artifact_id)
    return [edge for edge in edges if edge.from_id == artifact_id]


def find_incoming_relations(
    edges: list[RelationEdge],
    artifact_id: str,
) -> list[RelationEdge]:
    validate_artifact_id(artifact_id)
    return [edge for edge in edges if edge.to_id == artifact_id]


def resolve_relation_path(brain_root: Path | str, relation_file: str) -> Path:
    _ensure_supported_relation_file(relation_file)
    return _ensure_brain_root(brain_root) / RELATIONS_DIRECTORY / relation_file


def _parse_relation_line(
    relation_file: str,
    line: str,
    line_number: int,
    canonical_ids: set[str],
) -> RelationEdge | None:
    if not line.strip():
        return None

    try:
        raw_value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid relation JSON in {relation_file}:{line_number}"
        ) from exc

    if not isinstance(raw_value, dict):
        raise ValueError(
            f"relation entry must be a JSON object in {relation_file}:{line_number}"
        )

    return _build_relation_edge(relation_file, line_number, raw_value, canonical_ids)


def _build_relation_edge(
    relation_file: str,
    line_number: int,
    raw_value: dict[str, object],
    canonical_ids: set[str],
) -> RelationEdge:
    allowed_fields = {"from", "to"}
    unexpected_fields = sorted(field for field in raw_value if field not in allowed_fields)
    if unexpected_fields:
        fields = ", ".join(unexpected_fields)
        raise ValueError(
            f"unexpected relation fields in {relation_file}:{line_number}: {fields}"
        )

    if "from" not in raw_value or "to" not in raw_value:
        raise ValueError(f"missing relation fields in {relation_file}:{line_number}")

    from_id = validate_artifact_id(raw_value["from"])
    to_id = validate_artifact_id(raw_value["to"])
    if from_id == to_id:
        raise ValueError(f"self-edge relation is forbidden in {relation_file}:{line_number}")
    if from_id not in canonical_ids or to_id not in canonical_ids:
        raise ValueError(
            f"dangling relation reference in {relation_file}:{line_number}"
        )

    _validate_relation_semantics(relation_file, from_id, to_id, line_number)
    return RelationEdge(relation_file=relation_file, from_id=from_id, to_id=to_id)


def _validate_relation_semantics(
    relation_file: str,
    from_id: str,
    to_id: str,
    line_number: int,
) -> None:
    expected_from_type, expected_to_type = RELATION_TYPE_RULES[relation_file]
    actual_from_type = _get_artifact_type_for_id(from_id)
    actual_to_type = _get_artifact_type_for_id(to_id)

    if actual_from_type != expected_from_type or actual_to_type != expected_to_type:
        raise ValueError(
            f"invalid relation semantics in {relation_file}:{line_number}"
        )


def _get_artifact_type_for_id(artifact_id: str) -> str:
    prefix = artifact_id.split("_", 1)[0]
    return get_artifact_type_for_prefix(prefix)


def _ensure_supported_relation_file(relation_file: str) -> str:
    if relation_file not in SUPPORTED_RELATION_FILES:
        raise ValueError(f"invalid relation file: {relation_file}")
    return relation_file


def _ensure_brain_root(brain_root: Path | str) -> Path:
    path = Path(brain_root)
    if not path.exists():
        raise FileNotFoundError(f"reasoning brain root does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"reasoning brain root is not a directory: {path}")
    return path


__all__ = [
    "RELATION_TYPE_RULES",
    "RelationEdge",
    "find_incoming_relations",
    "find_outgoing_relations",
    "load_all_relations",
    "load_relation_file",
    "resolve_relation_path",
]
