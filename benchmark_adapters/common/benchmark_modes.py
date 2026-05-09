# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark mode definitions for Persistent Reasoning Light.

This module defines the supported execution modes and their semantic behavior.
"""

from __future__ import annotations

from typing import Final


BASELINE: Final[str] = "baseline"
PR_EPHEMERAL: Final[str] = "pr_ephemeral"
PR_LIGHT_BRAIN: Final[str] = "pr_light_brain"
PR_LIGHT: Final[str] = PR_EPHEMERAL

SUPPORTED_BENCHMARK_MODES: Final[tuple[str, ...]] = (
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)


def is_supported_benchmark_mode(mode: str) -> bool:
    return mode in SUPPORTED_BENCHMARK_MODES


def validate_benchmark_mode(mode: str) -> str:
    if not is_supported_benchmark_mode(mode):
        supported = ", ".join(SUPPORTED_BENCHMARK_MODES)
        raise ValueError(
            f"unsupported benchmark mode: '{mode}'. Supported modes: {supported}"
        )
    return mode


def uses_pr_runtime(mode: str) -> bool:
    """
    Returns True if the mode enables PR-Light runtime behavior.
    """
    validated_mode = validate_benchmark_mode(mode)
    return validated_mode in (PR_EPHEMERAL, PR_LIGHT_BRAIN)


def uses_seeded_reasoning_brain(mode: str) -> bool:
    """
    Returns True if the mode uses the seeded benchmark reasoning brain.
    """
    validated_mode = validate_benchmark_mode(mode)
    return validated_mode == PR_LIGHT_BRAIN


def uses_empty_reasoning_brain(mode: str) -> bool:
    """
    Returns True if the mode uses the empty benchmark reasoning brain.
    """
    validated_mode = validate_benchmark_mode(mode)
    return validated_mode == PR_EPHEMERAL


def is_pr_ephemeral_mode(mode: str) -> bool:
    validated_mode = validate_benchmark_mode(mode)
    return validated_mode == PR_EPHEMERAL


__all__ = [
    "BASELINE",
    "PR_EPHEMERAL",
    "PR_LIGHT",
    "PR_LIGHT_BRAIN",
    "SUPPORTED_BENCHMARK_MODES",
    "is_pr_ephemeral_mode",
    "is_supported_benchmark_mode",
    "validate_benchmark_mode",
    "uses_pr_runtime",
    "uses_seeded_reasoning_brain",
    "uses_empty_reasoning_brain",
]
