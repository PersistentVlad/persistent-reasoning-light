# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Storage-level safety and invariant enforcement helpers.

This module does NOT perform:
- artifact acceptance decisions
- duplicate detection
- governance logic

All decision-making belongs to reasoning_governance_light.

This module only enforces storage-domain safety constraints.
"""

from __future__ import annotations

from pathlib import Path

from .errors import BrainConflictError, BrainValidationError


BRAIN_DIRECTORY_NAME = "brain"
RUNTIME_DIRECTORY_NAME = "runtime"
RELATIONS_DIRECTORY_NAME = "relations"
VIEWS_DIRECTORY_NAME = "views"
WORKING_CONTEXT_FILENAME = "working_context.json"

CANONICAL_ARTIFACT_DIRECTORY_BY_TYPE = {
    "task": "tasks",
    "decision": "decisions",
    "constraint": "constraints",
    "procedure": "procedures",
    "issue": "issues",
}

REQUIRED_BRAIN_SUBDIRECTORIES = tuple(CANONICAL_ARTIFACT_DIRECTORY_BY_TYPE.values())
REQUIRED_RUNTIME_SUBDIRECTORIES = ("drafts", "inbox")


def require_existing_directory(path: Path, label: str) -> None:
    """
    Require that a path exists and is a directory.
    """
    _require_path_object(path, label)

    if not path.exists():
        raise BrainValidationError(f"{label} does not exist: {path}")

    if not path.is_dir():
        raise BrainValidationError(f"{label} must be a directory: {path}")


def require_existing_file(path: Path, label: str) -> None:
    """
    Require that a path exists and is a file.
    """
    _require_path_object(path, label)

    if not path.exists():
        raise BrainValidationError(f"{label} does not exist: {path}")

    if not path.is_file():
        raise BrainValidationError(f"{label} must be a file: {path}")


def forbid_existing_path(path: Path, label: str) -> None:
    """
    Forbid operations that would silently overwrite an existing path.
    """
    _require_path_object(path, label)

    if path.exists():
        raise BrainConflictError(f"{label} already exists: {path}")


def ensure_reasoning_brain_root(root: Path) -> None:
    """
    Validate that a reasoning brain root exists and has the canonical v1 structure.
    """
    require_existing_directory(root, "reasoning brain root")

    brain_dir = root / BRAIN_DIRECTORY_NAME
    require_existing_directory(brain_dir, "reasoning brain artifact directory")
    for subdirectory in REQUIRED_BRAIN_SUBDIRECTORIES:
        require_existing_directory(
            brain_dir / subdirectory,
            f"reasoning brain artifact subdirectory '{subdirectory}'",
        )

    runtime_dir = root / RUNTIME_DIRECTORY_NAME
    require_existing_directory(runtime_dir, "reasoning brain runtime directory")
    for subdirectory in REQUIRED_RUNTIME_SUBDIRECTORIES:
        require_existing_directory(
            runtime_dir / subdirectory,
            f"reasoning brain runtime subdirectory '{subdirectory}'",
        )

    relations_dir = root / RELATIONS_DIRECTORY_NAME
    require_existing_directory(relations_dir, "reasoning brain relations directory")

    views_dir = root / VIEWS_DIRECTORY_NAME
    require_existing_directory(views_dir, "reasoning brain views directory")

    working_context_path = views_dir / WORKING_CONTEXT_FILENAME
    require_existing_file(
        working_context_path,
        "reasoning brain working_context.json",
    )


def get_artifact_storage_dir(root: Path, artifact_type: str) -> Path:
    """
    Resolve the canonical persistence directory for a supported artifact type.
    """
    ensure_reasoning_brain_root(root)

    if not isinstance(artifact_type, str):
        raise BrainValidationError("artifact_type must be a string")

    cleaned_type = artifact_type.strip()
    if not cleaned_type:
        raise BrainValidationError("artifact_type must not be empty")

    directory_name = CANONICAL_ARTIFACT_DIRECTORY_BY_TYPE.get(cleaned_type)
    if directory_name is None:
        raise BrainValidationError(f"unsupported artifact type: {cleaned_type}")

    artifact_root = root / BRAIN_DIRECTORY_NAME
    artifact_dir = artifact_root / directory_name
    assert_child_path(artifact_dir, artifact_root, "artifact storage directory")
    return artifact_dir


def assert_child_path(path: Path, root: Path, label: str) -> None:
    """
    Ensure that a path is contained within the expected root.

    This helps prevent accidental writes outside the intended brain domain.
    """
    _require_path_object(path, label)
    _require_path_object(root, "root")
    require_existing_directory(root, "root")

    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise BrainValidationError(
            f"{label} must remain inside root {root}: {path}"
        ) from exc


def _require_path_object(path: object, label: str) -> None:
    if not isinstance(path, Path):
        raise BrainValidationError(f"{label} must be a pathlib.Path")
