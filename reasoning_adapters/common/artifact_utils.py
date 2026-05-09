# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from collections.abc import Mapping, Sequence

from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    PROCEDURE_CARD,
    SUPPORTED_ARTIFACT_TYPES,
    TASK_CARD,
)
from core.validation import validate_artifact_schema


ARTIFACT_TEXT_FIELDS = {
    TASK_CARD: ("goal",),
    DECISION_CARD: ("statement", "reason"),
    CONSTRAINT_CARD: ("statement", "reason"),
    PROCEDURE_CARD: ("name", "steps"),
    ISSUE_CARD: ("question",),
}

ARTIFACT_PRIMARY_FIELD = {
    TASK_CARD: "goal",
    DECISION_CARD: "statement",
    CONSTRAINT_CARD: "statement",
    PROCEDURE_CARD: "name",
    ISSUE_CARD: "question",
}


def validate_artifact_suggestion(
    artifact: Mapping[str, object],
) -> dict[str, object]:
    """
    Validate and copy an artifact suggestion into a deterministic mapping.

    This helper is intended for adapter-side shaping only.
    It preserves the approved artifact schema and does not write to storage.
    """
    if not isinstance(artifact, Mapping):
        raise ValueError("artifact must be a mapping")

    validated = dict(artifact)
    validate_artifact_schema(validated)
    return validated


def build_artifact_payload(
    artifact: Mapping[str, object],
) -> dict[str, object]:
    """
    Return a validated artifact payload suitable for runtime handoff.
    """
    validated = validate_artifact_suggestion(artifact)
    return dict(validated)


def summarize_artifact_suggestion(
    artifact: Mapping[str, object],
) -> str:
    """
    Build a compact human-readable summary of an artifact suggestion.

    Output remains reference-light and deterministic.
    """
    validated = validate_artifact_suggestion(artifact)
    artifact_type = validated["type"]
    primary_field = ARTIFACT_PRIMARY_FIELD[artifact_type]
    primary_value = _extract_primary_text(validated, primary_field)

    return f"{artifact_type}({validated['id']}): {primary_value}"


def build_artifact_prompt_block(
    artifact: Mapping[str, object],
    *,
    title: str = "Artifact Suggestion",
) -> str:
    """
    Render a deterministic artifact suggestion block for agent-facing prompts.
    """
    validated = validate_artifact_suggestion(artifact)

    lines = [title]
    lines.append(f"- id: {validated['id']}")
    lines.append(f"- type: {validated['type']}")
    lines.append(f"- domains: {', '.join(_coerce_string_list(validated.get('domains'), 'domains'))}")

    for field_name in _get_semantic_fields(validated["type"]):
        value = validated.get(field_name)
        lines.extend(_format_field_lines(field_name, value))

    return "\n".join(lines)


def extract_artifact_signature(
    artifact: Mapping[str, object],
) -> tuple[object, ...]:
    """
    Build a deterministic signature suitable for lightweight duplicate checks.
    """
    validated = validate_artifact_suggestion(artifact)
    artifact_type = validated["type"]

    if artifact_type == TASK_CARD:
        return artifact_type, _normalize_text(validated.get("goal"))

    if artifact_type == DECISION_CARD:
        return artifact_type, _normalize_text(validated.get("statement"))

    if artifact_type == CONSTRAINT_CARD:
        return artifact_type, _normalize_text(validated.get("statement"))

    if artifact_type == ISSUE_CARD:
        return artifact_type, _normalize_text(validated.get("question"))

    if artifact_type == PROCEDURE_CARD:
        return (
            artifact_type,
            _normalize_text(validated.get("name")),
            tuple(
                _normalize_text(step)
                for step in _coerce_string_list(validated.get("steps"), "steps")
            ),
        )

    raise ValueError(f"unsupported artifact type: {artifact_type}")


def collect_artifact_references(
    artifact: Mapping[str, object],
) -> list[str]:
    """
    Collect artifact references from an artifact suggestion while preserving input order.

    Currently only TaskCard.context is treated as a reference-bearing field.
    """
    validated = validate_artifact_suggestion(artifact)
    artifact_type = validated["type"]

    if artifact_type != TASK_CARD:
        return []

    references = _coerce_string_list(validated.get("context"), "context")
    return references


def build_artifact_payload_list(
    artifacts: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """
    Validate and copy a sequence of artifact suggestions while preserving input order.
    """
    if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes, bytearray)):
        raise ValueError("artifacts must be a sequence of mappings")

    payloads: list[dict[str, object]] = []
    for artifact in artifacts:
        payloads.append(build_artifact_payload(artifact))
    return payloads


def _get_semantic_fields(artifact_type: str) -> tuple[str, ...]:
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ValueError(f"unsupported artifact type: {artifact_type}")
    return ARTIFACT_TEXT_FIELDS[artifact_type]


def _extract_primary_text(
    artifact: Mapping[str, object],
    field_name: str,
) -> str:
    value = artifact.get(field_name)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} must not be empty")
        return text

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        normalized = _coerce_string_list(value, field_name)
        if not normalized:
            raise ValueError(f"{field_name} must not be empty")
        return "; ".join(normalized)

    raise ValueError(f"{field_name} must be a string or sequence of strings")


def _format_field_lines(
    field_name: str,
    value: object,
) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field_name} must not be empty")
        return [f"- {field_name}: {cleaned}"]

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        lines = [f"- {field_name}:"]
        normalized = _coerce_string_list(value, field_name)
        if not normalized:
            lines.append("  - none")
            return lines
        for item in normalized:
            lines.append(f"  - {item}")
        return lines

    if value is None:
        return [f"- {field_name}: none"]

    raise ValueError(f"{field_name} must be a string, sequence, or null")


def _coerce_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of strings")

    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = item.strip()
        if not cleaned:
            raise ValueError(f"{field_name} must not contain empty strings")
        strings.append(cleaned)
    return strings


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


__all__ = [
    "ARTIFACT_PRIMARY_FIELD",
    "ARTIFACT_TEXT_FIELDS",
    "build_artifact_payload",
    "build_artifact_payload_list",
    "build_artifact_prompt_block",
    "collect_artifact_references",
    "extract_artifact_signature",
    "summarize_artifact_suggestion",
    "validate_artifact_suggestion",
]