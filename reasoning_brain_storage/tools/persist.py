# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .errors import BrainConflictError, BrainValidationError
from .policy import (
    BRAIN_DIRECTORY_NAME,
    assert_child_path,
    ensure_reasoning_brain_root,
    get_artifact_storage_dir,
)
from .types import PersistArtifactResult


def persist_artifact(
    *,
    runtime_root: Path,
    artifact: Mapping[str, object],
) -> PersistArtifactResult:
    """
    Persist an already-accepted artifact into runtime brain storage.

    Contract:
    - storage does NOT decide acceptance
    - storage only performs storage-domain validation and persistence
    - no silent overwrite is allowed

    This function assumes governance/acceptance has already happened upstream.
    """
    _validate_runtime_root(runtime_root)
    normalized_artifact = _normalize_artifact_for_persistence(artifact)

    artifact_id = _require_non_empty_string(normalized_artifact, "id")
    artifact_type = _require_non_empty_string(normalized_artifact, "type")

    artifact_root = runtime_root / BRAIN_DIRECTORY_NAME
    artifact_dir = get_artifact_storage_dir(runtime_root, artifact_type)
    assert_child_path(artifact_dir, artifact_root, "artifact storage directory")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = artifact_dir / f"{artifact_id}.json"
    assert_child_path(artifact_path, artifact_root, "artifact path")

    if artifact_path.exists():
        raise BrainConflictError(
            f"refusing to overwrite existing artifact: {artifact_path}"
        )

    artifact_path.write_text(
        json.dumps(normalized_artifact, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    return PersistArtifactResult(
        persisted=True,
        storage_reason="persisted",
        artifact_path=artifact_path,
        conflict_path=None,
    )


def _validate_runtime_root(runtime_root: object) -> Path:
    if not isinstance(runtime_root, Path):
        raise BrainValidationError("runtime_root must be a pathlib.Path")

    if not runtime_root.exists():
        raise BrainValidationError(f"runtime_root does not exist: {runtime_root}")

    if not runtime_root.is_dir():
        raise BrainValidationError(f"runtime_root must be a directory: {runtime_root}")

    ensure_reasoning_brain_root(runtime_root)
    return runtime_root


def _normalize_artifact_for_persistence(
    artifact: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(artifact, Mapping):
        raise BrainValidationError("artifact must be a mapping")

    normalized: dict[str, object] = {}
    for key in sorted(artifact.keys()):
        if not isinstance(key, str):
            raise BrainValidationError("artifact keys must be strings")
        normalized[key] = _normalize_value(artifact[key])

    return normalized


def _normalize_value(value: object) -> object:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    if isinstance(value, Mapping):
        normalized_dict: dict[str, object] = {}
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                raise BrainValidationError("nested artifact keys must be strings")
            normalized_dict[key] = _normalize_value(value[key])
        return normalized_dict

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    raise BrainValidationError(
        f"unsupported artifact value type for persistence: {type(value).__name__}"
    )


def _require_non_empty_string(
    artifact: Mapping[str, object],
    field_name: str,
) -> str:
    value = artifact.get(field_name)
    if not isinstance(value, str):
        raise BrainValidationError(f"artifact field '{field_name}' must be a string")

    cleaned = value.strip()
    if not cleaned:
        raise BrainValidationError(
            f"artifact field '{field_name}' must not be empty"
        )

    return cleaned
