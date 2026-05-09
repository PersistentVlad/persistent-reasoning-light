# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Base execution interfaces for benchmark-backed model invocation.

This module defines the provider-agnostic execution contract used by the
benchmark runtime layer.

Key principles:
- one prompt in
- one contiguous raw string out
- no retries
- no streaming
- explicit timeout (handled by caller / adapter)
- explicit output limits

Provider-specific executors (for example OpenAI or Gemini) must implement this
contract without redefining benchmark system invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


DEFAULT_MAX_OUTPUT_CHARS = 20_000
DEFAULT_MAX_OUTPUT_TOKENS = 2_000


@dataclass(frozen=True)
class ExecutionConfig:
    """
    Provider-agnostic execution settings for benchmark model invocation.
    """

    model: str
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.model, str):
            raise ValueError("model must be a string")

        cleaned_model = self.model.strip()
        if not cleaned_model:
            raise ValueError("model must not be empty")
        if cleaned_model != self.model:
            raise ValueError("model must not contain surrounding whitespace")

        if not isinstance(self.max_output_chars, int) or self.max_output_chars <= 0:
            raise ValueError("max_output_chars must be a positive integer")

        if not isinstance(self.max_output_tokens, int) or self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")


@runtime_checkable
class ModelExecutor(Protocol):
    """
    Provider-agnostic benchmark execution interface.

    Implementations must:
    - accept exactly one prompt string
    - enforce timeout explicitly (outside or inside implementation)
    - return exactly one contiguous raw string
    - avoid retries, streaming, and hidden side effects
    """

    def execute(self, prompt: str, timeout_seconds: int) -> str:
        """
        Execute one benchmark prompt and return one raw textual response.
        """
        ...


def validate_prompt(prompt: object) -> str:
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")

    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("prompt must not be empty")

    return cleaned


def validate_timeout(timeout_seconds: object) -> int:
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise ValueError("timeout_seconds must be an integer")

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be a positive integer")

    return timeout_seconds


def validate_raw_output(
    output: object,
    *,
    max_output_chars: int,
) -> str:
    if not isinstance(max_output_chars, int) or max_output_chars <= 0:
        raise ValueError("max_output_chars must be a positive integer")

    if not isinstance(output, str):
        raise RuntimeError("executor output must be a string")

    if not output.strip():
        raise RuntimeError("executor output must not be empty or whitespace-only")

    if len(output) > max_output_chars:
        raise RuntimeError(
            f"executor output exceeds max_output_chars: {len(output)} > {max_output_chars}"
        )

    return output


__all__ = [
    "DEFAULT_MAX_OUTPUT_CHARS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "ExecutionConfig",
    "ModelExecutor",
    "validate_prompt",
    "validate_raw_output",
    "validate_timeout",
]