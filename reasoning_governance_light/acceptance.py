# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Deterministic artifact acceptance for reasoning_governance_light.

This module provides the minimal v1 governance boundary between:
- reasoning-engine (proposes)
- reasoning_brain_storage (persists)

It does not mutate storage and does not perform model-based or semantic judging.
"""

from __future__ import annotations

from typing import Any, Mapping

from .errors import GovernanceContractViolation, GovernanceLightError
from .types import AcceptanceDecision, AcceptanceStatus


def evaluate_artifact(
    candidate: Mapping[str, object],
    brain_state: Mapping[str, object],
) -> AcceptanceDecision:
    """
    Evaluate a structured artifact candidate against a read-only brain snapshot.

    Contract:
    - side-effect free
    - deterministic
    - no I/O
    - no storage mutation
    - reject is a normal decision, not an exception
    """
    _validate_candidate_input(candidate)
    normalized_brain_state = _normalize_brain_state(brain_state)

    artifact_id = _extract_non_empty_string(candidate, "id")
    artifact_type = _extract_non_empty_string(candidate, "type")

    if artifact_id is None:
        return AcceptanceDecision(
            status="rejected",
            reason_code="missing_required_field",
            artifact_id=None,
            notes="missing non-empty 'id'",
        )

    if artifact_type is None:
        return AcceptanceDecision(
            status="rejected",
            reason_code="missing_required_field",
            artifact_id=artifact_id,
            notes="missing non-empty 'type'",
        )

    if artifact_type not in _allowed_artifact_types():
        return AcceptanceDecision(
            status="rejected",
            reason_code="invalid_type",
            artifact_id=artifact_id,
            notes=f"unsupported artifact type: {artifact_type}",
        )

    existing_by_id = normalized_brain_state["artifacts_by_id"]
    if artifact_id in existing_by_id:
        return AcceptanceDecision(
            status="duplicate",
            reason_code="duplicate_id",
            artifact_id=artifact_id,
            duplicate_of=artifact_id,
        )

    normalized_candidate = _normalize_artifact_payload(candidate)
    normalized_candidate_signature = _artifact_signature(normalized_candidate)

    for existing_artifact_id, existing_artifact in existing_by_id.items():
        existing_signature = _artifact_signature(existing_artifact)
        if normalized_candidate_signature == existing_signature:
            return AcceptanceDecision(
                status="duplicate",
                reason_code="duplicate_exact",
                artifact_id=artifact_id,
                duplicate_of=existing_artifact_id,
            )

    # v1 rediscovery remains strictly deterministic and non-semantic.
    # We classify rediscovery only when:
    # - type matches
    # - canonical content fields match exactly
    # - id differs
    rediscovered_of = _detect_rule_based_rediscovery(
        normalized_candidate,
        normalized_brain_state["artifacts_by_id"],
    )
    if rediscovered_of is not None:
        return AcceptanceDecision(
            status="rediscovered",
            reason_code="rediscovered_rule_match",
            artifact_id=artifact_id,
            rediscovered_of=rediscovered_of,
        )

    return AcceptanceDecision(
        status="accepted",
        reason_code="accepted",
        artifact_id=artifact_id,
    )


def _validate_candidate_input(candidate: object) -> None:
    if not isinstance(candidate, Mapping):
        raise GovernanceContractViolation("candidate must be a mapping")


def _normalize_brain_state(brain_state: object) -> dict[str, Any]:
    if not isinstance(brain_state, Mapping):
        raise GovernanceContractViolation("brain_state must be a mapping")

    artifacts = brain_state.get("artifacts_by_id", {})
    if not isinstance(artifacts, Mapping):
        raise GovernanceContractViolation(
            "brain_state field 'artifacts_by_id' must be a mapping"
        )

    normalized_artifacts: dict[str, dict[str, object]] = {}
    for raw_id, raw_artifact in artifacts.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise GovernanceContractViolation(
                "brain_state artifacts_by_id keys must be non-empty strings"
            )
        if not isinstance(raw_artifact, Mapping):
            raise GovernanceContractViolation(
                "brain_state artifacts_by_id values must be mappings"
            )

        normalized_id = raw_id.strip()
        normalized_artifacts[normalized_id] = _normalize_artifact_payload(raw_artifact)

    return {"artifacts_by_id": normalized_artifacts}


def _extract_non_empty_string(
    data: Mapping[str, object],
    field_name: str,
) -> str | None:
    value = data.get(field_name)
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    return cleaned


def _allowed_artifact_types() -> set[str]:
    return {
        "task",
        "decision",
        "constraint",
        "procedure",
        "issue",
    }


def _normalize_artifact_payload(artifact: Mapping[str, object]) -> dict[str, object]:
    """
    Produce a deterministic normalized artifact payload.

    Rules:
    - trim top-level string values
    - normalize id/type to trimmed strings when present
    - keep structure read-only and deterministic
    - do not invent missing fields
    """
    normalized: dict[str, object] = {}

    for key in sorted(artifact.keys()):
        if not isinstance(key, str):
            raise GovernanceContractViolation("artifact keys must be strings")

        value = artifact[key]
        normalized[key] = _normalize_value(value)

    return normalized


def _normalize_value(value: object) -> object:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    if isinstance(value, Mapping):
        normalized_dict: dict[str, object] = {}
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                raise GovernanceContractViolation("nested artifact keys must be strings")
            normalized_dict[key] = _normalize_value(value[key])
        return normalized_dict

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    # Keep v1 strict: unsupported value types are contract violations.
    raise GovernanceContractViolation(
        f"unsupported artifact value type: {type(value).__name__}"
    )


def _artifact_signature(artifact: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    """
    Exact deterministic signature for duplicate detection.

    For exact-duplicate classification we compare normalized full payloads.
    """
    return tuple((key, _freeze_value(value)) for key, value in sorted(artifact.items()))


def _freeze_value(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)

    if isinstance(value, dict):
        return tuple((key, _freeze_value(val)) for key, val in sorted(value.items()))

    return value


def _detect_rule_based_rediscovery(
    candidate: Mapping[str, object],
    existing_artifacts_by_id: Mapping[str, Mapping[str, object]],
) -> str | None:
    """
    Strict deterministic non-semantic rediscovery detection.

    v1 rule:
    - same type
    - same canonical content payload excluding 'id' and common metadata fields
    - different id
    """
    candidate_type = candidate.get("type")
    candidate_id = candidate.get("id")

    if not isinstance(candidate_type, str) or not isinstance(candidate_id, str):
        return None

    candidate_core = _core_comparison_payload(candidate)

    for existing_artifact_id, existing_artifact in existing_artifacts_by_id.items():
        existing_type = existing_artifact.get("type")
        existing_id = existing_artifact.get("id")

        if not isinstance(existing_type, str) or not isinstance(existing_id, str):
            continue

        if existing_id == candidate_id:
            continue
        if existing_type != candidate_type:
            continue

        existing_core = _core_comparison_payload(existing_artifact)
        if candidate_core == existing_core:
            return existing_artifact_id

    return None


def _core_comparison_payload(artifact: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    """
    Deterministic payload for non-semantic rediscovery classification.

    Excludes identity and common metadata fields.
    """
    excluded_fields = {
        "id",
        "created_at",
        "updated_at",
        "timestamp",
        "last_seen_at",
        "rediscovered_count",
    }

    filtered_items: list[tuple[str, object]] = []
    for key, value in sorted(artifact.items()):
        if key in excluded_fields:
            continue
        filtered_items.append((key, _freeze_value(value)))

    return tuple(filtered_items)


__all__ = [
    "AcceptanceDecision",
    "AcceptanceStatus",
    "GovernanceContractViolation",
    "GovernanceLightError",
    "evaluate_artifact",
]
