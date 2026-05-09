# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from collections.abc import Mapping, Sequence
from typing import Final


WORKING_CONTEXT_FIELDS: Final[tuple[str, ...]] = (
    "active_task",
    "constraints",
    "decisions",
    "open_issues",
)


def normalize_working_context(
    context: Mapping[str, object],
) -> dict[str, object]:
    """
    Normalize a PR-Light working context into a deterministic, reference-only shape.

    Expected input fields:
    - active_task: str | None
    - constraints: list[str]
    - decisions: list[str]
    - open_issues: list[str]

    Output preserves the same schema and sorts list fields lexicographically.
    """
    if not isinstance(context, Mapping):
        raise ValueError("working context must be a mapping")

    unexpected_fields = sorted(field for field in context if field not in WORKING_CONTEXT_FIELDS)
    if unexpected_fields:
        fields = ", ".join(unexpected_fields)
        raise ValueError(f"unexpected working context fields: {fields}")

    missing_fields = [field for field in WORKING_CONTEXT_FIELDS if field not in context]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ValueError(f"missing working context fields: {fields}")

    active_task = _normalize_optional_reference(context["active_task"], "active_task")
    constraints = _normalize_reference_list(context["constraints"], "constraints")
    decisions = _normalize_reference_list(context["decisions"], "decisions")
    open_issues = _normalize_reference_list(context["open_issues"], "open_issues")

    return {
        "active_task": active_task,
        "constraints": constraints,
        "decisions": decisions,
        "open_issues": open_issues,
    }


def build_context_sections(
    context: Mapping[str, object],
    *,
    include_empty: bool = True,
) -> list[tuple[str, list[str]]]:
    """
    Convert a working context into deterministic display sections.

    Returns a list of:
    - ("active_task", [...])
    - ("decisions", [...])
    - ("constraints", [...])
    - ("open_issues", [...])

    Sections are returned in fixed order.
    """
    normalized = normalize_working_context(context)

    sections: list[tuple[str, list[str]]] = []

    active_task = normalized["active_task"]
    active_task_lines = [active_task] if isinstance(active_task, str) else []
    if include_empty or active_task_lines:
        sections.append(("active_task", active_task_lines))

    for field in ("decisions", "constraints", "open_issues"):
        values = normalized[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list after normalization")
        if include_empty or values:
            sections.append((field, list(values)))

    return sections


def format_working_context_text(
    context: Mapping[str, object],
    *,
    header: str | None = "Working Context",
) -> str:
    """
    Render a deterministic human-readable text block from a working context.

    This helper is agent-agnostic and intentionally compact.
    It preserves IDs/references only and does not expand artifact bodies.
    """
    sections = build_context_sections(context, include_empty=True)

    lines: list[str] = []
    if header:
        lines.append(header)

    for section_name, values in sections:
        title = _humanize_section_name(section_name)
        lines.append(f"{title}:")
        if not values:
            lines.append("- none")
            continue
        for value in values:
            lines.append(f"- {value}")

    return "\n".join(lines)


def flatten_context_references(context: Mapping[str, object]) -> list[str]:
    """
    Return all referenced artifact IDs from the working context in deterministic order.

    Order:
    1. active_task (if present)
    2. decisions
    3. constraints
    4. open_issues
    """
    normalized = normalize_working_context(context)

    references: list[str] = []

    active_task = normalized["active_task"]
    if isinstance(active_task, str):
        references.append(active_task)

    for field in ("decisions", "constraints", "open_issues"):
        values = normalized[field]
        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list after normalization")
        references.extend(values)

    return references


def truncate_reference_list(
    references: Sequence[str],
    *,
    max_items: int,
) -> list[str]:
    """
    Truncate an already ordered list of references without mutation.

    This helper preserves input order.
    """
    if not isinstance(max_items, int) or max_items < 0:
        raise ValueError("max_items must be a non-negative integer")

    if not isinstance(references, Sequence) or isinstance(references, (str, bytes, bytearray)):
        raise ValueError("references must be a sequence of strings")

    validated: list[str] = []
    for item in references:
        if not isinstance(item, str):
            raise ValueError("references must contain only strings")
        cleaned = item.strip()
        if not cleaned:
            raise ValueError("references must not contain empty strings")
        validated.append(cleaned)

    return list(validated[:max_items])


def _normalize_optional_reference(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_reference_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized_values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = item.strip()
        if not cleaned:
            raise ValueError(f"{field_name} must not contain empty strings")
        normalized_values.append(cleaned)

    if len(set(normalized_values)) != len(normalized_values):
        raise ValueError(f"{field_name} must not contain duplicate references")

    return sorted(normalized_values)


def _humanize_section_name(section_name: str) -> str:
    return section_name.replace("_", " ").title()


__all__ = [
    "WORKING_CONTEXT_FIELDS",
    "build_context_sections",
    "flatten_context_references",
    "format_working_context_text",
    "normalize_working_context",
    "truncate_reference_list",
]