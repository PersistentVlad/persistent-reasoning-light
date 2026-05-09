# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Gemini-backed benchmark execution transport.

This module implements the provider-specific execution layer for Gemini-backed
benchmark runs. It is transport-only:
- one prompt in
- one non-streaming generate_content call
- one contiguous raw string out

It does not implement benchmark logic, repository access, retries, or tool use.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import errors, types

from benchmark_execution.base import (
    ExecutionConfig,
    ModelExecutor,
    validate_prompt,
    validate_raw_output,
    validate_timeout,
)


GEMINI_HTTP_RETRY_ATTEMPTS = 1
GEMINI_RETRYABLE_HTTP_STATUS_CODES = (429, 503)
GEMINI_RETRYABLE_PROVIDER_STATUSES = frozenset({"RESOURCE_EXHAUSTED", "UNAVAILABLE"})

logger = logging.getLogger(__name__)


class GeminiExecutor(ModelExecutor):
    """
    Gemini-backed executor for benchmark prompt execution.

    The executor requires explicit configuration and an explicit API key.
    It performs exactly one non-streaming generate_content call per execute()
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
        self._client = genai.Client(api_key=validated_api_key)
        self._last_token_usage = {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    # Gemini SDK retry handling is intentionally constrained to a single attempt.
    # Benchmark execution forbids implicit retries.
    # timeout=validated_timeout * 1000 in milliseconds (ms)

    def execute(self, prompt: str, timeout_seconds: int) -> str:
        validated_prompt = validate_prompt(prompt)
        validated_timeout = validate_timeout(timeout_seconds)

        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=validated_prompt,
                config=types.GenerateContentConfig(
                    candidate_count=1,
                    max_output_tokens=self._config.max_output_tokens,
                    tools=[],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                    http_options=types.HttpOptions(
                        timeout=validated_timeout * 1000,
                        retry_options=_build_http_retry_options(),
                    ),
                ),
            )
        except errors.APIError as exc:
            classification = _classify_provider_error(exc)
            _log_provider_error_warning(classification)
            if classification["retryable"]:
                raise RuntimeError(
                    f"retrying after {_describe_retryable_provider_error(exc)} under Gemini provider retry policy failed after {GEMINI_HTTP_RETRY_ATTEMPTS} retry attempt(s): {exc}"
                ) from exc
            raise

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
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, list):
        raise RuntimeError("Gemini response candidates must be a list")
    if len(candidates) != 1:
        raise RuntimeError(
            f"Gemini response must contain exactly one candidate, got {len(candidates)}"
        )

    candidate = candidates[0]
    content = getattr(candidate, "content", None)
    if content is None:
        raise RuntimeError("Gemini response candidate is missing content")

    parts = getattr(content, "parts", None)
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Gemini response candidate content must contain parts")

    text_parts: list[str] = []
    for part in parts:
        if part is None:
            raise RuntimeError("Gemini response contains a null part")

        non_text_fields = _collect_non_text_part_fields(part)
        if non_text_fields:
            joined = ", ".join(non_text_fields)
            raise RuntimeError(
                f"Gemini response contains non-text part fields: {joined}"
            )

        text = getattr(part, "text", None)
        if not isinstance(text, str):
            raise RuntimeError("Gemini response text part must be a string")

        thought = getattr(part, "thought", None)
        if isinstance(thought, bool) and thought:
            raise RuntimeError("Gemini response contains thought-only text content")

        text_parts.append(text)

    return "".join(text_parts)


def _extract_token_usage(response: object) -> dict[str, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "prompt_tokens": _extract_optional_int(usage, "prompt_token_count"),
        "output_tokens": _extract_optional_int(usage, "candidates_token_count"),
        "total_tokens": _extract_optional_int(usage, "total_token_count"),
    }


def _extract_optional_int(container: object, field_name: str) -> int | None:
    value = getattr(container, field_name, None)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _build_http_retry_options() -> types.HttpRetryOptions:
    return types.HttpRetryOptions(
        attempts=GEMINI_HTTP_RETRY_ATTEMPTS,
        http_status_codes=list(GEMINI_RETRYABLE_HTTP_STATUS_CODES),
    )


def _is_retryable_provider_error(error: object) -> bool:
    return bool(_classify_provider_error(error)["retryable"])


def _describe_retryable_provider_error(error: errors.APIError) -> str:
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)

    if isinstance(code, int) and isinstance(status, str) and status.strip():
        return f"{code} {status.strip().upper()}"
    if isinstance(code, int):
        return str(code)
    if isinstance(status, str) and status.strip():
        return status.strip().upper()
    return "provider error"


def _is_deadline_exceeded_provider_error(error: object) -> bool:
    return _classify_provider_error(error)["type"] == "deadline_exceeded"


def _classify_provider_error(error: object) -> dict[str, object]:
    if not isinstance(error, errors.APIError):
        return {
            "type": "other",
            "retryable": False,
        }

    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    normalized_status = status.strip().upper() if isinstance(status, str) else None
    message = getattr(error, "message", None)
    normalized_message = message.lower() if isinstance(message, str) else str(error).lower()

    if code == 429 or normalized_status == "RESOURCE_EXHAUSTED":
        return {
            "type": "rate_limit",
            "retryable": True,
        }

    if code == 503 or normalized_status == "UNAVAILABLE":
        return {
            "type": "unavailable",
            "retryable": True,
        }

    if (
        code == 504
        or normalized_status == "DEADLINE_EXCEEDED"
        or "deadline expired" in normalized_message
    ):
        return {
            "type": "deadline_exceeded",
            "retryable": False,
        }

    return {
        "type": "other",
        "retryable": False,
    }


def _log_provider_error_warning(classification: dict[str, object]) -> None:
    error_type = classification.get("type")

    if error_type == "rate_limit":
        logger.warning(
            "Gemini request rate-limited (429 RESOURCE_EXHAUSTED). Retrying with backoff."
        )
        return

    if error_type == "unavailable":
        logger.warning(
            "Gemini service unavailable (503 UNAVAILABLE). Retrying. Possible temporary overload."
        )
        return

    if error_type == "deadline_exceeded":
        logger.warning(
            "Gemini request exceeded timeout_seconds (504 DEADLINE_EXCEEDED). "
            "This may indicate: scenario complexity is too high; timeout_seconds is too low; temporary provider latency spike. "
            "Consider increasing timeout_seconds or simplifying the scenario."
        )


def _collect_non_text_part_fields(part: object) -> list[str]:
    non_text_field_names = (
        "code_execution_result",
        "executable_code",
        "file_data",
        "function_call",
        "function_response",
        "inline_data",
        "media_resolution",
        "part_metadata",
        "tool_call",
        "tool_response",
        "video_metadata",
    )

    present_fields = [
        field_name
        for field_name in non_text_field_names
        if getattr(part, field_name, None) is not None
    ]
    return sorted(present_fields)


__all__ = ["GeminiExecutor"]
