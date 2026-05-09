# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from dataclasses import dataclass
from typing import Iterable, Mapping

from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    PROCEDURE_CARD,
    TASK_CARD,
)
from core.validation import validate_artifact_schema


ACCEPT = "ACCEPT"
REJECT = "REJECT"
REWRITE = "REWRITE"
POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"

ALLOWED_VERDICTS = (
    ACCEPT,
    REJECT,
    REWRITE,
    POSSIBLE_DUPLICATE,
)

LOW_VALUE_PHRASES = (
    "maybe try",
    "i think this may work",
    "let's attempt",
    "lets attempt",
)

REJECTED_TRACE_PHRASES = (
    "intermediate reasoning",
    "reasoning trace",
    "scratchpad",
    "thinking aloud",
)

WEAK_PROCEDURE_STEPS = (
    "maybe try",
    "try it",
    "do it",
    "attempt it",
    "work on this",
)

MEANINGFUL_TEXT_FIELDS = {
    TASK_CARD: "goal",
    DECISION_CARD: "statement",
    CONSTRAINT_CARD: "statement",
    PROCEDURE_CARD: "name",
    ISSUE_CARD: "question",
}

SEMANTIC_TEXT_FIELDS = {
    TASK_CARD: ("goal",),
    DECISION_CARD: ("statement", "reason"),
    CONSTRAINT_CARD: ("statement", "reason"),
    PROCEDURE_CARD: ("name", "steps"),
    ISSUE_CARD: ("question",),
}


@dataclass(frozen=True)
class FilterResult:
    verdict: str
    reason: str


def filter_artifact_suggestion(
    artifact: Mapping[str, object],
    existing_artifacts: Iterable[Mapping[str, object]] = (),
) -> FilterResult:
    artifact_data = _coerce_artifact_mapping(artifact, "artifact")
    existing_data = _coerce_existing_artifacts(existing_artifacts)

    try:
        validate_artifact_schema(artifact_data)
    except ValueError as exc:
        return FilterResult(REJECT, str(exc))

    if _looks_like_reasoning_trace(artifact_data):
        return FilterResult(REJECT, "artifact looks like an intermediate reasoning trace")

    if not _has_meaningful_content(artifact_data):
        return FilterResult(REWRITE, "artifact content needs clarification")

    if _has_weak_phrasing(artifact_data):
        return FilterResult(REWRITE, "artifact is conceptually valid but weakly phrased")

    if _is_trivial_duplicate(artifact_data, existing_data):
        return FilterResult(POSSIBLE_DUPLICATE, "artifact may duplicate existing content")

    return FilterResult(ACCEPT, "artifact is suitable for draft persistence")


def _coerce_artifact_mapping(
    artifact: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    if not isinstance(artifact, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(artifact)


def _coerce_existing_artifacts(
    artifacts: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    existing_data: list[dict[str, object]] = []
    for index, artifact in enumerate(artifacts):
        existing_data.append(
            _coerce_artifact_mapping(artifact, f"existing artifact {index}")
        )
    return existing_data


def _has_meaningful_content(artifact: Mapping[str, object]) -> bool:
    artifact_type = artifact["type"]
    field_name = MEANINGFUL_TEXT_FIELDS[artifact_type]
    text_value = _normalize_text(artifact.get(field_name))
    if len(text_value) < 8:
        return False

    if artifact_type == PROCEDURE_CARD:
        return _has_meaningful_procedure_steps(artifact.get("steps"))

    return True


def _has_weak_phrasing(artifact: Mapping[str, object]) -> bool:
    text = _artifact_text_blob(artifact)
    if not text:
        return False
    for phrase in LOW_VALUE_PHRASES:
        if phrase in text:
            return True
    return False


def _looks_like_reasoning_trace(artifact: Mapping[str, object]) -> bool:
    text = _artifact_text_blob(artifact)
    if not text:
        return False
    for phrase in REJECTED_TRACE_PHRASES:
        if phrase in text:
            return True
    return False


def _artifact_text_blob(artifact: Mapping[str, object]) -> str:
    artifact_type = artifact.get("type")
    fields = SEMANTIC_TEXT_FIELDS.get(artifact_type, ())
    parts: list[str] = []
    for field_name in fields:
        value = artifact.get(field_name)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
    return " ".join(_normalize_text(part) for part in parts if part).strip()


def _is_trivial_duplicate(
    artifact: Mapping[str, object],
    existing_artifacts: list[dict[str, object]],
) -> bool:
    artifact_id = artifact["id"]
    signature = _artifact_signature(artifact)
    for existing_artifact in existing_artifacts:
        if existing_artifact.get("id") == artifact_id:
            return True
        if _artifact_signature(existing_artifact) == signature:
            return True
    return False


def _artifact_signature(artifact: Mapping[str, object]) -> tuple[object, ...]:
    artifact_type = artifact.get("type")
    if artifact_type == TASK_CARD:
        return artifact_type, _normalize_text(artifact.get("goal"))
    if artifact_type == DECISION_CARD:
        return artifact_type, _normalize_text(artifact.get("statement"))
    if artifact_type == CONSTRAINT_CARD:
        return artifact_type, _normalize_text(artifact.get("statement"))
    if artifact_type == ISSUE_CARD:
        return artifact_type, _normalize_text(artifact.get("question"))
    if artifact_type == PROCEDURE_CARD:
        return (
            artifact_type,
            _normalize_text(artifact.get("name")),
            tuple(_normalize_text(step) for step in _coerce_string_list(artifact.get("steps"))),
        )
    return (artifact_type, artifact.get("id"))


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    strings: list[str] = []
    for item in value:
        if isinstance(item, str):
            strings.append(item)
    return strings


def _has_meaningful_procedure_steps(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False

    normalized_steps = [_normalize_text(step) for step in value if isinstance(step, str)]
    if not normalized_steps:
        return False

    for step in normalized_steps:
        if len(step) < 4:
            continue
        if step in WEAK_PROCEDURE_STEPS:
            continue
        return True
    return False


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.strip().lower().split())
    return collapsed


__all__ = [
    "ACCEPT",
    "ALLOWED_VERDICTS",
    "FilterResult",
    "POSSIBLE_DUPLICATE",
    "REJECT",
    "REWRITE",
    "filter_artifact_suggestion",
]
