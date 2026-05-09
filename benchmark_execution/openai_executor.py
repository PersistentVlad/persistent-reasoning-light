# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
OpenAI-backed benchmark execution transport.

This module implements the provider-specific execution layer for OpenAI-backed
benchmark runs. It is transport-only:

- one prompt in
- one non-streaming Responses API call
- one contiguous raw string out

It does not implement benchmark logic, repository access, retries, or tool use.
"""

from __future__ import annotations

from openai import OpenAI

from benchmark_execution.base import (
    ExecutionConfig,
    ModelExecutor,
    validate_prompt,
    validate_raw_output,
    validate_timeout,
)


class OpenAIExecutor(ModelExecutor):
    """
    OpenAI-backed executor for benchmark prompt execution.

    The executor requires explicit configuration and an explicit API key.
    It performs exactly one non-streaming Responses API call per execute()
    invocation and returns exactly one validated raw string.
    """

    def __init__(
        self,
        *,
        config: ExecutionConfig,
        api_key: str,
    ) -> None:
        if not isinstance(config, ExecutionConfig):
            raise ValueError("config must be an ExecutionConfig instance")

        self._config = config
        validated_api_key = _validate_api_key(api_key)

        # Benchmark execution forbids implicit retries.
        self._client = OpenAI(
            api_key=validated_api_key,
            max_retries=0,
        )
        self._last_token_usage = {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    def execute(self, prompt: str, timeout_seconds: int) -> str:
        validated_prompt = validate_prompt(prompt)
        validated_timeout = validate_timeout(timeout_seconds)

        # Note:
        # Timeout behavior depends on the OpenAI SDK transport implementation.
        # The benchmark system still treats timeout as an explicit execution
        # boundary and expects timeout failures to surface as execution errors.
        response = self._client.responses.create(
            model=self._config.model,
            input=validated_prompt,
            max_output_tokens=self._config.max_output_tokens,
            tools=[],
            stream=False,
            timeout=validated_timeout,
        )
        self._last_token_usage = _extract_token_usage(response)

        raw_output = _extract_output_text(response)
        return validate_raw_output(
            raw_output,
            max_output_chars=self._config.max_output_chars,
        )

    @property
    def last_token_usage(self) -> dict[str, int | None]:
        return dict(self._last_token_usage)


def _validate_api_key(api_key: object) -> str:
    if not isinstance(api_key, str):
        raise ValueError("api_key must be a string")

    cleaned_api_key = api_key.strip()
    if not cleaned_api_key:
        raise ValueError("api_key must not be empty")
    if cleaned_api_key != api_key:
        raise ValueError("api_key must not contain surrounding whitespace")

    return cleaned_api_key


def _extract_output_text(response: object) -> str:
    if not hasattr(response, "output_text"):
        raise RuntimeError("OpenAI response is missing output_text")

    output_text = getattr(response, "output_text", None)

    if output_text is None:
        raise RuntimeError("OpenAI response does not contain output_text")

    if not isinstance(output_text, str):
        raise RuntimeError("OpenAI response output_text must be a string")

    return output_text


def _extract_token_usage(response: object) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "prompt_tokens": _extract_optional_int(usage, "input_tokens"),
        "output_tokens": _extract_optional_int(usage, "output_tokens"),
        "total_tokens": _extract_optional_int(usage, "total_tokens"),
    }


def _extract_optional_int(container: object, field_name: str) -> int | None:
    value = getattr(container, field_name, None)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


__all__ = ["OpenAIExecutor"]
