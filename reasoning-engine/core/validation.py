# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import re
from datetime import datetime
from typing import Mapping

from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    PROCEDURE_CARD,
    SUPPORTED_ARTIFACT_TYPES,
    TASK_CARD,
    get_artifact_type_for_prefix,
    get_prefix_for_artifact_type,
)


DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ARTIFACT_ID_PATTERN = re.compile(r"^[a-z]+_[a-z0-9]+(?:_[a-z0-9]+)*$")

BASE_REQUIRED_FIELDS = {"id", "type"}
BASE_OPTIONAL_FIELDS = {"domains", "created_at", "updated_at"}

TYPE_REQUIRED_FIELDS = {
    TASK_CARD: {"goal", "status", "context"},
    DECISION_CARD: {"statement", "reason", "status"},
    CONSTRAINT_CARD: {"statement", "reason"},
    PROCEDURE_CARD: {"name", "steps"},
    ISSUE_CARD: {"question", "priority"},
}


def validate_artifact_schema(data: Mapping[str, object]) -> None:
    if not isinstance(data, Mapping):
        raise ValueError("artifact data must be a mapping")

    artifact_type = _validate_artifact_type(data)
    _validate_declared_artifact_id(data, artifact_type)
    _validate_required_fields(data, artifact_type)
    _validate_allowed_fields(data, artifact_type)
    _validate_domains(data.get("domains"))
    _validate_timestamp_field("created_at", data.get("created_at"))
    _validate_timestamp_field("updated_at", data.get("updated_at"))
    _validate_content_fields(data, artifact_type)
    _validate_reference_context(data, artifact_type)


def validate_artifact_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("artifact id must be a string")
    if not ARTIFACT_ID_PATTERN.match(value):
        raise ValueError(f"invalid artifact id: {value}")

    prefix, _, short_name = value.partition("_")
    get_artifact_type_for_prefix(prefix)
    if not short_name:
        raise ValueError(f"invalid artifact id: {value}")
    return value


def _validate_artifact_type(data: Mapping[str, object]) -> str:
    artifact_type = data.get("type")
    if not isinstance(artifact_type, str):
        raise ValueError("artifact type must be a string")
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ValueError(f"invalid artifact type: {artifact_type}")
    return artifact_type


def _validate_declared_artifact_id(data: Mapping[str, object], artifact_type: str) -> str:
    artifact_id = validate_artifact_id(data.get("id"))
    expected_prefix = get_prefix_for_artifact_type(artifact_type)
    if not artifact_id.startswith(f"{expected_prefix}_"):
        raise ValueError(
            f"artifact id prefix mismatch for type {artifact_type}: {artifact_id}"
        )
    return artifact_id


def _validate_required_fields(data: Mapping[str, object], artifact_type: str) -> None:
    required_fields = BASE_REQUIRED_FIELDS | TYPE_REQUIRED_FIELDS[artifact_type]
    missing_fields = sorted(field for field in required_fields if field not in data)
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ValueError(f"missing required fields: {fields}")


def _validate_allowed_fields(data: Mapping[str, object], artifact_type: str) -> None:
    allowed_fields = (
        BASE_REQUIRED_FIELDS
        | BASE_OPTIONAL_FIELDS
        | TYPE_REQUIRED_FIELDS[artifact_type]
    )
    unexpected_fields = sorted(field for field in data if field not in allowed_fields)
    if unexpected_fields:
        fields = ", ".join(unexpected_fields)
        raise ValueError(f"unexpected artifact fields: {fields}")


def _validate_domains(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise ValueError("domains must be a list")
    if not value:
        raise ValueError("domains must not be empty")

    for domain in value:
        if not isinstance(domain, str):
            raise ValueError("domains must contain only strings")
        if not DOMAIN_PATTERN.match(domain):
            raise ValueError(f"invalid domain: {domain}")


def _validate_timestamp_field(field_name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not TIMESTAMP_PATTERN.match(value):
        raise ValueError(f"invalid {field_name}: {value}")

    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _validate_content_fields(data: Mapping[str, object], artifact_type: str) -> None:
    if artifact_type == TASK_CARD:
        _validate_string_field(data, "goal")
        _validate_string_field(data, "status")
        _validate_string_list(data.get("context"), "context")
        return

    if artifact_type == DECISION_CARD:
        _validate_string_field(data, "statement")
        _validate_string_field(data, "status")
        _validate_string_list(data.get("reason"), "reason")
        return

    if artifact_type == CONSTRAINT_CARD:
        _validate_string_field(data, "statement")
        _validate_string_list(data.get("reason"), "reason")
        return

    if artifact_type == PROCEDURE_CARD:
        _validate_string_field(data, "name")
        _validate_string_list(data.get("steps"), "steps")
        return

    if artifact_type == ISSUE_CARD:
        _validate_string_field(data, "question")
        _validate_string_field(data, "priority")


def _validate_reference_context(data: Mapping[str, object], artifact_type: str) -> None:
    if artifact_type != TASK_CARD:
        return

    context = data.get("context")
    if not isinstance(context, list):
        raise ValueError("context must be a list")
    for artifact_id in context:
        validate_artifact_id(artifact_id)


def _validate_string_field(data: Mapping[str, object], field_name: str) -> None:
    value = data.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")


def _validate_string_list(value: object, field_name: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")


__all__ = [
    "validate_artifact_id",
    "validate_artifact_schema",
]
