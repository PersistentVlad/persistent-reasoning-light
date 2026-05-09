# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from collections.abc import Mapping, Sequence

from reasoning_adapters.common.context_utils import (
    build_context_sections,
    format_working_context_text,
    normalize_working_context,
)


def build_context_prompt_block(
    context: Mapping[str, object],
    *,
    title: str = "Persistent Reasoning Light Context",
) -> str:
    """
    Build a compact prompt block from a normalized PR-Light working context.

    The block preserves reference-only semantics and does not embed artifact bodies.
    """
    return format_working_context_text(context, header=title)


def build_instruction_block(
    instructions: Sequence[str],
    *,
    title: str = "Instructions",
) -> str:
    """
    Build a deterministic instruction block.

    Empty instructions are rejected.
    Blank lines are removed.
    """
    normalized = _normalize_string_sequence(instructions, "instructions")
    if not normalized:
        raise ValueError("instructions must not be empty")

    lines = [title]
    for instruction in normalized:
        lines.append(f"- {instruction}")
    return "\n".join(lines)


def build_reference_block(
    references: Sequence[str],
    *,
    title: str = "References",
) -> str:
    """
    Build a reference block from artifact IDs or other compact references.

    This helper preserves input order and does not reorder references.
    """
    normalized = _normalize_string_sequence(references, "references")
    lines = [title]
    if not normalized:
        lines.append("- none")
        return "\n".join(lines)

    for reference in normalized:
        lines.append(f"- {reference}")
    return "\n".join(lines)


def build_agent_prompt(
    context: Mapping[str, object],
    *,
    task_text: str,
    instructions: Sequence[str] = (),
    extra_references: Sequence[str] = (),
    title: str = "Persistent Reasoning Light Prompt",
) -> str:
    """
    Assemble a compact, deterministic agent-facing prompt.

    Structure:
    - title
    - task
    - context
    - optional instructions
    - optional references
    """
    task = _normalize_required_text(task_text, "task_text")
    normalized_context = normalize_working_context(context)

    blocks: list[str] = [
        title,
        "",
        "Task:",
        task,
        "",
        build_context_prompt_block(normalized_context),
    ]

    if instructions:
        blocks.extend(
            [
                "",
                build_instruction_block(instructions),
            ]
        )

    if extra_references:
        blocks.extend(
            [
                "",
                build_reference_block(extra_references),
            ]
        )

    return "\n".join(blocks)


def build_context_payload(
    context: Mapping[str, object],
) -> dict[str, object]:
    """
    Return a deterministic agent-safe context payload.

    This helper preserves the minimal reference-only representation.
    """
    normalized = normalize_working_context(context)
    return {
        "active_task": normalized["active_task"],
        "constraints": list(normalized["constraints"]),
        "decisions": list(normalized["decisions"]),
        "open_issues": list(normalized["open_issues"]),
    }


def build_prompt_sections(
    context: Mapping[str, object],
    *,
    task_text: str,
    instructions: Sequence[str] = (),
) -> list[tuple[str, list[str]]]:
    """
    Build structured prompt sections for adapters that do not use flat text prompts.

    Returns deterministic sections:
    - ("task", [...])
    - ("active_task", [...])
    - ("decisions", [...])
    - ("constraints", [...])
    - ("open_issues", [...])
    - optionally ("instructions", [...])
    """
    task = _normalize_required_text(task_text, "task_text")
    normalized_context = normalize_working_context(context)
    context_sections = build_context_sections(normalized_context, include_empty=True)

    sections: list[tuple[str, list[str]]] = [("task", [task])]
    sections.extend(context_sections)

    normalized_instructions = _normalize_string_sequence(instructions, "instructions")
    if normalized_instructions:
        sections.append(("instructions", normalized_instructions))

    return sections


def _normalize_string_sequence(value: object, field_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = item.strip()
        if cleaned:
            normalized.append(cleaned)

    return normalized


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


__all__ = [
    "build_agent_prompt",
    "build_context_payload",
    "build_context_prompt_block",
    "build_instruction_block",
    "build_prompt_sections",
    "build_reference_block",
]