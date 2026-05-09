# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from pathlib import Path

from core.artifact_types import WORKING_CONTEXT_FILE, get_artifact_type_for_prefix
from core.storage import load_canonical_artifact
from core.validation import validate_artifact_id


def load_working_context(brain_root: Path | str) -> dict[str, object]:
    working_context_path = _resolve_working_context_path(brain_root)
    if not working_context_path.exists():
        raise FileNotFoundError(
            f"working context file does not exist: {working_context_path}"
        )
    if not working_context_path.is_file():
        raise ValueError(f"working context path is not a file: {working_context_path}")

    try:
        raw_value = json.loads(working_context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid working context JSON: {working_context_path}") from exc

    return _validate_working_context(raw_value)


def resolve_working_context(brain_root: Path | str) -> dict[str, object]:
    working_context = load_working_context(brain_root)
    _ensure_optional_artifact_exists(brain_root, working_context["active_task"])
    _ensure_artifacts_exist(brain_root, working_context["constraints"])
    _ensure_artifacts_exist(brain_root, working_context["decisions"])
    _ensure_artifacts_exist(brain_root, working_context["open_issues"])
    return {
        "active_task": working_context["active_task"],
        "constraints": list(working_context["constraints"]),
        "decisions": list(working_context["decisions"]),
        "open_issues": list(working_context["open_issues"]),
    }


def _validate_working_context(raw_value: object) -> dict[str, object]:
    if not isinstance(raw_value, dict):
        raise ValueError("working context must be a JSON object")

    allowed_fields = {"active_task", "constraints", "decisions", "open_issues"}
    unexpected_fields = sorted(field for field in raw_value if field not in allowed_fields)
    if unexpected_fields:
        fields = ", ".join(unexpected_fields)
        raise ValueError(f"unexpected working context fields: {fields}")

    for field_name in sorted(allowed_fields):
        if field_name not in raw_value:
            raise ValueError(f"missing working context field: {field_name}")

    active_task = _validate_optional_artifact_id(raw_value["active_task"], "active_task")
    constraints = _validate_artifact_id_list(raw_value["constraints"], "constraints")
    decisions = _validate_artifact_id_list(raw_value["decisions"], "decisions")
    open_issues = _validate_artifact_id_list(raw_value["open_issues"], "open_issues")

    return {
        "active_task": active_task,
        "constraints": constraints,
        "decisions": decisions,
        "open_issues": open_issues,
    }


def _ensure_optional_artifact_exists(
    brain_root: Path | str,
    artifact_id: str | None,
) -> None:
    if artifact_id is None:
        return
    _ensure_artifact_exists(brain_root, artifact_id)


def _ensure_artifacts_exist(
    brain_root: Path | str,
    artifact_ids: list[str],
) -> None:
    for artifact_id in artifact_ids:
        _ensure_artifact_exists(brain_root, artifact_id)


def _ensure_artifact_exists(brain_root: Path | str, artifact_id: str) -> None:
    validate_artifact_id(artifact_id)
    artifact_type = _get_artifact_type_for_id(artifact_id)
    load_canonical_artifact(brain_root, artifact_type, artifact_id)


def _validate_optional_artifact_id(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return validate_artifact_id(value)


def _validate_artifact_id_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    artifact_ids: list[str] = []
    for item in value:
        artifact_ids.append(validate_artifact_id(item))
    return artifact_ids


def _get_artifact_type_for_id(artifact_id: str) -> str:
    prefix = artifact_id.split("_", 1)[0]
    return get_artifact_type_for_prefix(prefix)


def _resolve_working_context_path(brain_root: Path | str) -> Path:
    brain_root_path = Path(brain_root)
    if not brain_root_path.exists():
        raise FileNotFoundError(f"reasoning brain root does not exist: {brain_root_path}")
    if not brain_root_path.is_dir():
        raise ValueError(f"reasoning brain root is not a directory: {brain_root_path}")
    return brain_root_path / WORKING_CONTEXT_FILE


__all__ = [
    "load_working_context",
    "resolve_working_context",
]
