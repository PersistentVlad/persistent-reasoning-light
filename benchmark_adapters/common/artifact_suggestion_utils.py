# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark artifact suggestion parsing helpers.

The prompt-facing benchmark shape is compact and storage-facing:
- legacy: {"id": "...", "type": "decision", "summary": "..."}
- v2: {"TaskCard": "NONE" | {"id": "...", "summary": "..."}, ...}

Filter integration may normalize these candidates into core Card schemas, but
the artifact_candidate payload remains compact for event/storage compatibility.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Final


TASK_CARD: Final[str] = "TaskCard"
DECISION_CARD: Final[str] = "DecisionCard"
CONSTRAINT_CARD: Final[str] = "ConstraintCard"
PROCEDURE_CARD: Final[str] = "ProcedureCard"

ARTIFACT_CARD_TYPES: Final[tuple[str, ...]] = (
    TASK_CARD,
    DECISION_CARD,
    CONSTRAINT_CARD,
    PROCEDURE_CARD,
)

CARD_TO_BENCHMARK_TYPE: Final[dict[str, str]] = {
    TASK_CARD: "task",
    DECISION_CARD: "decision",
    CONSTRAINT_CARD: "constraint",
    PROCEDURE_CARD: "procedure",
}

BENCHMARK_TYPE_TO_CARD: Final[dict[str, str]] = {
    value: key for key, value in CARD_TO_BENCHMARK_TYPE.items()
}

NONE_VALUE: Final[str] = "NONE"
ARTIFACT_PARSE_MISSING: Final[str] = "missing"
ARTIFACT_PARSE_NONE: Final[str] = "none"
ARTIFACT_PARSE_MALFORMED: Final[str] = "malformed"
ARTIFACT_PARSE_VALID: Final[str] = "valid"

REJECTED_TRACE_FRAGMENTS: Final[tuple[str, ...]] = (
    "reasoning trace",
    "intermediate reasoning",
    "scratchpad",
    "thinking aloud",
)


def parse_benchmark_artifact_suggestions(payload: str) -> list[dict[str, object]]:
    if not isinstance(payload, str):
        raise ValueError("artifact suggestion payload must be a string")
    cleaned_payload = payload.strip()
    if not cleaned_payload:
        raise ValueError("artifact suggestion payload must not be empty")
    if "```" in cleaned_payload:
        raise ValueError("artifact suggestion must not contain markdown fences")

    try:
        decoded = json.loads(cleaned_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("artifact suggestion must be valid JSON") from exc

    if not isinstance(decoded, Mapping):
        raise ValueError("artifact suggestion JSON must be an object")

    if _is_legacy_decision_shape(decoded):
        return [_validate_legacy_decision_suggestion(decoded)]

    return _parse_multi_type_suggestion(decoded)


def build_artifact_generation_telemetry(
    parser_outcome: str,
    suggestions: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    proposed_count = len(suggestions) if parser_outcome == ARTIFACT_PARSE_VALID else 0
    per_type = {
        card_type: {
            "parser_outcome": ARTIFACT_PARSE_NONE,
            "artifact_proposed_count": 0,
            "none_output_count": 1,
            "malformed_output_count": 0,
        }
        for card_type in ARTIFACT_CARD_TYPES
    }

    if parser_outcome == ARTIFACT_PARSE_VALID:
        for suggestion in suggestions:
            card_type = BENCHMARK_TYPE_TO_CARD.get(str(suggestion.get("type")))
            if card_type in per_type:
                per_type[card_type] = {
                    "parser_outcome": ARTIFACT_PARSE_VALID,
                    "artifact_proposed_count": 1,
                    "none_output_count": 0,
                    "malformed_output_count": 0,
                }
    elif parser_outcome == ARTIFACT_PARSE_MALFORMED:
        per_type = {
            card_type: {
                "parser_outcome": ARTIFACT_PARSE_MALFORMED,
                "artifact_proposed_count": 0,
                "none_output_count": 0,
                "malformed_output_count": 1,
            }
            for card_type in ARTIFACT_CARD_TYPES
        }

    return {
        "parser_outcome": parser_outcome,
        "artifact_proposed_count": proposed_count,
        "none_output_count": 1 if parser_outcome == ARTIFACT_PARSE_NONE else 0,
        "malformed_output_count": 1 if parser_outcome == ARTIFACT_PARSE_MALFORMED else 0,
        "per_type": per_type,
    }


def _is_legacy_decision_shape(value: Mapping[str, object]) -> bool:
    return set(value.keys()) == {"id", "type", "summary"}


def _validate_legacy_decision_suggestion(
    suggestion: Mapping[str, object],
) -> dict[str, object]:
    artifact_id = _normalize_required_text(suggestion.get("id"), "artifact id")
    artifact_type = _normalize_required_text(suggestion.get("type"), "artifact type")
    summary = _normalize_summary(suggestion.get("summary"), "summary")

    if artifact_type != "decision":
        raise ValueError("legacy benchmark suggestion must be a decision")
    _reject_reasoning_trace(summary)

    return {
        "id": artifact_id,
        "type": artifact_type,
        "summary": summary,
    }


def _parse_multi_type_suggestion(
    suggestion: Mapping[str, object],
) -> list[dict[str, object]]:
    if set(suggestion.keys()) != set(ARTIFACT_CARD_TYPES):
        unexpected = sorted(set(suggestion.keys()) - set(ARTIFACT_CARD_TYPES))
        missing = sorted(set(ARTIFACT_CARD_TYPES) - set(suggestion.keys()))
        details = []
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        if missing:
            details.append("missing: " + ", ".join(missing))
        raise ValueError("multi-type artifact suggestion shape invalid" + (": " + "; ".join(details) if details else ""))

    candidates: list[dict[str, object]] = []
    seen_types: set[str] = set()
    for card_type in ARTIFACT_CARD_TYPES:
        value = suggestion[card_type]
        if isinstance(value, str) and value == NONE_VALUE:
            continue
        if isinstance(value, str):
            raise ValueError(f"{card_type} must be NONE or an object")
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            raise ValueError(f"{card_type} must contain at most one artifact")
        if not isinstance(value, Mapping):
            raise ValueError(f"{card_type} must be NONE or an object")

        benchmark_type = CARD_TO_BENCHMARK_TYPE[card_type]
        if benchmark_type in seen_types:
            raise ValueError(f"duplicate artifact type: {card_type}")
        seen_types.add(benchmark_type)
        candidates.append(_validate_multi_type_card(card_type, value))

    return candidates


def _validate_multi_type_card(
    card_type: str,
    value: Mapping[str, object],
) -> dict[str, object]:
    expected_fields = {"id", "summary"}
    unexpected = sorted(set(value.keys()) - expected_fields)
    missing = sorted(expected_fields - set(value.keys()))
    if unexpected:
        raise ValueError(f"{card_type} has unexpected fields: " + ", ".join(unexpected))
    if missing:
        raise ValueError(f"{card_type} is missing fields: " + ", ".join(missing))

    artifact_id = _normalize_required_text(value.get("id"), f"{card_type}.id")
    summary = _normalize_summary(value.get("summary"), f"{card_type}.summary")
    _reject_reasoning_trace(summary)
    return {
        "id": artifact_id,
        "type": CARD_TO_BENCHMARK_TYPE[card_type],
        "summary": summary,
    }


def _normalize_summary(value: object, field_name: str) -> str:
    summary = _normalize_required_text(value, field_name)
    return " ".join(summary.split())


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _reject_reasoning_trace(summary: str) -> None:
    normalized = summary.lower()
    for fragment in REJECTED_TRACE_FRAGMENTS:
        if fragment in normalized:
            raise ValueError("artifact summary must not contain reasoning traces")


__all__ = [
    "ARTIFACT_CARD_TYPES",
    "ARTIFACT_PARSE_MALFORMED",
    "ARTIFACT_PARSE_MISSING",
    "ARTIFACT_PARSE_NONE",
    "ARTIFACT_PARSE_VALID",
    "BENCHMARK_TYPE_TO_CARD",
    "CARD_TO_BENCHMARK_TYPE",
    "CONSTRAINT_CARD",
    "DECISION_CARD",
    "NONE_VALUE",
    "PROCEDURE_CARD",
    "TASK_CARD",
    "build_artifact_generation_telemetry",
    "parse_benchmark_artifact_suggestions",
]
