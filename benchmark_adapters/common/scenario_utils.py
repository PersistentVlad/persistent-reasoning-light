# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark scenario utilities for Persistent Reasoning Light.

This module defines deterministic helpers for loading, validating, and listing
benchmark scenarios stored as paired markdown and JSON files.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .benchmark_paths import (
    BenchmarkPaths,
    scenario_json_path,
    scenario_metadata_path,
    scenario_markdown_path,
    validate_scenario_id,
)


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    markdown_path: Path
    json_path: Path
    metadata_path: Path
    markdown_text: str
    config: dict[str, Any]


REQUIRED_SCENARIO_IDENTITY_FIELDS = {
    "scenario_id",
    "scenario_name",
    "scenario_type",
    "description",
}
REQUIRED_SCENARIO_TASK_FIELDS = {
    *REQUIRED_SCENARIO_IDENTITY_FIELDS,
    "steps",
}
REQUIRED_SCENARIO_METADATA_FIELDS = {
    "contract_version",
    "identity",
    "migration_lock",
    "execution_contract",
    "interpretation_support",
    "interpretation_contract",
    "retention_contract",
    "ghost_contract",
    "correctness_contract",
    "trajectory_contract",
    "expected_ready",
    "expected_file",
}
REQUIRED_MIGRATION_LOCK_FIELDS = {
    "execution_contract",
    "interpretation_support",
    "interpretation_contract",
    "retention_contract",
    "ghost_contract",
    "correctness_contract",
}
REQUIRED_EXECUTION_CONTRACT_FIELDS = {
    "scenario_mode",
    "showcase",
    "status",
    "return_to_origin",
}
REQUIRED_INTERPRETATION_SUPPORT_FIELDS = {
    "supports_retention",
    "supports_correctness",
    "supports_ghost",
    "supports_temporal_ghost",
    "trajectory_readiness",
}
REQUIRED_INTERPRETATION_CONTRACT_FIELDS = {
    "interpretation_variant",
    "layer_support",
}
REQUIRED_RETENTION_CONTRACT_FIELDS = {
    "retention_type",
    "checkpoints",
    "final_sections",
    "required_exact_section_headings",
}
REQUIRED_CORRECTNESS_CONTRACT_FIELDS = {
    "slot_section_heading",
    "value_match_policy",
    "expected_slot_values",
}
REQUIRED_EXPECTED_REF_CORRECTNESS_CONTRACT_FIELDS = {
    "slot_section_heading",
    "value_match_policy",
    "expected_ref",
}
REQUIRED_GHOST_CONTRACT_FIELDS = {
    "token_pattern",
    "valid_transformations",
}
REQUIRED_TRAJECTORY_CONTRACT_FIELDS = {
    "enabled",
}
REQUIRED_ENABLED_TRAJECTORY_CONTRACT_FIELDS = {
    "enabled",
    "mode",
    "checkpoint_expected_values",
}
REQUIRED_SECTION_CORRECTNESS_CONTRACT_FIELDS = {
    "section_id",
    "correctness_contract",
}
REQUIRED_EFFECTIVE_SCENARIO_CONFIG_FIELDS = {
    *REQUIRED_SCENARIO_IDENTITY_FIELDS,
    "supports_retention",
    "supports_correctness",
    "supports_ghost",
    "supports_temporal_ghost",
    "return_to_origin",
    "scenario_mode",
    "showcase",
    "status",
    "trajectory_readiness",
}
ALLOWED_SCENARIO_MODES = frozenset({"standard", "sectioned", "showcase"})
ALLOWED_SCENARIO_STATUSES = frozenset({"stable", "experimental", "deprecated"})
ALLOWED_TRAJECTORY_READINESS_VALUES = frozenset({"ready", "deferred", "unsupported"})
ALLOWED_LAYER_SUPPORT_VALUES = frozenset({"enabled", "deferred", "unsupported"})
SECTIONED_REFERENCE_COMPOSITION_TYPE = "sectioned_by_reference"
SECTIONED_REFERENCE_RESOLUTION_POLICY = "explicit_sections_only"
REQUIRED_COMPOSITION_SECTION_FIELDS = (
    "section_id",
    "section_label",
    "source_scenario_id",
    "include_steps",
    "max_percent",
    "interpretation_variant",
    "layer_support",
    "return_to_origin",
    "contract_imports",
)
REQUIRED_CONTRACT_IMPORT_FIELDS = (
    "retention_type",
    "unit_groups",
    "checkpoints",
    "final_sections",
    "required_exact_section_headings",
    "ghost_spec",
    "correctness_spec",
)
RESOLVED_SCENARIO_ARTIFACT_KEY = "resolved_scenario"
EXPECTED_VALUES_REF = "final.expected_slot_values"


def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"text file not found: {path}")
    if not path.is_file():
        raise ValueError(f"text path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"json file not found: {path}")
    if not path.is_file():
        raise ValueError(f"json path is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"scenario json must contain an object: {path}")

    return data


def _validate_correctness_contract_object(
    correctness_contract: dict[str, Any],
    *,
    context: str,
    expected_ready: bool = False,
) -> dict[str, Any]:
    if expected_ready:
        unexpected_value_fields = [
            field for field in ("expected_slot_values",) if field in correctness_contract
        ]
        if unexpected_value_fields:
            raise ValueError(
                f"{context} must not contain expected_slot_values when expected_ready=true"
            )
        missing_expected_ref_fields = sorted(
            field
            for field in REQUIRED_EXPECTED_REF_CORRECTNESS_CONTRACT_FIELDS
            if field not in correctness_contract
        )
        if missing_expected_ref_fields:
            raise ValueError(
                f"{context} is missing required fields: "
                + ", ".join(missing_expected_ref_fields)
            )
        slot_section_heading = correctness_contract.get("slot_section_heading")
        if not isinstance(slot_section_heading, str) or not slot_section_heading.strip():
            raise ValueError(f"{context}.slot_section_heading must be a non-empty string")
        value_match_policy = correctness_contract.get("value_match_policy")
        if not isinstance(value_match_policy, str) or not value_match_policy.strip():
            raise ValueError(f"{context}.value_match_policy must be a non-empty string")
        expected_ref = correctness_contract.get("expected_ref")
        if expected_ref != EXPECTED_VALUES_REF:
            raise ValueError(f"{context}.expected_ref must be '{EXPECTED_VALUES_REF}'")
        return correctness_contract

    missing_correctness_fields = sorted(
        field for field in REQUIRED_CORRECTNESS_CONTRACT_FIELDS if field not in correctness_contract
    )
    if missing_correctness_fields:
        raise ValueError(
            f"{context} is missing required fields: " + ", ".join(missing_correctness_fields)
        )
    slot_section_heading = correctness_contract.get("slot_section_heading")
    if not isinstance(slot_section_heading, str) or not slot_section_heading.strip():
        raise ValueError(f"{context}.slot_section_heading must be a non-empty string")
    value_match_policy = correctness_contract.get("value_match_policy")
    if not isinstance(value_match_policy, str) or not value_match_policy.strip():
        raise ValueError(f"{context}.value_match_policy must be a non-empty string")
    expected_slot_values = correctness_contract.get("expected_slot_values")
    if not isinstance(expected_slot_values, dict) or not expected_slot_values:
        raise ValueError(f"{context}.expected_slot_values must be a non-empty object")
    for field_name, field_value in expected_slot_values.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise ValueError(f"{context}.expected_slot_values contains an invalid field name")
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"{context}.expected_slot_values contains an invalid field value")
    return correctness_contract


def _validate_expected_file_name(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string when expected_ready=true")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError(f"{context} must not contain surrounding whitespace")
    if cleaned != Path(cleaned).name:
        raise ValueError(f"{context} must be a file name, not a path")
    if not cleaned.endswith(".expected.json"):
        raise ValueError(f"{context} must end with .expected.json")
    return cleaned


def load_expected_values_file(
    metadata_path: Path,
    *,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    expected_ready = metadata.get("expected_ready")
    if not isinstance(expected_ready, bool):
        raise ValueError("metadata expected_ready must be boolean")
    expected_file = metadata.get("expected_file")
    if not expected_ready:
        if expected_file is not None:
            raise ValueError("metadata expected_file must be null when expected_ready=false")
        return None

    expected_file_name = _validate_expected_file_name(
        expected_file,
        context="metadata expected_file",
    )
    expected_path = metadata_path.with_name(expected_file_name)
    expected_payload = load_json(expected_path)
    scenario_id = _require_dict(metadata, "identity", "metadata")["scenario_id"]
    retention_contract = metadata.get("retention_contract")
    valid_checkpoint_ids: set[str] = set()
    if isinstance(retention_contract, dict):
        checkpoints = retention_contract.get("checkpoints")
        if isinstance(checkpoints, list):
            for checkpoint in checkpoints:
                if isinstance(checkpoint, dict):
                    checkpoint_id = checkpoint.get("checkpoint_id")
                    if isinstance(checkpoint_id, str) and checkpoint_id.strip():
                        valid_checkpoint_ids.add(checkpoint_id.strip())
    _validate_expected_values_payload(
        expected_payload,
        expected_scenario_id=validate_scenario_id(scenario_id),
        valid_checkpoint_ids=valid_checkpoint_ids,
        context=f"expected file {expected_path}",
    )
    return expected_payload


def _validate_expected_values_payload(
    payload: dict[str, Any],
    *,
    expected_scenario_id: str,
    valid_checkpoint_ids: set[str],
    context: str,
) -> dict[str, Any]:
    allowed_top_level_fields = {"scenario_id", "final", "checkpoints"}
    unexpected_fields = sorted(field for field in payload if field not in allowed_top_level_fields)
    if unexpected_fields:
        raise ValueError(f"{context} contains unsupported fields: " + ", ".join(unexpected_fields))
    scenario_id = validate_scenario_id(payload.get("scenario_id"))
    if scenario_id != expected_scenario_id:
        raise ValueError(
            f"{context} scenario_id mismatch: {expected_scenario_id} != {scenario_id}"
        )
    final = payload.get("final")
    if not isinstance(final, dict):
        raise ValueError(f"{context}.final must be an object")
    final_unexpected_fields = sorted(field for field in final if field != "expected_slot_values")
    if final_unexpected_fields:
        raise ValueError(
            f"{context}.final contains unsupported fields: "
            + ", ".join(final_unexpected_fields)
        )
    expected_slot_values = final.get("expected_slot_values")
    if not isinstance(expected_slot_values, dict) or not expected_slot_values:
        raise ValueError(f"{context}.final.expected_slot_values must be a non-empty object")
    _validate_expected_value_mapping(
        expected_slot_values,
        context=f"{context}.final.expected_slot_values",
    )

    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list):
        raise ValueError(f"{context}.checkpoints must be a list")
    seen_checkpoint_ids: set[str] = set()
    for index, checkpoint in enumerate(checkpoints):
        if not isinstance(checkpoint, dict):
            raise ValueError(f"{context}.checkpoints[{index}] must be an object")
        unexpected_checkpoint_fields = sorted(
            field for field in checkpoint if field not in {"checkpoint_id", "expected_state"}
        )
        if unexpected_checkpoint_fields:
            raise ValueError(
                f"{context}.checkpoints[{index}] contains unsupported fields: "
                + ", ".join(unexpected_checkpoint_fields)
            )
        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError(f"{context}.checkpoints[{index}].checkpoint_id must be non-empty")
        normalized_checkpoint_id = checkpoint_id.strip()
        if normalized_checkpoint_id != checkpoint_id:
            raise ValueError(
                f"{context}.checkpoints[{index}].checkpoint_id must not contain surrounding whitespace"
            )
        if valid_checkpoint_ids and normalized_checkpoint_id not in valid_checkpoint_ids:
            raise ValueError(
                f"{context}.checkpoints[{index}].checkpoint_id does not match retention checkpoints"
            )
        if normalized_checkpoint_id in seen_checkpoint_ids:
            raise ValueError(
                f"{context}.checkpoints contains duplicate checkpoint_id '{normalized_checkpoint_id}'"
            )
        seen_checkpoint_ids.add(normalized_checkpoint_id)
        expected_state = checkpoint.get("expected_state")
        if not isinstance(expected_state, dict) or not expected_state:
            raise ValueError(
                f"{context}.checkpoints[{index}].expected_state must be a non-empty object"
            )
        _validate_expected_value_mapping(
            expected_state,
            context=f"{context}.checkpoints[{index}].expected_state",
        )
    return payload


def _validate_expected_value_mapping(values: dict[str, Any], *, context: str) -> None:
    for field_name, field_value in values.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise ValueError(f"{context} contains an invalid field name")
        _validate_expected_value(field_value, context=f"{context}.{field_name}")


def _validate_expected_value(value: Any, *, context: str) -> None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_expected_value(item, context=f"{context}[{index}]")
        return
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{context} contains an invalid nested key")
            _validate_expected_value(nested_value, context=f"{context}.{key}")
        return
    raise ValueError(f"{context} contains unsupported expected value type")


def _resolve_expected_ref(
    expected_payload: dict[str, Any],
    expected_ref: str,
) -> Any:
    if expected_ref != EXPECTED_VALUES_REF:
        raise ValueError(f"unsupported expected_ref: {expected_ref}")
    return copy.deepcopy(expected_payload["final"]["expected_slot_values"])


def _resolve_correctness_contract_expected_ref(
    correctness_contract: dict[str, Any] | None,
    *,
    expected_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if correctness_contract is None:
        return None
    resolved = copy.deepcopy(correctness_contract)
    expected_ref = resolved.pop("expected_ref", None)
    if expected_ref is None:
        return resolved
    if expected_payload is None:
        raise ValueError("correctness_contract.expected_ref requires loaded expected data")
    resolved["expected_slot_values"] = _resolve_expected_ref(expected_payload, expected_ref)
    return resolved


def _validate_ghost_contract_object(
    ghost_contract: dict[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    missing_ghost_fields = sorted(
        field for field in REQUIRED_GHOST_CONTRACT_FIELDS if field not in ghost_contract
    )
    if missing_ghost_fields:
        raise ValueError(f"{context} is missing required fields: " + ", ".join(missing_ghost_fields))
    token_pattern = ghost_contract.get("token_pattern")
    if not isinstance(token_pattern, str) or not token_pattern.strip():
        raise ValueError(f"{context}.token_pattern must be a non-empty string")
    valid_transformations = ghost_contract.get("valid_transformations")
    if not isinstance(valid_transformations, dict):
        raise ValueError(f"{context}.valid_transformations must be an object")
    for transformation_name, transformation_values in valid_transformations.items():
        if not isinstance(transformation_name, str) or not transformation_name.strip():
            raise ValueError(f"{context}.valid_transformations keys must be non-empty strings")
        if not isinstance(transformation_values, list):
            raise ValueError(f"{context}.valid_transformations values must be lists")
        for transformation_id in transformation_values:
            if not isinstance(transformation_id, str) or not transformation_id.strip():
                raise ValueError(
                    f"{context}.valid_transformations transformation ids must be non-empty strings"
                )
    return ghost_contract


def _validate_trajectory_contract_object(
    trajectory_contract: dict[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    missing_fields = sorted(
        field for field in REQUIRED_TRAJECTORY_CONTRACT_FIELDS if field not in trajectory_contract
    )
    if missing_fields:
        raise ValueError(f"{context} is missing required fields: " + ", ".join(missing_fields))

    enabled = trajectory_contract.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError(f"{context}.enabled must be boolean")

    if not enabled:
        extra_fields = sorted(field for field in trajectory_contract if field != "enabled")
        if extra_fields:
            raise ValueError(
                f"{context} disabled form supports only enabled=false; extra fields: "
                + ", ".join(extra_fields)
            )
        return trajectory_contract

    missing_enabled_fields = sorted(
        field
        for field in REQUIRED_ENABLED_TRAJECTORY_CONTRACT_FIELDS
        if field not in trajectory_contract
    )
    if missing_enabled_fields:
        raise ValueError(
            f"{context} enabled form is missing required fields: "
            + ", ".join(missing_enabled_fields)
        )
    extra_enabled_fields = sorted(
        field
        for field in trajectory_contract
        if field not in REQUIRED_ENABLED_TRAJECTORY_CONTRACT_FIELDS
    )
    if extra_enabled_fields:
        raise ValueError(
            f"{context} enabled form contains unsupported fields: "
            + ", ".join(extra_enabled_fields)
        )

    mode = trajectory_contract.get("mode")
    if mode != "checkpoint_expected_values":
        raise ValueError(f"{context}.mode must be exactly 'checkpoint_expected_values'")

    checkpoint_expected_values = trajectory_contract.get("checkpoint_expected_values")
    if not isinstance(checkpoint_expected_values, list) or not checkpoint_expected_values:
        raise ValueError(f"{context}.checkpoint_expected_values must be a non-empty list")

    seen_checkpoint_ids: set[str] = set()
    for index, checkpoint in enumerate(checkpoint_expected_values, start=1):
        if not isinstance(checkpoint, dict):
            raise ValueError(
                f"{context}.checkpoint_expected_values[{index}] must be an object"
            )
        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError(
                f"{context}.checkpoint_expected_values[{index}].checkpoint_id "
                "must be a non-empty string"
            )
        normalized_checkpoint_id = checkpoint_id.strip()
        if normalized_checkpoint_id in seen_checkpoint_ids:
            raise ValueError(
                f"{context}.checkpoint_expected_values contains duplicate checkpoint_id "
                f"'{normalized_checkpoint_id}'"
            )
        seen_checkpoint_ids.add(normalized_checkpoint_id)

        expected_slot_values = checkpoint.get("expected_slot_values")
        if not isinstance(expected_slot_values, dict) or not expected_slot_values:
            raise ValueError(
                f"{context}.checkpoint_expected_values[{index}].expected_slot_values "
                "must be a non-empty object"
            )
        for field_name, field_value in expected_slot_values.items():
            if not isinstance(field_name, str) or not field_name.strip():
                raise ValueError(
                    f"{context}.checkpoint_expected_values[{index}].expected_slot_values "
                    "contains an invalid field name"
                )
            if not isinstance(field_value, str):
                raise ValueError(
                    f"{context}.checkpoint_expected_values[{index}].expected_slot_values "
                    "values must be strings"
                )

    return trajectory_contract


def _validate_scenario_identity_fields(
    config: dict[str, Any],
    expected_scenario_id: str,
) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_SCENARIO_IDENTITY_FIELDS if field not in config)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"scenario config is missing required identity fields: {joined}")

    validated_config_id = validate_scenario_id(config["scenario_id"])
    if validated_config_id != expected_scenario_id:
        raise ValueError(
            "scenario_id mismatch between filename and scenario config: "
            f"{expected_scenario_id} != {validated_config_id}"
        )

    if not isinstance(config["scenario_name"], str) or not config["scenario_name"].strip():
        raise ValueError("scenario_name must be a non-empty string")

    if not isinstance(config["scenario_type"], str) or not config["scenario_type"].strip():
        raise ValueError("scenario_type must be a non-empty string")

    if not isinstance(config["description"], str) or not config["description"].strip():
        raise ValueError("description must be a non-empty string")

    return config


def validate_scenario_task_config(config: dict[str, Any], expected_scenario_id: str) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_SCENARIO_TASK_FIELDS if field not in config)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"scenario config is missing required task fields: {joined}")

    _validate_scenario_identity_fields(config, expected_scenario_id)

    if not isinstance(config["steps"], list) or not config["steps"]:
        raise ValueError("steps must be a non-empty list")

    seen_step_ids: set[str] = set()

    for index, step in enumerate(config["steps"], start=1):
        if not isinstance(step, dict):
            raise ValueError(f"scenario step #{index} must be an object")
        if "step_id" not in step or "instruction" not in step:
            raise ValueError(
                f"scenario step #{index} must contain step_id and instruction"
            )

        step_id = step["step_id"]
        instruction = step["instruction"]

        if not isinstance(step_id, str) or not step_id.strip():
            raise ValueError(f"scenario step #{index} has invalid step_id")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError(f"scenario step #{index} has invalid instruction")

        normalized_step_id = step_id.strip()
        if normalized_step_id in seen_step_ids:
            raise ValueError(f"duplicate step_id detected: {normalized_step_id}")
        seen_step_ids.add(normalized_step_id)

    return config


def validate_composition_authoring_config(
    config: dict[str, Any],
    expected_scenario_id: str,
) -> dict[str, Any]:
    _validate_scenario_identity_fields(config, expected_scenario_id)

    composition_spec = config.get("composition_spec")
    if not isinstance(composition_spec, dict):
        raise ValueError("composition scenario config requires composition_spec")

    if composition_spec.get("composition_type") == SECTIONED_REFERENCE_COMPOSITION_TYPE:
        if "steps" in config:
            raise ValueError(
                "sectioned_by_reference composition scenarios must not define top-level steps"
            )

    return config


def validate_scenario_metadata(metadata: dict[str, Any], expected_scenario_id: str) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_SCENARIO_METADATA_FIELDS if field not in metadata)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"scenario metadata is missing required fields: {joined}")

    contract_version = metadata.get("contract_version")
    if not isinstance(contract_version, str) or not contract_version.strip():
        raise ValueError("metadata contract_version must be a non-empty string")

    identity = metadata.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("metadata identity must be an object")
    validated_metadata_id = validate_scenario_id(identity.get("scenario_id"))
    if validated_metadata_id != expected_scenario_id:
        raise ValueError(
            "scenario_id mismatch between filename and scenario metadata: "
            f"{expected_scenario_id} != {validated_metadata_id}"
        )

    migration_lock = metadata.get("migration_lock")
    if not isinstance(migration_lock, dict):
        raise ValueError("metadata migration_lock must be an object")
    missing_lock_fields = sorted(
        field for field in REQUIRED_MIGRATION_LOCK_FIELDS if field not in migration_lock
    )
    if missing_lock_fields:
        raise ValueError(
            "metadata migration_lock is missing required fields: "
            + ", ".join(missing_lock_fields)
        )
    for field_name in REQUIRED_MIGRATION_LOCK_FIELDS:
        if not isinstance(migration_lock[field_name], bool):
            raise ValueError(f"metadata migration_lock.{field_name} must be boolean")

    execution_contract = metadata.get("execution_contract")
    if not isinstance(execution_contract, dict):
        raise ValueError("metadata execution_contract must be an object")
    missing_execution_fields = sorted(
        field for field in REQUIRED_EXECUTION_CONTRACT_FIELDS if field not in execution_contract
    )
    if missing_execution_fields:
        raise ValueError(
            "metadata execution_contract is missing required fields: "
            + ", ".join(missing_execution_fields)
        )
    scenario_mode = execution_contract["scenario_mode"]
    if scenario_mode not in ALLOWED_SCENARIO_MODES:
        raise ValueError(
            "metadata execution_contract.scenario_mode must be one of "
            + ", ".join(sorted(ALLOWED_SCENARIO_MODES))
        )
    if not isinstance(execution_contract["showcase"], bool):
        raise ValueError("metadata execution_contract.showcase must be boolean")
    status = execution_contract["status"]
    if status not in ALLOWED_SCENARIO_STATUSES:
        raise ValueError(
            "metadata execution_contract.status must be one of "
            + ", ".join(sorted(ALLOWED_SCENARIO_STATUSES))
        )
    if not isinstance(execution_contract["return_to_origin"], bool):
        raise ValueError("metadata execution_contract.return_to_origin must be boolean")

    expected_ready = metadata.get("expected_ready")
    if not isinstance(expected_ready, bool):
        raise ValueError("metadata expected_ready must be boolean")
    expected_file = metadata.get("expected_file")
    if expected_ready:
        _validate_expected_file_name(expected_file, context="metadata expected_file")
    elif expected_file is not None:
        raise ValueError("metadata expected_file must be null when expected_ready=false")

    interpretation_support = metadata.get("interpretation_support")
    if not isinstance(interpretation_support, dict):
        raise ValueError("metadata interpretation_support must be an object")
    missing_support_fields = sorted(
        field
        for field in REQUIRED_INTERPRETATION_SUPPORT_FIELDS
        if field not in interpretation_support
    )
    if missing_support_fields:
        raise ValueError(
            "metadata interpretation_support is missing required fields: "
            + ", ".join(missing_support_fields)
        )
    for field_name in (
        "supports_retention",
        "supports_correctness",
        "supports_ghost",
        "supports_temporal_ghost",
    ):
        if not isinstance(interpretation_support[field_name], bool):
            raise ValueError(f"metadata interpretation_support.{field_name} must be boolean")
    trajectory_readiness = interpretation_support["trajectory_readiness"]
    if trajectory_readiness not in ALLOWED_TRAJECTORY_READINESS_VALUES:
        raise ValueError(
            "metadata interpretation_support.trajectory_readiness must be one of "
            + ", ".join(sorted(ALLOWED_TRAJECTORY_READINESS_VALUES))
        )

    trajectory_contract = metadata.get("trajectory_contract")
    if trajectory_contract is not None:
        if not isinstance(trajectory_contract, dict):
            raise ValueError("metadata trajectory_contract must be an object or null")
        _validate_trajectory_contract_object(
            trajectory_contract,
            context="metadata trajectory_contract",
        )

    ghost_contract = metadata.get("ghost_contract")
    if ghost_contract is not None and not isinstance(ghost_contract, dict):
        raise ValueError("metadata ghost_contract must be an object or null")
    if isinstance(ghost_contract, dict):
        _validate_ghost_contract_object(
            ghost_contract,
            context="metadata ghost_contract",
        )

    if scenario_mode == "sectioned":
        if ghost_contract is not None:
            raise ValueError(
                "metadata ghost_contract must be null for sectioned scenarios during staged migration"
            )
    elif interpretation_support["supports_ghost"]:
        if migration_lock["ghost_contract"]:
            if not isinstance(ghost_contract, dict):
                raise ValueError(
                    "supports_ghost=true with migrated ghost_contract requires metadata ghost_contract"
                )
        elif ghost_contract is not None:
            raise ValueError(
                "metadata ghost_contract must be null until ghost migration is enabled for this scenario"
            )
    elif ghost_contract is not None:
        raise ValueError("supports_ghost=false requires metadata ghost_contract to be null")

    section_ghost_contract_migration = migration_lock.get("section_ghost_contract")
    if section_ghost_contract_migration is not None and not isinstance(
        section_ghost_contract_migration, bool
    ):
        raise ValueError("metadata migration_lock.section_ghost_contract must be boolean")
    section_ghost_contracts = metadata.get("section_ghost_contracts")
    if section_ghost_contract_migration:
        if scenario_mode != "sectioned":
            raise ValueError(
                "metadata migration_lock.section_ghost_contract is supported only for sectioned scenarios"
            )
        if not isinstance(section_ghost_contracts, list) or not section_ghost_contracts:
            raise ValueError(
                "metadata section_ghost_contracts must be a non-empty list when section ghost migration is enabled"
            )
        seen_section_ids: set[str] = set()
        for index, entry in enumerate(section_ghost_contracts):
            if not isinstance(entry, dict):
                raise ValueError("metadata section_ghost_contracts entries must be objects")
            missing_section_fields = sorted(
                field
                for field in ("section_id", "ghost_contract")
                if field not in entry
            )
            if missing_section_fields:
                raise ValueError(
                    "metadata section_ghost_contracts"
                    f"[{index}] is missing required fields: "
                    + ", ".join(missing_section_fields)
                )
            section_id = _require_config_string(
                entry,
                "section_id",
                "metadata section_ghost_contracts entry",
            )
            if section_id in seen_section_ids:
                raise ValueError(
                    "metadata section_ghost_contracts contains duplicate section_id "
                    f"'{section_id}'"
                )
            seen_section_ids.add(section_id)
            ghost_payload = entry.get("ghost_contract")
            if not isinstance(ghost_payload, dict):
                raise ValueError(
                    f"metadata section_ghost_contracts[{index}].ghost_contract must be an object"
                )
            _validate_ghost_contract_object(
                ghost_payload,
                context=f"metadata section_ghost_contracts[{index}].ghost_contract",
            )
    elif section_ghost_contracts is not None:
        raise ValueError(
            "metadata section_ghost_contracts must be omitted unless section ghost migration is enabled"
        )

    interpretation_contract = metadata.get("interpretation_contract")
    if not isinstance(interpretation_contract, dict):
        raise ValueError("metadata interpretation_contract must be an object")
    missing_contract_fields = sorted(
        field
        for field in REQUIRED_INTERPRETATION_CONTRACT_FIELDS
        if field not in interpretation_contract
    )
    if missing_contract_fields:
        raise ValueError(
            "metadata interpretation_contract is missing required fields: "
            + ", ".join(missing_contract_fields)
        )
    interpretation_variant = interpretation_contract.get("interpretation_variant")
    if not isinstance(interpretation_variant, str) or not interpretation_variant.strip():
        raise ValueError(
            "metadata interpretation_contract.interpretation_variant must be a non-empty string"
        )
    interpretation_reason = interpretation_contract.get("reason")
    if interpretation_reason is not None and (
        not isinstance(interpretation_reason, str) or not interpretation_reason.strip()
    ):
        raise ValueError(
            "metadata interpretation_contract.reason must be a non-empty string when provided"
        )
    layer_support = interpretation_contract.get("layer_support")
    if not isinstance(layer_support, dict):
        raise ValueError("metadata interpretation_contract.layer_support must be an object")
    for field_name in ("retention", "correctness", "ghost"):
        support_value = layer_support.get(field_name)
        if support_value not in ALLOWED_LAYER_SUPPORT_VALUES:
            raise ValueError(
                "metadata interpretation_contract.layer_support."
                f"{field_name} must be one of "
                + ", ".join(sorted(ALLOWED_LAYER_SUPPORT_VALUES))
            )

    interpretation_sections = interpretation_contract.get("sections")
    if interpretation_sections is not None:
        if not isinstance(interpretation_sections, list) or not interpretation_sections:
            raise ValueError(
                "metadata interpretation_contract.sections must be a non-empty list when provided"
            )
        seen_section_ids: set[str] = set()
        for index, section in enumerate(interpretation_sections, start=1):
            if not isinstance(section, dict):
                raise ValueError(
                    "metadata interpretation_contract.sections"
                    f"[{index}] must be an object"
                )
            section_id = section.get("section_id")
            if not isinstance(section_id, str) or not section_id.strip():
                raise ValueError(
                    "metadata interpretation_contract.sections"
                    f"[{index}].section_id must be a non-empty string"
                )
            normalized_section_id = section_id.strip()
            if normalized_section_id in seen_section_ids:
                raise ValueError(
                    "metadata interpretation_contract.sections contains duplicate "
                    f"section_id '{normalized_section_id}'"
                )
            seen_section_ids.add(normalized_section_id)

            section_variant = section.get("interpretation_variant")
            if not isinstance(section_variant, str) or not section_variant.strip():
                raise ValueError(
                    "metadata interpretation_contract.sections"
                    f"[{index}].interpretation_variant must be a non-empty string"
                )
            section_layer_support = section.get("layer_support")
            if not isinstance(section_layer_support, dict):
                raise ValueError(
                    "metadata interpretation_contract.sections"
                    f"[{index}].layer_support must be an object"
                )
            for field_name in ("retention", "correctness", "ghost"):
                support_value = section_layer_support.get(field_name)
                if support_value not in ALLOWED_LAYER_SUPPORT_VALUES:
                    raise ValueError(
                        "metadata interpretation_contract.sections"
                        f"[{index}].layer_support.{field_name} must be one of "
                        + ", ".join(sorted(ALLOWED_LAYER_SUPPORT_VALUES))
                    )
            section_reason = section.get("reason")
            if section_reason is not None and (
                not isinstance(section_reason, str) or not section_reason.strip()
            ):
                raise ValueError(
                    "metadata interpretation_contract.sections"
                    f"[{index}].reason must be a non-empty string when provided"
                )

    retention_contract = metadata.get("retention_contract")
    supports_retention = interpretation_support["supports_retention"]
    if supports_retention:
        if not isinstance(retention_contract, dict):
            raise ValueError(
                "metadata retention_contract must be an object when supports_retention=true"
            )
        missing_retention_fields = sorted(
            field
            for field in REQUIRED_RETENTION_CONTRACT_FIELDS
            if field not in retention_contract
        )
        if missing_retention_fields:
            raise ValueError(
                "metadata retention_contract is missing required fields: "
                + ", ".join(missing_retention_fields)
            )
        retention_type = retention_contract.get("retention_type")
        if not isinstance(retention_type, str) or not retention_type.strip():
            raise ValueError(
                "metadata retention_contract.retention_type must be a non-empty string"
            )
        unit_groups = retention_contract.get("unit_groups")
        if unit_groups is not None and (not isinstance(unit_groups, list) or not unit_groups):
            raise ValueError(
                "metadata retention_contract.unit_groups must be a non-empty list when provided"
            )
        checkpoints = retention_contract.get("checkpoints")
        if not isinstance(checkpoints, list) or not checkpoints:
            raise ValueError(
                "metadata retention_contract.checkpoints must be a non-empty list"
            )
        final_sections = retention_contract.get("final_sections")
        if not isinstance(final_sections, dict):
            raise ValueError("metadata retention_contract.final_sections must be an object")
        for field_name in ("retained", "lost"):
            field_value = final_sections.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(
                    f"metadata retention_contract.final_sections.{field_name} "
                    "must be a non-empty string"
                )
        required_headings = retention_contract.get("required_exact_section_headings")
        if not isinstance(required_headings, list) or not required_headings:
            raise ValueError(
                "metadata retention_contract.required_exact_section_headings "
                "must be a non-empty list"
            )
        for index, heading in enumerate(required_headings, start=1):
            if not isinstance(heading, str) or not heading.strip():
                raise ValueError(
                    "metadata retention_contract.required_exact_section_headings"
                    f"[{index}] must be a non-empty string"
                )
        retention_sections = retention_contract.get("sections")
        if retention_sections is not None:
            if not isinstance(retention_sections, list) or not retention_sections:
                raise ValueError(
                    "metadata retention_contract.sections must be a non-empty list when provided"
                )
            seen_section_ids: set[str] = set()
            for index, section in enumerate(retention_sections, start=1):
                if not isinstance(section, dict):
                    raise ValueError(
                        f"metadata retention_contract.sections[{index}] must be an object"
                    )
                section_id = section.get("section_id")
                if not isinstance(section_id, str) or not section_id.strip():
                    raise ValueError(
                        "metadata retention_contract.sections"
                        f"[{index}].section_id must be a non-empty string"
                    )
                normalized_section_id = section_id.strip()
                if normalized_section_id in seen_section_ids:
                    raise ValueError(
                        "metadata retention_contract.sections contains duplicate "
                        f"section_id '{normalized_section_id}'"
                    )
                seen_section_ids.add(normalized_section_id)
                section_retention_type = section.get("retention_type")
                if section_retention_type is not None and (
                    not isinstance(section_retention_type, str)
                    or not section_retention_type.strip()
                ):
                    raise ValueError(
                        "metadata retention_contract.sections"
                        f"[{index}].retention_type must be a non-empty string when provided"
                    )
                section_unit_groups = section.get("unit_groups")
                if section_unit_groups is not None and (
                    not isinstance(section_unit_groups, list) or not section_unit_groups
                ):
                    raise ValueError(
                        "metadata retention_contract.sections"
                        f"[{index}].unit_groups must be a non-empty list when provided"
                    )
    elif retention_contract is not None:
        raise ValueError(
            "metadata retention_contract must be null when supports_retention=false"
        )

    correctness_contract = metadata.get("correctness_contract")
    scenario_mode = execution_contract["scenario_mode"]
    supports_correctness = interpretation_support["supports_correctness"]
    section_correctness_contract_migration = migration_lock.get("section_correctness_contract")
    if section_correctness_contract_migration is not None and not isinstance(
        section_correctness_contract_migration, bool
    ):
        raise ValueError("metadata migration_lock.section_correctness_contract must be boolean")
    section_correctness_contracts = metadata.get("section_correctness_contracts")
    if section_correctness_contract_migration:
        if scenario_mode != "sectioned":
            raise ValueError(
                "metadata migration_lock.section_correctness_contract is supported only for sectioned scenarios"
            )
        if not isinstance(section_correctness_contracts, list) or not section_correctness_contracts:
            raise ValueError(
                "metadata section_correctness_contracts must be a non-empty list when section correctness migration is enabled"
            )
        seen_section_ids: set[str] = set()
        for index, entry in enumerate(section_correctness_contracts):
            if not isinstance(entry, dict):
                raise ValueError(
                    "metadata section_correctness_contracts entries must be objects"
                )
            missing_section_fields = sorted(
                field
                for field in REQUIRED_SECTION_CORRECTNESS_CONTRACT_FIELDS
                if field not in entry
            )
            if missing_section_fields:
                raise ValueError(
                    "metadata section_correctness_contracts"
                    f"[{index}] is missing required fields: "
                    + ", ".join(missing_section_fields)
                )
            section_id = _require_config_string(
                entry,
                "section_id",
                "metadata section_correctness_contracts entry",
            )
            if section_id in seen_section_ids:
                raise ValueError(
                    "metadata section_correctness_contracts contains duplicate section_id "
                    f"'{section_id}'"
                )
            seen_section_ids.add(section_id)
            correctness_payload = entry.get("correctness_contract")
            if not isinstance(correctness_payload, dict):
                raise ValueError(
                    "metadata section_correctness_contracts"
                    f"[{index}].correctness_contract must be an object"
                )
        _validate_correctness_contract_object(
            correctness_payload,
            context=(
                "metadata section_correctness_contracts"
                f"[{index}].correctness_contract"
            ),
            expected_ready=False,
        )
    elif section_correctness_contracts is not None:
        raise ValueError(
            "metadata section_correctness_contracts must be omitted unless section correctness migration is enabled"
        )

    if scenario_mode == "sectioned":
        if correctness_contract is not None:
            raise ValueError(
                "metadata correctness_contract must be null for sectioned scenarios in this migration stage"
            )
    elif supports_correctness:
        if not isinstance(correctness_contract, dict):
            raise ValueError(
                "metadata correctness_contract must be an object when supports_correctness=true for non-sectioned scenarios"
            )
        _validate_correctness_contract_object(
            correctness_contract,
            context="metadata correctness_contract",
            expected_ready=expected_ready,
        )
    elif correctness_contract is not None:
        raise ValueError(
            "metadata correctness_contract must be null when supports_correctness=false for non-sectioned scenarios"
        )

    return metadata


def merge_scenario_with_metadata(
    scenario_config: dict[str, Any],
    metadata: dict[str, Any],
    expected_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = copy.deepcopy(scenario_config)
    execution_contract = _require_dict(metadata, "execution_contract", "metadata")
    interpretation_support = _require_dict(metadata, "interpretation_support", "metadata")
    interpretation_contract = _require_dict(metadata, "interpretation_contract", "metadata")
    retention_contract = metadata.get("retention_contract")
    ghost_contract = metadata.get("ghost_contract")
    correctness_contract = metadata.get("correctness_contract")
    expected_ready = metadata["expected_ready"]
    section_correctness_contract_migration = (
        metadata.get("migration_lock", {}).get("section_correctness_contract") is True
    )
    section_correctness_contracts = metadata.get("section_correctness_contracts")
    section_ghost_contract_migration = (
        metadata.get("migration_lock", {}).get("section_ghost_contract") is True
    )
    section_ghost_contracts = metadata.get("section_ghost_contracts")

    merged["scenario_mode"] = execution_contract["scenario_mode"]
    merged["showcase"] = execution_contract["showcase"]
    merged["status"] = execution_contract["status"]
    merged["return_to_origin"] = execution_contract["return_to_origin"]
    merged["supports_retention"] = interpretation_support["supports_retention"]
    merged["supports_correctness"] = interpretation_support["supports_correctness"]
    merged["supports_ghost"] = interpretation_support["supports_ghost"]
    merged["supports_temporal_ghost"] = interpretation_support["supports_temporal_ghost"]
    merged["trajectory_readiness"] = interpretation_support["trajectory_readiness"]
    merged["contract_version"] = metadata["contract_version"]
    merged["migration_lock"] = copy.deepcopy(metadata["migration_lock"])
    merged["expected_ready"] = expected_ready
    merged["expected_file"] = metadata["expected_file"]
    if expected_payload is not None:
        merged["expected"] = copy.deepcopy(expected_payload)
    else:
        merged.pop("expected", None)
    resolved_correctness_contract = _resolve_correctness_contract_expected_ref(
        correctness_contract,
        expected_payload=expected_payload,
    )
    merged["interpretation_contract"] = copy.deepcopy(interpretation_contract)
    merged["correctness_contract"] = copy.deepcopy(resolved_correctness_contract)
    merged["interpretation_spec"] = {
        "interpretation_variant": interpretation_contract["interpretation_variant"],
        "layer_support": copy.deepcopy(interpretation_contract["layer_support"]),
    }
    interpretation_reason = interpretation_contract.get("reason")
    if isinstance(interpretation_reason, str) and interpretation_reason.strip():
        merged["interpretation_spec"]["reason"] = interpretation_reason.strip()

    interpretation_sections = interpretation_contract.get("sections")
    interpretation_section_map: dict[str, dict[str, Any]] = {}
    if interpretation_sections is not None:
        for raw_section in interpretation_sections:
            if not isinstance(raw_section, dict):
                raise ValueError(
                    "metadata interpretation_contract.sections entries must be objects"
                )
            section_id = _require_config_string(
                raw_section,
                "section_id",
                "metadata interpretation_contract section",
            )
            normalized_section = {
                "section_id": section_id,
                "interpretation_variant": _require_config_string(
                    raw_section,
                    "interpretation_variant",
                    "metadata interpretation_contract section",
                ),
                "layer_support": copy.deepcopy(
                    _require_dict(
                        raw_section,
                        "layer_support",
                        "metadata interpretation_contract section",
                    )
                ),
            }
            section_reason = raw_section.get("reason")
            if isinstance(section_reason, str) and section_reason.strip():
                normalized_section["reason"] = section_reason.strip()
            interpretation_section_map[section_id] = normalized_section

    composition_spec = merged.get("composition_spec")
    if isinstance(composition_spec, dict):
        composition_sections = _require_list(
            composition_spec,
            "sections",
            "scenario composition_spec",
        )
        if interpretation_section_map and len(interpretation_section_map) != len(composition_sections):
            raise ValueError(
                "metadata interpretation_contract.sections must align 1:1 with composition_spec.sections"
            )
        for section in composition_sections:
            if not isinstance(section, dict):
                raise ValueError("scenario composition_spec.sections entries must be objects")
            section_id = _require_config_string(section, "section_id", "composition section")
            metadata_section = interpretation_section_map.get(section_id)
            if metadata_section is None:
                if interpretation_section_map:
                    raise ValueError(
                        "metadata interpretation_contract is missing section metadata for "
                        f"'{section_id}'"
                    )
                continue
            section["interpretation_variant"] = metadata_section["interpretation_variant"]
            section["layer_support"] = copy.deepcopy(metadata_section["layer_support"])
            if "reason" in metadata_section:
                section["reason"] = metadata_section["reason"]
            else:
                section.pop("reason", None)

        extra_section_ids = sorted(
            section_id
            for section_id in interpretation_section_map
            if section_id
            not in {
                _require_config_string(section, "section_id", "composition section")
                for section in composition_sections
                if isinstance(section, dict)
            }
        )
        if extra_section_ids:
            raise ValueError(
                "metadata interpretation_contract.sections contains unknown section ids: "
                + ", ".join(extra_section_ids)
            )

    retention_spec = merged.get("retention_spec")
    if isinstance(retention_spec, dict):
        retention_sections = retention_spec.get("sections")
        if isinstance(retention_sections, list) and interpretation_section_map:
            seen_retention_section_ids: set[str] = set()
            for section in retention_sections:
                if not isinstance(section, dict):
                    raise ValueError("scenario retention_spec.sections entries must be objects")
                section_id = _require_config_string(
                    section,
                    "section_id",
                    "retention_spec section",
                )
                seen_retention_section_ids.add(section_id)
                metadata_section = interpretation_section_map.get(section_id)
                if metadata_section is None:
                    raise ValueError(
                        "metadata interpretation_contract is missing retention section metadata for "
                        f"'{section_id}'"
                    )
                section["interpretation_variant"] = metadata_section["interpretation_variant"]
                section["layer_support"] = copy.deepcopy(metadata_section["layer_support"])
                if "reason" in metadata_section:
                    section["reason"] = metadata_section["reason"]
                else:
                    section.pop("reason", None)
            extra_section_ids = sorted(
                section_id
                for section_id in interpretation_section_map
                if section_id not in seen_retention_section_ids
            )
            if extra_section_ids:
                raise ValueError(
                    "metadata interpretation_contract.sections contains section ids missing from "
                    "retention_spec.sections: "
                    + ", ".join(extra_section_ids)
                )

    if retention_contract is None:
        merged["retention_contract"] = None
        if not merged["supports_retention"]:
            merged.pop("retention_spec", None)
        if resolved_correctness_contract is None:
            merged.pop("correctness_spec", None)
        return merged

    merged["retention_contract"] = copy.deepcopy(retention_contract)
    merged_retention_spec = copy.deepcopy(merged.get("retention_spec"))
    if not isinstance(merged_retention_spec, dict):
        merged_retention_spec = {}
    merged_retention_spec["retention_type"] = retention_contract["retention_type"]
    if "unit_groups" in retention_contract:
        merged_retention_spec["unit_groups"] = copy.deepcopy(retention_contract["unit_groups"])
    else:
        merged_retention_spec.pop("unit_groups", None)
    merged_retention_spec["checkpoints"] = copy.deepcopy(retention_contract["checkpoints"])
    merged_retention_spec["final_sections"] = copy.deepcopy(retention_contract["final_sections"])
    merged_retention_spec["required_exact_section_headings"] = copy.deepcopy(
        retention_contract["required_exact_section_headings"]
    )

    retention_sections = merged_retention_spec.get("sections")
    retention_contract_sections = retention_contract.get("sections")
    if retention_contract_sections is not None:
        if not isinstance(retention_sections, list):
            raise ValueError(
                "metadata retention_contract.sections requires scenario retention_spec.sections"
            )
        retention_section_map: dict[str, dict[str, Any]] = {}
        for raw_section in retention_contract_sections:
            if not isinstance(raw_section, dict):
                raise ValueError("metadata retention_contract.sections entries must be objects")
            section_id = _require_config_string(
                raw_section,
                "section_id",
                "metadata retention_contract section",
            )
            retention_section_map[section_id] = copy.deepcopy(raw_section)
        seen_retention_section_ids: set[str] = set()
        for section in retention_sections:
            if not isinstance(section, dict):
                raise ValueError("scenario retention_spec.sections entries must be objects")
            section_id = _require_config_string(section, "section_id", "retention_spec section")
            seen_retention_section_ids.add(section_id)
            metadata_section = retention_section_map.get(section_id)
            if metadata_section is None:
                raise ValueError(
                    "metadata retention_contract is missing section retention metadata for "
                    f"'{section_id}'"
                )
            if "retention_type" in metadata_section:
                section["retention_type"] = metadata_section["retention_type"]
            else:
                section.pop("retention_type", None)
            if "unit_groups" in metadata_section:
                section["unit_groups"] = copy.deepcopy(metadata_section["unit_groups"])
            else:
                section.pop("unit_groups", None)
        extra_section_ids = sorted(
            section_id
            for section_id in retention_section_map
            if section_id not in seen_retention_section_ids
        )
        if extra_section_ids:
            raise ValueError(
                "metadata retention_contract.sections contains section ids missing from "
                "scenario retention_spec.sections: "
                + ", ".join(extra_section_ids)
            )

    if section_correctness_contract_migration:
        if not isinstance(retention_sections, list):
            raise ValueError(
                "metadata section_correctness_contracts requires scenario retention_spec.sections"
            )
        if not isinstance(section_correctness_contracts, list):
            raise ValueError(
                "metadata section_correctness_contracts must be a list when section correctness migration is enabled"
            )
        section_correctness_map: dict[str, dict[str, Any]] = {}
        for entry in section_correctness_contracts:
            if not isinstance(entry, dict):
                raise ValueError("metadata section_correctness_contracts entries must be objects")
            section_id = _require_config_string(
                entry,
                "section_id",
                "metadata section_correctness_contracts entry",
            )
            correctness_payload = _require_dict(
                entry,
                "correctness_contract",
                "metadata section_correctness_contracts entry",
            )
            section_correctness_map[section_id] = copy.deepcopy(correctness_payload)

        enabled_correctness_section_ids = {
            section_id
            for section_id, section_metadata in interpretation_section_map.items()
            if isinstance(section_metadata, dict)
            and isinstance(section_metadata.get("layer_support"), dict)
            and section_metadata["layer_support"].get("correctness") == "enabled"
        }
        seen_retention_section_ids: set[str] = set()
        for section in retention_sections:
            if not isinstance(section, dict):
                raise ValueError("scenario retention_spec.sections entries must be objects")
            section_id = _require_config_string(section, "section_id", "retention_spec section")
            seen_retention_section_ids.add(section_id)
            metadata_correctness = section_correctness_map.get(section_id)
            if metadata_correctness is None:
                section.pop("correctness_spec", None)
                if section_id in enabled_correctness_section_ids:
                    raise ValueError(
                        "metadata section_correctness_contracts is missing section correctness metadata for "
                        f"'{section_id}'"
                    )
                continue
            section["correctness_spec"] = copy.deepcopy(metadata_correctness)

        extra_section_ids = sorted(
            section_id
            for section_id in section_correctness_map
            if section_id not in seen_retention_section_ids
        )
        if extra_section_ids:
            raise ValueError(
                "metadata section_correctness_contracts contains unknown section ids: "
                + ", ".join(extra_section_ids)
            )

    if section_ghost_contract_migration:
        if not isinstance(retention_sections, list):
            raise ValueError(
                "metadata section_ghost_contracts requires scenario retention_spec.sections"
            )
        if not isinstance(section_ghost_contracts, list):
            raise ValueError(
                "metadata section_ghost_contracts must be a list when section ghost migration is enabled"
            )
        section_ghost_map: dict[str, dict[str, Any]] = {}
        for entry in section_ghost_contracts:
            if not isinstance(entry, dict):
                raise ValueError("metadata section_ghost_contracts entries must be objects")
            section_id = _require_config_string(
                entry,
                "section_id",
                "metadata section_ghost_contracts entry",
            )
            ghost_payload = _require_dict(
                entry,
                "ghost_contract",
                "metadata section_ghost_contracts entry",
            )
            section_ghost_map[section_id] = copy.deepcopy(ghost_payload)

        enabled_ghost_section_ids = {
            section_id
            for section_id, section_metadata in interpretation_section_map.items()
            if isinstance(section_metadata, dict)
            and isinstance(section_metadata.get("layer_support"), dict)
            and section_metadata["layer_support"].get("ghost") == "enabled"
        }
        seen_retention_section_ids = set()
        for section in retention_sections:
            if not isinstance(section, dict):
                raise ValueError("scenario retention_spec.sections entries must be objects")
            section_id = _require_config_string(section, "section_id", "retention_spec section")
            seen_retention_section_ids.add(section_id)
            metadata_ghost = section_ghost_map.get(section_id)
            if metadata_ghost is None:
                section.pop("ghost_spec", None)
                if section_id in enabled_ghost_section_ids:
                    raise ValueError(
                        "metadata section_ghost_contracts is missing section ghost metadata for "
                        f"'{section_id}'"
                    )
                continue
            section["ghost_spec"] = copy.deepcopy(metadata_ghost)

        extra_section_ids = sorted(
            section_id
            for section_id in section_ghost_map
            if section_id not in seen_retention_section_ids
        )
        if extra_section_ids:
            raise ValueError(
                "metadata section_ghost_contracts contains unknown section ids: "
                + ", ".join(extra_section_ids)
            )

    if resolved_correctness_contract is None:
        merged.pop("correctness_spec", None)
        if isinstance(merged_retention_spec, dict) and merged["scenario_mode"] != "sectioned":
            merged_retention_spec.pop("correctness_spec", None)
    else:
        merged["correctness_spec"] = copy.deepcopy(resolved_correctness_contract)
        if isinstance(merged_retention_spec, dict):
            merged_retention_spec["correctness_spec"] = copy.deepcopy(
                resolved_correctness_contract
            )
    if (
        isinstance(merged_retention_spec, dict)
        and metadata["migration_lock"]["ghost_contract"]
        and merged["scenario_mode"] != "sectioned"
    ):
        if isinstance(ghost_contract, dict):
            merged_retention_spec["ghost_spec"] = copy.deepcopy(ghost_contract)
        else:
            merged_retention_spec.pop("ghost_spec", None)
    merged["retention_spec"] = merged_retention_spec
    return merged


def validate_scenario_config(config: dict[str, Any], expected_scenario_id: str) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_EFFECTIVE_SCENARIO_CONFIG_FIELDS if field not in config)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"scenario config is missing required fields: {joined}")

    validated_config_id = validate_scenario_id(config["scenario_id"])
    if validated_config_id != expected_scenario_id:
        raise ValueError(
            "scenario_id mismatch between filename and scenario config: "
            f"{expected_scenario_id} != {validated_config_id}"
        )

    if "composition_spec" in config and "resolved_from" not in config:
        validate_composition_authoring_config(config, expected_scenario_id)
    else:
        validate_scenario_task_config(config, expected_scenario_id)

    for field_name in (
        "supports_retention",
        "supports_correctness",
        "supports_ghost",
        "supports_temporal_ghost",
        "return_to_origin",
    ):
        if not isinstance(config[field_name], bool):
            raise ValueError(f"{field_name} must be an explicit boolean")

    scenario_mode = config["scenario_mode"]
    if scenario_mode not in ALLOWED_SCENARIO_MODES:
        raise ValueError(
            "scenario_mode must be one of "
            + ", ".join(sorted(ALLOWED_SCENARIO_MODES))
        )
    if not isinstance(config["showcase"], bool):
        raise ValueError("showcase must be an explicit boolean")
    if config["status"] not in ALLOWED_SCENARIO_STATUSES:
        raise ValueError(
            "status must be one of "
            + ", ".join(sorted(ALLOWED_SCENARIO_STATUSES))
        )
    if config["trajectory_readiness"] not in ALLOWED_TRAJECTORY_READINESS_VALUES:
        raise ValueError(
            "trajectory_readiness must be one of "
            + ", ".join(sorted(ALLOWED_TRAJECTORY_READINESS_VALUES))
        )

    retention_spec = config.get("retention_spec")
    if config["supports_retention"]:
        if not isinstance(retention_spec, dict):
            raise ValueError("supports_retention=true requires retention_spec")
        retention_type = retention_spec.get("retention_type")
        if not isinstance(retention_type, str) or not retention_type.strip():
            raise ValueError(
                "supports_retention=true requires retention_spec.retention_type"
            )

    if config["supports_correctness"] and not _has_explicit_correctness_contract(config):
        raise ValueError(
            "supports_correctness=true requires an explicit correctness contract"
        )

    if config["supports_ghost"] and not _has_explicit_ghost_contract(config):
        raise ValueError("supports_ghost=true requires an explicit ghost contract")

    return config


def _has_explicit_correctness_contract(config: dict[str, Any]) -> bool:
    top_level = config.get("correctness_spec")
    if isinstance(top_level, dict):
        return True

    retention_spec = config.get("retention_spec")
    if isinstance(retention_spec, dict) and isinstance(retention_spec.get("correctness_spec"), dict):
        return True

    if config.get("scenario_mode") == "sectioned":
        composition_spec = config.get("composition_spec")
        if isinstance(composition_spec, dict):
            for section in composition_spec.get("sections", []):
                if not isinstance(section, dict):
                    continue
                layer_support = section.get("layer_support")
                contract_imports = section.get("contract_imports")
                if (
                    isinstance(layer_support, dict)
                    and layer_support.get("correctness") != "unsupported"
                    and isinstance(contract_imports, dict)
                    and contract_imports.get("correctness_spec") is True
                ):
                    return True
    return False


def _has_explicit_ghost_contract(config: dict[str, Any]) -> bool:
    top_level = config.get("ghost_spec")
    if isinstance(top_level, dict):
        return True

    retention_spec = config.get("retention_spec")
    if isinstance(retention_spec, dict) and isinstance(retention_spec.get("ghost_spec"), dict):
        return True

    if config.get("scenario_mode") == "sectioned":
        composition_spec = config.get("composition_spec")
        if isinstance(composition_spec, dict):
            for section in composition_spec.get("sections", []):
                if not isinstance(section, dict):
                    continue
                layer_support = section.get("layer_support")
                contract_imports = section.get("contract_imports")
                if (
                    isinstance(layer_support, dict)
                    and layer_support.get("ghost") != "unsupported"
                    and isinstance(contract_imports, dict)
                    and contract_imports.get("ghost_spec") is True
                ):
                    return True
    return False


def load_scenario_config_with_metadata(
    paths: BenchmarkPaths,
    scenario_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validated_id = validate_scenario_id(scenario_id)
    json_path = scenario_json_path(paths, validated_id)
    metadata_path = scenario_metadata_path(paths, validated_id)
    scenario_config = load_json(json_path)
    metadata = load_json(metadata_path)
    if "composition_spec" in scenario_config:
        validate_composition_authoring_config(scenario_config, validated_id)
    else:
        validate_scenario_task_config(scenario_config, validated_id)
    validate_scenario_metadata(metadata, validated_id)
    expected_payload = load_expected_values_file(metadata_path, metadata=metadata)

    metadata_identity = _require_dict(metadata, "identity", "metadata")
    metadata_scenario_id = validate_scenario_id(metadata_identity["scenario_id"])
    scenario_config_id = validate_scenario_id(scenario_config["scenario_id"])
    if metadata_scenario_id != scenario_config_id:
        raise ValueError(
            "scenario_id mismatch between scenario config and scenario metadata: "
            f"{scenario_config_id} != {metadata_scenario_id}"
        )

    merged_config = merge_scenario_with_metadata(
        scenario_config,
        metadata,
        expected_payload=expected_payload,
    )
    validate_scenario_config(merged_config, validated_id)
    return scenario_config, metadata, merged_config


def build_sectioned_reference_composition_validation_result(
    paths: BenchmarkPaths,
    *,
    scenario_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scenario_id": scenario_id,
        "valid": False,
        "warnings": [],
        "errors": [],
        "sections": [],
    }
    errors: list[str] = result["errors"]
    warnings: list[str] = result["warnings"]

    scenario_mode = config.get("scenario_mode")
    result["scenario_mode"] = scenario_mode
    if scenario_mode != "sectioned":
        errors.append("scenario_mode must be exactly 'sectioned'")

    composition_spec = config.get("composition_spec")
    if not isinstance(composition_spec, dict):
        errors.append("composition_spec must be an object")
        return result

    composition_type = composition_spec.get("composition_type")
    resolution_policy = composition_spec.get("resolution_policy")
    namespace_format = composition_spec.get("namespace_format")
    result["composition_type"] = composition_type
    result["resolution_policy"] = resolution_policy
    result["namespace_format"] = namespace_format

    if composition_type != SECTIONED_REFERENCE_COMPOSITION_TYPE:
        errors.append(
            "composition_spec.composition_type must be exactly "
            f"'{SECTIONED_REFERENCE_COMPOSITION_TYPE}'"
        )
    if resolution_policy != SECTIONED_REFERENCE_RESOLUTION_POLICY:
        errors.append(
            "composition_spec.resolution_policy must be exactly "
            f"'{SECTIONED_REFERENCE_RESOLUTION_POLICY}'"
        )
    if not isinstance(namespace_format, str) or not namespace_format.strip():
        errors.append("composition_spec.namespace_format must be a non-empty string")

    sections = composition_spec.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("composition_spec.sections must be a non-empty list")
        return result

    seen_section_ids: set[str] = set()
    total_max_percent = Decimal("0")

    for index, section in enumerate(sections, start=1):
        section_result: dict[str, Any] = {
            "index": index,
            "valid": False,
            "errors": [],
        }
        result["sections"].append(section_result)
        section_errors: list[str] = section_result["errors"]

        if not isinstance(section, dict):
            section_errors.append("section must be an object")
            errors.append(f"composition_spec.sections[{index}] must be an object")
            continue

        for field_name in REQUIRED_COMPOSITION_SECTION_FIELDS:
            section_result[field_name] = section.get(field_name)
            if field_name not in section:
                section_errors.append(f"missing field '{field_name}'")

        section_id = section.get("section_id")
        if not isinstance(section_id, str) or not section_id.strip():
            section_errors.append("section_id must be a non-empty string")
            normalized_section_id = f"<invalid:{index}>"
        else:
            normalized_section_id = section_id.strip()
            section_result["section_id"] = normalized_section_id
            if normalized_section_id in seen_section_ids:
                section_errors.append(f"duplicate section_id '{normalized_section_id}'")
            else:
                seen_section_ids.add(normalized_section_id)

        section_label = section.get("section_label")
        if not isinstance(section_label, str) or not section_label.strip():
            section_errors.append("section_label must be a non-empty string")

        source_scenario_id = section.get("source_scenario_id")
        if not isinstance(source_scenario_id, str) or not source_scenario_id.strip():
            section_errors.append("source_scenario_id must be a non-empty string")
            normalized_source_id = None
        else:
            normalized_source_id = source_scenario_id.strip()
            section_result["source_scenario_id"] = normalized_source_id
            if normalized_source_id == scenario_id:
                section_errors.append("source_scenario_id must not self-reference the composite scenario")

        include_steps = section.get("include_steps")
        normalized_include_steps: list[str] = []
        if not isinstance(include_steps, list) or not include_steps:
            section_errors.append("include_steps must be a non-empty list")
        else:
            seen_include_steps: set[str] = set()
            for step_index, step_id in enumerate(include_steps, start=1):
                if not isinstance(step_id, str) or not step_id.strip():
                    section_errors.append(
                        f"include_steps[{step_index}] must be a non-empty string"
                    )
                    continue
                normalized_step_id = step_id.strip()
                if normalized_step_id in seen_include_steps:
                    section_errors.append(
                        f"include_steps contains duplicate step_id '{normalized_step_id}'"
                    )
                    continue
                seen_include_steps.add(normalized_step_id)
                normalized_include_steps.append(normalized_step_id)
        section_result["include_steps"] = normalized_include_steps

        max_percent = section.get("max_percent")
        try:
            if isinstance(max_percent, bool):
                raise InvalidOperation
            normalized_max_percent = Decimal(str(max_percent))
        except (InvalidOperation, TypeError):
            section_errors.append("max_percent must be numeric")
        else:
            if normalized_max_percent <= 0:
                section_errors.append("max_percent must be greater than zero")
            else:
                total_max_percent += normalized_max_percent
                section_result["max_percent"] = float(normalized_max_percent)

        interpretation_variant = section.get("interpretation_variant")
        if not isinstance(interpretation_variant, str) or not interpretation_variant.strip():
            section_errors.append("interpretation_variant must be a non-empty string")

        layer_support = section.get("layer_support")
        if not isinstance(layer_support, dict):
            section_errors.append("layer_support must be an object")
        else:
            normalized_layer_support: dict[str, str] = {}
            for support_key in ("retention", "correctness", "ghost"):
                support_value = layer_support.get(support_key)
                if support_value not in ALLOWED_LAYER_SUPPORT_VALUES:
                    section_errors.append(
                        f"layer_support.{support_key} must be one of "
                        f"{sorted(ALLOWED_LAYER_SUPPORT_VALUES)}"
                    )
                else:
                    normalized_layer_support[support_key] = str(support_value)
            if len(normalized_layer_support) == 3:
                section_result["layer_support"] = normalized_layer_support

        return_to_origin = section.get("return_to_origin")
        if not isinstance(return_to_origin, bool):
            section_errors.append("return_to_origin must be an explicit boolean")
        else:
            section_result["return_to_origin"] = return_to_origin

        contract_imports = section.get("contract_imports")
        if not isinstance(contract_imports, dict):
            section_errors.append("contract_imports must be an object")
        else:
            normalized_contract_imports: dict[str, bool] = {}
            extra_keys = sorted(
                key for key in contract_imports if key not in REQUIRED_CONTRACT_IMPORT_FIELDS
            )
            missing_keys = sorted(
                key for key in REQUIRED_CONTRACT_IMPORT_FIELDS if key not in contract_imports
            )
            if missing_keys:
                section_errors.append(
                    "contract_imports is missing required keys: "
                    + ", ".join(missing_keys)
                )
            if extra_keys:
                section_errors.append(
                    "contract_imports contains unsupported keys: "
                    + ", ".join(extra_keys)
                )
            for field_name in REQUIRED_CONTRACT_IMPORT_FIELDS:
                value = contract_imports.get(field_name)
                if field_name in contract_imports and not isinstance(value, bool):
                    section_errors.append(
                        f"contract_imports.{field_name} must be a boolean"
                    )
                elif isinstance(value, bool):
                    normalized_contract_imports[field_name] = value
            if (
                not missing_keys
                and not extra_keys
                and len(normalized_contract_imports) == len(REQUIRED_CONTRACT_IMPORT_FIELDS)
            ):
                section_result["contract_imports"] = normalized_contract_imports

        if normalized_source_id is not None and normalized_include_steps:
            source_json_path = scenario_json_path(paths, normalized_source_id)
            source_markdown_path = scenario_markdown_path(paths, normalized_source_id)
            source_metadata_path = scenario_metadata_path(paths, normalized_source_id)
            if not source_json_path.exists() or not source_markdown_path.exists() or not source_metadata_path.exists():
                section_errors.append(
                    f"source_scenario_id '{normalized_source_id}' does not resolve to a complete scenario bundle"
                )
            else:
                try:
                    _, _, source_config = load_scenario_config_with_metadata(
                        paths,
                        normalized_source_id,
                    )
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
                    section_errors.append(
                        f"source_scenario_id '{normalized_source_id}' is invalid: {exc}"
                    )
                else:
                    source_retention_spec = source_config.get("retention_spec")
                    if not isinstance(source_retention_spec, dict):
                        section_errors.append(
                            f"source_scenario_id '{normalized_source_id}' must declare retention_spec"
                        )
                        source_retention_spec = None
                    source_step_ids = {
                        str(step["step_id"]).strip()
                        for step in source_config["steps"]
                        if isinstance(step, dict) and "step_id" in step
                    }
                    missing_step_ids = [
                        step_id
                        for step_id in normalized_include_steps
                        if step_id not in source_step_ids
                    ]
                    if missing_step_ids:
                        section_errors.append(
                            "include_steps contains unknown source step ids: "
                            + ", ".join(missing_step_ids)
                        )
                    if isinstance(source_retention_spec, dict):
                        missing_imported_fields = [
                            field_name
                            for field_name, should_import in section_result.get(
                                "contract_imports",
                                {},
                            ).items()
                            if should_import and field_name not in source_retention_spec
                        ]
                        if missing_imported_fields:
                            section_errors.append(
                                "contract_imports requests missing source retention fields: "
                                + ", ".join(missing_imported_fields)
                            )

        if section_errors:
            errors.append(
                f"composition_spec section '{normalized_section_id}' is invalid: "
                + "; ".join(section_errors)
            )
        else:
            section_result["valid"] = True

    if total_max_percent != Decimal("100"):
        errors.append(
            "composition_spec section max_percent total must equal exactly 100"
        )

    if not errors:
        result["valid"] = True
    else:
        warnings.append("composition_spec marked invalid")

    return result


def validate_sectioned_reference_composition(
    paths: BenchmarkPaths,
    *,
    scenario_id: str,
    config: dict[str, Any],
    strict: bool,
) -> dict[str, Any]:
    result = build_sectioned_reference_composition_validation_result(
        paths,
        scenario_id=scenario_id,
        config=config,
    )
    if result["valid"]:
        return result
    if strict:
        raise ValueError(
            f"invalid composition_spec for scenario '{scenario_id}': "
            + " | ".join(result["errors"])
        )
    return result


def resolve_sectioned_reference_scenario(
    paths: BenchmarkPaths,
    *,
    scenario_id: str,
    config: dict[str, Any],
    strict: bool,
) -> dict[str, Any]:
    validation_result = validate_sectioned_reference_composition(
        paths,
        scenario_id=scenario_id,
        config=config,
        strict=strict,
    )
    if not validation_result["valid"]:
        return {
            "scenario_id": scenario_id,
            "valid": False,
            "validation": validation_result,
        }

    composition_spec = _require_dict(config, "composition_spec", "scenario config")
    namespace_format = _require_config_string(
        composition_spec,
        "namespace_format",
        "composition_spec",
    )
    composite_retention_spec = _require_dict(config, "retention_spec", "scenario config")
    raw_composite_sections = {
        _require_config_string(section, "section_id", "retention_spec section"): section
        for section in _require_list(
            composite_retention_spec,
            "sections",
            "scenario retention_spec",
        )
        if isinstance(section, dict)
    }
    resolved_sections: list[dict[str, Any]] = []
    flat_steps: list[dict[str, Any]] = []
    execution_flow: list[str] = []

    for section in _require_list(composition_spec, "sections", "composition_spec"):
        if not isinstance(section, dict):
            raise ValueError("composition_spec.sections entries must be objects")
        section_id = _require_config_string(section, "section_id", "composition section")
        section_label = _require_config_string(section, "section_label", "composition section")
        source_scenario_id = _require_config_string(
            section,
            "source_scenario_id",
            "composition section",
        )
        include_steps = _require_config_string_list(
            section,
            "include_steps",
            "composition section",
        )
        _, _, source_config = load_scenario_config_with_metadata(
            paths,
            source_scenario_id,
        )
        source_retention_spec = _require_dict(
            source_config,
            "retention_spec",
            f"source scenario '{source_scenario_id}'",
        )
        source_step_map = {
            _require_config_string(step, "step_id", "source step"): step
            for step in _require_list(source_config, "steps", f"source scenario '{source_scenario_id}'")
            if isinstance(step, dict)
        }

        contract_imports = _require_dict(section, "contract_imports", "composition section")
        resolved_contract: dict[str, Any] = {}
        for field_name in REQUIRED_CONTRACT_IMPORT_FIELDS:
            should_import = contract_imports.get(field_name)
            if not isinstance(should_import, bool):
                raise ValueError(
                    f"composition section '{section_id}' contract_imports.{field_name} must be boolean"
                )
            if should_import:
                if field_name not in source_retention_spec:
                    raise ValueError(
                        f"composition section '{section_id}' requested missing field '{field_name}' "
                        f"from source scenario '{source_scenario_id}'"
                    )
                resolved_contract[field_name] = copy.deepcopy(source_retention_spec[field_name])

        resolved_steps: list[dict[str, Any]] = []
        seen_resolved_step_ids: set[str] = set()
        for source_step_id in include_steps:
            source_step = source_step_map[source_step_id]
            resolved_step_id = namespace_format.format(
                section_id=section_id,
                source_step_id=source_step_id,
            )
            if not isinstance(resolved_step_id, str) or not resolved_step_id.strip():
                raise ValueError(
                    f"composition section '{section_id}' produced an invalid resolved step id"
                )
            normalized_resolved_step_id = resolved_step_id.strip()
            if normalized_resolved_step_id in seen_resolved_step_ids:
                raise ValueError(
                    f"composition section '{section_id}' produced duplicate resolved step id "
                    f"'{normalized_resolved_step_id}'"
                )
            seen_resolved_step_ids.add(normalized_resolved_step_id)
            resolved_step = {
                "step_id": normalized_resolved_step_id,
                "resolved_step_id": normalized_resolved_step_id,
                "source_step_id": source_step_id,
                "source_scenario_id": source_scenario_id,
                "section_id": section_id,
                "instruction": _require_config_string(
                    source_step,
                    "instruction",
                    "source step",
                ),
            }
            resolved_steps.append(resolved_step)
            flat_steps.append(copy.deepcopy(resolved_step))
            execution_flow.append(normalized_resolved_step_id)

        source_section_spec_ref = section.get("section_spec_ref")
        raw_section = raw_composite_sections.get(section_id)
        if not isinstance(raw_section, dict):
            raise ValueError(
                f"composite retention_spec is missing raw section metadata for '{section_id}'"
            )
        resolved_retention_type = resolved_contract.get("retention_type")
        if not isinstance(resolved_retention_type, str) or not resolved_retention_type.strip():
            raise ValueError(
                f"composition section '{section_id}' must resolve an explicit retention_type"
            )

        resolved_sections.append(
            {
                "section_id": section_id,
                "section_label": section_label,
                "section_heading": _require_config_string(
                    raw_section,
                    "section_heading",
                    "retention_spec section",
                ),
                "source_scenario_id": source_scenario_id,
                "include_steps": include_steps,
                "max_percent": _require_config_number(
                    section,
                    "max_percent",
                    "composition section",
                ),
                "interpretation_variant": _require_config_string(
                    section,
                    "interpretation_variant",
                    "composition section",
                ),
                "layer_support": copy.deepcopy(
                    _require_dict(section, "layer_support", "composition section")
                ),
                "return_to_origin": section["return_to_origin"],
                "section_spec_ref": (
                    source_section_spec_ref
                    if isinstance(source_section_spec_ref, str) and source_section_spec_ref.strip()
                    else source_scenario_id
                ),
                "retention_type": resolved_retention_type,
                "reason": section.get("reason"),
                "unit_groups": copy.deepcopy(resolved_contract.get("unit_groups")),
                "ghost_spec": copy.deepcopy(resolved_contract.get("ghost_spec")),
                "correctness_spec": copy.deepcopy(resolved_contract.get("correctness_spec")),
                "resolved_contract": resolved_contract,
                "resolved_steps": resolved_steps,
            }
        )

    resolved_retention_spec = copy.deepcopy(config.get("retention_spec"))
    if isinstance(resolved_retention_spec, dict):
        resolved_retention_spec["resolved_sections"] = [
            {
                "section_id": section["section_id"],
                "section_label": section["section_label"],
                "section_heading": section["section_heading"],
                "source_scenario_id": section["source_scenario_id"],
                "include_steps": list(section["include_steps"]),
                "max_percent": section["max_percent"],
                "interpretation_variant": section["interpretation_variant"],
                "layer_support": copy.deepcopy(section["layer_support"]),
                "return_to_origin": section["return_to_origin"],
                "section_spec_ref": section["section_spec_ref"],
                "retention_type": section["retention_type"],
                "reason": section["reason"],
                "unit_groups": copy.deepcopy(section["unit_groups"]),
                "ghost_spec": copy.deepcopy(section["ghost_spec"]),
                "correctness_spec": copy.deepcopy(section["correctness_spec"]),
                "resolved_contract": copy.deepcopy(section["resolved_contract"]),
                "resolved_steps": copy.deepcopy(section["resolved_steps"]),
            }
            for section in resolved_sections
        ]

    resolved_config = copy.deepcopy(config)
    resolved_config["resolved_from"] = scenario_id
    resolved_config["resolved_sections"] = resolved_sections
    resolved_config["steps"] = flat_steps
    resolved_config["execution_flow"] = execution_flow
    if isinstance(resolved_retention_spec, dict):
        resolved_config["retention_spec"] = resolved_retention_spec
    resolved_config[RESOLVED_SCENARIO_ARTIFACT_KEY] = {
        "scenario_id": scenario_id,
        "resolved_from": scenario_id,
        "composition_spec": copy.deepcopy(config["composition_spec"]),
        "interpretation_spec": copy.deepcopy(config.get("interpretation_spec")),
        "retention_spec": copy.deepcopy(resolved_retention_spec),
        "resolved_sections": copy.deepcopy(resolved_sections),
        "steps": copy.deepcopy(flat_steps),
        "execution_flow": list(execution_flow),
    }
    return {
        "scenario_id": scenario_id,
        "valid": True,
        "validation": validation_result,
        "resolved_config": resolved_config,
    }


def _require_dict(data: dict[str, Any], field_name: str, label: str) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{label} field '{field_name}' must be an object")
    return value


def _require_list(data: dict[str, Any], field_name: str, label: str) -> list[Any]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{label} field '{field_name}' must be a list")
    return value


def _require_config_string(data: dict[str, Any], field_name: str, label: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} field '{field_name}' must be a non-empty string")
    return value.strip()


def _require_config_string_list(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> list[str]:
    value = _require_list(data, field_name, label)
    normalized: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"{label} field '{field_name}' entry #{index} must be a non-empty string"
            )
        normalized.append(item.strip())
    return normalized


def _require_config_number(data: dict[str, Any], field_name: str, label: str) -> float:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} field '{field_name}' must be numeric")
    return float(value)


def load_benchmark_scenario(paths: BenchmarkPaths, scenario_id: str) -> BenchmarkScenario:
    validated_id = validate_scenario_id(scenario_id)

    md_path = scenario_markdown_path(paths, validated_id)
    json_path = scenario_json_path(paths, validated_id)
    metadata_path = scenario_metadata_path(paths, validated_id)

    markdown_text = load_text(md_path)
    _, _, config = load_scenario_config_with_metadata(paths, validated_id)
    if "composition_spec" in config:
        resolution_result = resolve_sectioned_reference_scenario(
            paths,
            scenario_id=validated_id,
            config=config,
            strict=True,
        )
        if not resolution_result["valid"]:
            raise ValueError(
                f"invalid composition resolution for scenario '{validated_id}'"
            )
        config = resolution_result["resolved_config"]
        validate_scenario_config(config, validated_id)

    return BenchmarkScenario(
        scenario_id=validated_id,
        markdown_path=md_path,
        json_path=json_path,
        metadata_path=metadata_path,
        markdown_text=markdown_text,
        config=config,
    )


def build_resolved_execution_artifact_payload(
    paths: BenchmarkPaths,
    *,
    scenario_id: str,
) -> dict[str, Any] | None:
    _, _, config = load_scenario_config_with_metadata(paths, scenario_id)
    if "composition_spec" not in config:
        return None
    resolution_result = resolve_sectioned_reference_scenario(
        paths,
        scenario_id=scenario_id,
        config=config,
        strict=True,
    )
    if not resolution_result["valid"]:
        raise ValueError(
            f"invalid composition resolution for scenario '{scenario_id}'"
        )
    resolved_config = resolution_result["resolved_config"]
    payload = resolved_config.get(RESOLVED_SCENARIO_ARTIFACT_KEY)
    if not isinstance(payload, dict):
        raise ValueError(
            f"resolved scenario '{scenario_id}' is missing resolved artifact payload"
        )
    return copy.deepcopy(payload)


def list_available_scenarios(paths: BenchmarkPaths) -> list[str]:
    scenario_ids: set[str] = set()

    for path in paths.scenarios_root.glob("*.md"):
        scenario_ids.add(path.stem)

    for path in paths.scenarios_root.glob("*.json"):
        if path.name.endswith(".metadata.json"):
            continue
        scenario_ids.add(path.stem)

    valid_ids = []
    for scenario_id in sorted(scenario_ids):
        md_exists = scenario_markdown_path(paths, scenario_id).exists()
        json_exists = scenario_json_path(paths, scenario_id).exists()
        metadata_exists = scenario_metadata_path(paths, scenario_id).exists()
        if md_exists and json_exists and metadata_exists:
            valid_ids.append(scenario_id)

    return valid_ids


def load_all_benchmark_scenarios(paths: BenchmarkPaths) -> list[BenchmarkScenario]:
    return [
        load_benchmark_scenario(paths, scenario_id)
        for scenario_id in list_available_scenarios(paths)
    ]


__all__ = [
    "BenchmarkScenario",
    "ALLOWED_LAYER_SUPPORT_VALUES",
    "ALLOWED_TRAJECTORY_READINESS_VALUES",
    "SECTIONED_REFERENCE_COMPOSITION_TYPE",
    "SECTIONED_REFERENCE_RESOLUTION_POLICY",
    "REQUIRED_EFFECTIVE_SCENARIO_CONFIG_FIELDS",
    "REQUIRED_SCENARIO_METADATA_FIELDS",
    "REQUIRED_SCENARIO_TASK_FIELDS",
    "REQUIRED_COMPOSITION_SECTION_FIELDS",
    "REQUIRED_CONTRACT_IMPORT_FIELDS",
    "build_resolved_execution_artifact_payload",
    "build_sectioned_reference_composition_validation_result",
    "list_available_scenarios",
    "load_all_benchmark_scenarios",
    "load_benchmark_scenario",
    "load_scenario_config_with_metadata",
    "load_json",
    "load_text",
    "merge_scenario_with_metadata",
    "resolve_sectioned_reference_scenario",
    "validate_sectioned_reference_composition",
    "validate_scenario_config",
    "validate_scenario_metadata",
    "validate_scenario_task_config",
]
