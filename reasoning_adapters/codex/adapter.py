# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from reasoning_adapters.common.artifact_utils import build_artifact_payload
from reasoning_adapters.common.prompt_utils import build_agent_prompt
from core.context_loader import resolve_working_context
from core.storage import save_runtime_artifact


DEFAULT_PROMPT_TITLE = "Persistent Reasoning Light - Codex Context"
DEFAULT_INBOX_AREA = "inbox"


def load_context(brain_root: Path | str) -> dict[str, object]:
    """
    Load the prepared PR-Light working context for Codex.

    The returned structure remains compact and reference-based.
    """
    return resolve_working_context(brain_root)


def build_agent_input_from_context(
    context: Mapping[str, object],
    *,
    task_text: str,
    instructions: Sequence[str] = (),
    extra_references: Sequence[str] = (),
    title: str = DEFAULT_PROMPT_TITLE,
) -> str:
    """
    Build a deterministic Codex-facing prompt from an already loaded PR-Light context.
    """
    task = _normalize_required_text(task_text, "task_text")
    return build_agent_prompt(
        context,
        task_text=task,
        instructions=instructions,
        extra_references=extra_references,
        title=title,
    )


def build_agent_input(
    brain_root: Path | str,
    *,
    task_text: str,
    instructions: Sequence[str] = (),
    extra_references: Sequence[str] = (),
    title: str = DEFAULT_PROMPT_TITLE,
) -> str:
    """
    Build a deterministic Codex-facing prompt from prepared PR-Light context.
    """
    context = load_context(brain_root)
    return build_agent_input_from_context(
        context,
        task_text=task_text,
        instructions=instructions,
        extra_references=extra_references,
        title=title,
    )


def extract_artifact_suggestion(
    agent_output: Mapping[str, object] | str,
) -> dict[str, object]:
    """
    Extract and validate a candidate artifact suggestion from Codex output.

    Supported inputs:
    - mapping
    - JSON object string

    If a string is provided, it must contain a single top-level JSON object
    and no surrounding explanatory text.
    """
    if isinstance(agent_output, Mapping):
        return build_artifact_payload(agent_output)

    if not isinstance(agent_output, str):
        raise ValueError("agent_output must be a mapping or JSON string")

    raw_text = agent_output.strip()
    if not raw_text:
        raise ValueError("agent_output must not be empty")

    try:
        raw_value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("agent_output must be valid JSON") from exc

    if not isinstance(raw_value, Mapping):
        raise ValueError("agent_output JSON must be an object")

    return build_artifact_payload(raw_value)


def submit_suggestion(
    brain_root: Path | str,
    artifact_suggestion: Mapping[str, object] | str,
) -> Path:
    """
    Submit a candidate artifact suggestion into the approved proposal flow.

    The adapter writes only to runtime/inbox and does not bypass the proposal path.
    """
    artifact_payload = extract_artifact_suggestion(artifact_suggestion)
    return save_runtime_artifact(brain_root, DEFAULT_INBOX_AREA, artifact_payload)


def build_submission_payload(
    brain_root: Path | str,
    *,
    task_text: str,
    instructions: Sequence[str] = (),
    extra_references: Sequence[str] = (),
    title: str = DEFAULT_PROMPT_TITLE,
) -> dict[str, object]:
    """
    Build a structured Codex adapter payload.

    This helper is useful for callers that prefer a structured payload over
    a flat prompt string.
    """
    task = _normalize_required_text(task_text, "task_text")
    context = load_context(brain_root)
    prompt = build_agent_input_from_context(
        context,
        task_text=task,
        instructions=instructions,
        extra_references=extra_references,
        title=title,
    )
    return {
        "task": task,
        "context": context,
        "prompt": prompt,
    }


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


__all__ = [
    "DEFAULT_INBOX_AREA",
    "DEFAULT_PROMPT_TITLE",
    "build_agent_input",
    "build_agent_input_from_context",
    "build_submission_payload",
    "extract_artifact_suggestion",
    "load_context",
    "submit_suggestion",
]
