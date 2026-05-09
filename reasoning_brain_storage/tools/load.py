# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, cast

from .errors import BrainConflictError, BrainValidationError
from .policy import (
    BRAIN_DIRECTORY_NAME,
    REQUIRED_BRAIN_SUBDIRECTORIES,
    ensure_reasoning_brain_root,
)
from .types import BrainState, GovernanceBrainState


def load_brain(*, root: Path) -> BrainState:
    """
    Load a reasoning brain as read-only state handle.
    """
    ensure_reasoning_brain_root(root)

    working_context_path = root / "views" / "working_context.json"
    return BrainState(
        root=root,
        working_context_path=working_context_path,
    )


def load_benchmark_visible_working_context(*, root: Path) -> dict[str, object]:
    """
    Load the canonical benchmark-visible working context from working_context.json.

    This helper reads only the benchmark-visible compact context view and does not
    reconstruct context from artifact folders.
    """
    brain = load_brain(root=root)
    raw_value = json.loads(brain.working_context_path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, Mapping):
        raise BrainValidationError("working_context.json must contain a mapping")

    return _validate_benchmark_visible_working_context(raw_value)


def export_governance_brain_state(*, brain: BrainState) -> GovernanceBrainState:
    """
    Export the minimal read-only brain_state snapshot required by governance v1.

    The exported snapshot is built only from canonical persisted artifacts under
    brain/<plural-category>/ and excludes runtime, relations, and live handles.
    """
    if not isinstance(brain, BrainState):
        raise BrainValidationError("brain must be a BrainState")

    ensure_reasoning_brain_root(brain.root)

    artifact_root = brain.root / BRAIN_DIRECTORY_NAME
    artifacts_by_id: dict[str, Mapping[str, object]] = {}

    for subdirectory in REQUIRED_BRAIN_SUBDIRECTORIES:
        artifact_dir = artifact_root / subdirectory
        for artifact_path in sorted(artifact_dir.glob("*.json"), key=lambda path: path.name):
            if not artifact_path.is_file():
                continue

            artifact = _load_persisted_artifact(artifact_path)
            artifact_id = _require_artifact_id(artifact, artifact_path)

            if artifact_id in artifacts_by_id:
                raise BrainConflictError(
                    "duplicate artifact id in persisted brain state: "
                    f"{artifact_id} in {artifact_path}"
                )

            artifacts_by_id[artifact_id] = _freeze_mapping(artifact)

    snapshot = {
        "artifacts_by_id": MappingProxyType(dict(artifacts_by_id)),
    }
    return cast(GovernanceBrainState, MappingProxyType(snapshot))


def _validate_benchmark_visible_working_context(
    context: Mapping[str, object],
) -> dict[str, object]:
    active_task = context.get("active_task")
    if active_task is not None and not isinstance(active_task, str):
        raise BrainValidationError("active_task must be a string or null")

    normalized: dict[str, object] = {
        "active_task": active_task,
    }

    for field_name in ("tasks", "constraints", "decisions", "procedures", "open_issues"):
        value = context.get(field_name)
        if value is None and field_name in {"tasks", "procedures"}:
            value = []
        if not isinstance(value, list):
            raise BrainValidationError(f"{field_name} must be a list")

        normalized_values: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise BrainValidationError(f"{field_name} must contain only strings")
            cleaned = item.strip()
            if not cleaned:
                raise BrainValidationError(f"{field_name} must not contain empty strings")
            normalized_values.append(cleaned)

        normalized[field_name] = normalized_values

    return normalized


def _load_persisted_artifact(artifact_path: Path) -> dict[str, object]:
    try:
        raw_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BrainValidationError(
            f"artifact file is not valid JSON: {artifact_path}"
        ) from exc

    if not isinstance(raw_payload, Mapping):
        raise BrainValidationError(
            f"artifact file must contain a mapping: {artifact_path}"
        )

    normalized_payload: dict[str, object] = {}
    for key in sorted(raw_payload.keys()):
        if not isinstance(key, str):
            raise BrainValidationError(
                f"artifact keys must be strings: {artifact_path}"
            )
        normalized_payload[key] = _freeze_value(raw_payload[key], artifact_path)

    return normalized_payload


def _require_artifact_id(artifact: Mapping[str, object], artifact_path: Path) -> str:
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise BrainValidationError(
            f"artifact file must contain a non-empty string id: {artifact_path}"
        )
    return artifact_id.strip()


def _freeze_mapping(payload: Mapping[str, object]) -> Mapping[str, object]:
    frozen_payload: dict[str, object] = {}
    for key in sorted(payload.keys()):
        if not isinstance(key, str):
            raise BrainValidationError("artifact keys must be strings")
        frozen_payload[key] = _freeze_value(payload[key], None)
    return MappingProxyType(frozen_payload)


def _freeze_value(value: object, artifact_path: Path | None) -> object:
    if isinstance(value, Mapping):
        normalized_dict: dict[str, object] = {}
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                location = f": {artifact_path}" if artifact_path is not None else ""
                raise BrainValidationError(
                    f"nested artifact keys must be strings{location}"
                )
            normalized_dict[key] = _freeze_value(value[key], artifact_path)
        return MappingProxyType(normalized_dict)

    if isinstance(value, list):
        return [_freeze_value(item, artifact_path) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    location = f": {artifact_path}" if artifact_path is not None else ""
    raise BrainValidationError(
        f"unsupported artifact value type in persisted state: {type(value).__name__}{location}"
    )
