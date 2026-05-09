# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from collections.abc import Mapping
from pathlib import Path

from core.artifact_cards import (
    ArtifactCard,
    BaseArtifact,
    artifact_from_dict,
    artifact_to_dict,
)
from core.artifact_types import (
    RUNTIME_DRAFTS_DIRECTORY,
    RUNTIME_INBOX_DIRECTORY,
    TYPE_TO_CANONICAL_SUBPATH,
    get_directory_for_artifact_type,
    get_prefix_for_artifact_type,
)
from core.validation import validate_artifact_id, validate_artifact_schema


RUNTIME_SUBPATHS = {
    "drafts": RUNTIME_DRAFTS_DIRECTORY,
    "inbox": RUNTIME_INBOX_DIRECTORY,
}


def resolve_canonical_artifact_path(
    brain_root: Path | str,
    artifact_type: str,
    artifact_id: str,
) -> Path:
    artifact_id = validate_artifact_id(artifact_id)
    expected_prefix = get_prefix_for_artifact_type(artifact_type)
    if not artifact_id.startswith(f"{expected_prefix}_"):
        raise ValueError(
            f"artifact id prefix mismatch for type {artifact_type}: {artifact_id}"
        )
    return _ensure_brain_root(brain_root) / get_directory_for_artifact_type(
        artifact_type
    ) / f"{artifact_id}.json"


def resolve_runtime_artifact_path(
    brain_root: Path | str,
    runtime_area: str,
    artifact_id: str,
) -> Path:
    artifact_id = validate_artifact_id(artifact_id)
    return _ensure_brain_root(brain_root) / _get_runtime_subpath(runtime_area) / (
        f"{artifact_id}.json"
    )


def save_canonical_artifact(
    brain_root: Path | str,
    artifact: ArtifactCard | Mapping[str, object],
) -> Path:
    artifact_data = _coerce_artifact_mapping(artifact)
    artifact_path = resolve_canonical_artifact_path(
        brain_root,
        artifact_data["type"],
        artifact_data["id"],
    )
    _ensure_parent_directory_exists(artifact_path)
    if artifact_path.exists():
        raise FileExistsError(f"artifact already exists: {artifact_path}")
    _write_json_file(artifact_path, artifact_data)
    return artifact_path


def load_canonical_artifact(
    brain_root: Path | str,
    artifact_type: str,
    artifact_id: str,
) -> ArtifactCard:
    artifact_path = resolve_canonical_artifact_path(brain_root, artifact_type, artifact_id)
    artifact_data = _read_artifact_file(artifact_path)
    _validate_filename_matches_id(artifact_path, artifact_data["id"])
    return artifact_from_dict(artifact_data)


def list_canonical_artifacts(
    brain_root: Path | str,
    artifact_type: str,
) -> list[ArtifactCard]:
    directory_path = _ensure_brain_root(brain_root) / get_directory_for_artifact_type(
        artifact_type
    )
    if not directory_path.exists():
        return []
    if not directory_path.is_dir():
        raise ValueError(f"canonical artifact path is not a directory: {directory_path}")

    artifacts: list[ArtifactCard] = []
    for artifact_path in sorted(directory_path.glob("*.json")):
        artifact_data = _read_artifact_file(artifact_path)
        _validate_filename_matches_id(artifact_path, artifact_data["id"])
        artifacts.append(artifact_from_dict(artifact_data))
    return artifacts


def list_canonical_artifact_ids(brain_root: Path | str) -> list[str]:
    artifact_ids: list[str] = []
    for artifact_type in TYPE_TO_CANONICAL_SUBPATH:
        artifacts = list_canonical_artifacts(brain_root, artifact_type)
        artifact_ids.extend(artifact.id for artifact in artifacts)
    return sorted(artifact_ids)


def save_runtime_artifact(
    brain_root: Path | str,
    runtime_area: str,
    artifact: ArtifactCard | Mapping[str, object],
) -> Path:
    artifact_data = _coerce_artifact_mapping(artifact)
    artifact_path = resolve_runtime_artifact_path(
        brain_root,
        runtime_area,
        artifact_data["id"],
    )
    _ensure_parent_directory_exists(artifact_path)
    if artifact_path.exists():
        raise FileExistsError(f"runtime artifact already exists: {artifact_path}")
    _write_json_file(artifact_path, artifact_data)
    return artifact_path


def load_runtime_artifact(
    brain_root: Path | str,
    runtime_area: str,
    artifact_id: str,
) -> dict[str, object]:
    artifact_path = resolve_runtime_artifact_path(brain_root, runtime_area, artifact_id)
    artifact_data = _read_artifact_file(artifact_path)
    _validate_filename_matches_id(artifact_path, artifact_data["id"])
    return artifact_data


def list_runtime_artifacts(
    brain_root: Path | str,
    runtime_area: str,
) -> list[dict[str, object]]:
    directory_path = _ensure_brain_root(brain_root) / _get_runtime_subpath(runtime_area)
    if not directory_path.exists():
        return []
    if not directory_path.is_dir():
        raise ValueError(f"runtime artifact path is not a directory: {directory_path}")

    artifacts: list[dict[str, object]] = []
    for artifact_path in sorted(directory_path.glob("*.json")):
        artifact_data = _read_artifact_file(artifact_path)
        _validate_filename_matches_id(artifact_path, artifact_data["id"])
        artifacts.append(artifact_data)
    return artifacts


def _coerce_artifact_mapping(
    artifact: ArtifactCard | Mapping[str, object],
) -> dict[str, object]:
    if isinstance(artifact, BaseArtifact):
        artifact_data = artifact_to_dict(artifact)
    elif isinstance(artifact, Mapping):
        artifact_data = dict(artifact)
    else:
        raise ValueError("artifact must be a mapping or artifact card")

    validate_artifact_schema(artifact_data)
    return artifact_data


def _read_artifact_file(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"artifact file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"artifact path is not a file: {path}")

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid artifact JSON: {path}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError(f"artifact data must be a JSON object: {path}")

    validate_artifact_schema(raw_data)
    return dict(raw_data)


def _write_json_file(path: Path, data: Mapping[str, object]) -> None:
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


def _validate_filename_matches_id(path: Path, artifact_id: object) -> None:
    validated_id = validate_artifact_id(artifact_id)
    if path.stem != validated_id:
        raise ValueError(f"artifact filename does not match artifact id: {path}")


def _get_runtime_subpath(runtime_area: str) -> Path:
    if runtime_area not in RUNTIME_SUBPATHS:
        raise ValueError(f"invalid runtime area: {runtime_area}")
    return RUNTIME_SUBPATHS[runtime_area]


__all__ = [
    "RUNTIME_SUBPATHS",
    "list_canonical_artifact_ids",
    "list_canonical_artifacts",
    "list_runtime_artifacts",
    "load_canonical_artifact",
    "load_runtime_artifact",
    "resolve_canonical_artifact_path",
    "resolve_runtime_artifact_path",
    "save_canonical_artifact",
    "save_runtime_artifact",
]
