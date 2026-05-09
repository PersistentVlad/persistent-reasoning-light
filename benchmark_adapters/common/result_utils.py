# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark result utilities for Persistent Reasoning Light.

This module defines deterministic helpers for building, validating, saving,
and loading structured benchmark result artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .benchmark_modes import validate_benchmark_mode
from .benchmark_paths import (
    LEGACY_RESULT_JSON_SUFFIX,
    LEGACY_TRACE_LOG_SUFFIX,
    RESULT_JSON_SUFFIX,
    TRACE_LOG_SUFFIX,
    validate_scenario_id,
)

REQUIRED_NUMERIC_RESULT_METRIC_NAMES = (
    "reasoning_drift_rate",
    "replanning_events",
    "context_loss_events",
    "plan_retention_rate",
    "rediscovery_rate",
    "knowledge_retention_rate",
    "context_utilization_rate",
    "reuse_rate",
    "context_growth_rate",
    "token_efficiency",
    "token_reduction_ratio",
    "memory_compression_ratio",
    "retrieval_precision",
    "files_read_per_query",
    "tokens_read_per_query",
    "time_to_context_ms",
    "structural_integrity_score",
    "controlled_mutations_ratio",
    "artifact_suggested_count",
    "execution_time_ms",
    "steps_to_completion",
)

REQUIRED_BOOLEAN_RESULT_METRIC_NAMES = (
    "task_success",
)


def ensure_numeric_metric(value: Any, metric_name: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"metric '{metric_name}' must be numeric")
    return value


def ensure_boolean_metric(value: Any, metric_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"metric '{metric_name}' must be boolean")
    return value


def validate_result_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("result timestamp must be a string")

    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid result timestamp: {value}") from exc

    return value


def validate_adapter_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("adapter must be a string")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError("adapter must not be empty")
    if cleaned != value:
        raise ValueError("adapter must not contain surrounding whitespace")

    return cleaned


def validate_required_section(
    result: dict[str, Any],
    section_name: str,
    required_keys: set[str],
) -> dict[str, Any]:
    section = result.get(section_name)
    if not isinstance(section, dict):
        raise ValueError(f"{section_name} section must be an object")

    missing = sorted(key for key in required_keys if key not in section)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{section_name} is missing required fields: {joined}")

    return section


def validate_result_schema(result: dict[str, Any]) -> dict[str, Any]:
    required_sections = {
        "metadata",
        "reasoning_stability",
        "knowledge_persistence",
        "memory_efficiency",
        "retrieval_metrics",
        "persistence_integrity",
        "task_outcome",
    }

    missing_sections = sorted(section for section in required_sections if section not in result)
    if missing_sections:
        joined = ", ".join(missing_sections)
        raise ValueError(f"result json is missing required sections: {joined}")

    metadata = result["metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("metadata section must be an object")

    required_metadata = {"scenario_id", "adapter", "mode"}
    optional_metadata = {"timestamp"}

    missing_metadata = sorted(key for key in required_metadata if key not in metadata)
    if missing_metadata:
        joined = ", ".join(missing_metadata)
        raise ValueError(f"metadata is missing required fields: {joined}")

    unexpected_metadata = sorted(
        key for key in metadata if key not in required_metadata and key not in optional_metadata
    )
    if unexpected_metadata:
        joined = ", ".join(unexpected_metadata)
        raise ValueError(f"metadata contains unexpected fields: {joined}")

    metadata["scenario_id"] = validate_scenario_id(metadata["scenario_id"])
    metadata["adapter"] = validate_adapter_name(metadata["adapter"])
    metadata["mode"] = validate_benchmark_mode(metadata["mode"])

    if "timestamp" in metadata:
        metadata["timestamp"] = validate_result_timestamp(metadata["timestamp"])

    reasoning_stability = validate_required_section(
        result,
        "reasoning_stability",
        {
            "reasoning_drift_rate",
            "replanning_events",
            "context_loss_events",
            "plan_retention_rate",
        },
    )
    ensure_numeric_metric(reasoning_stability["reasoning_drift_rate"], "reasoning_drift_rate")
    ensure_numeric_metric(reasoning_stability["replanning_events"], "replanning_events")
    ensure_numeric_metric(reasoning_stability["context_loss_events"], "context_loss_events")
    ensure_numeric_metric(reasoning_stability["plan_retention_rate"], "plan_retention_rate")

    knowledge_persistence = validate_required_section(
        result,
        "knowledge_persistence",
        {
            "rediscovery_rate",
            "knowledge_retention_rate",
        },
    )
    ensure_numeric_metric(knowledge_persistence["rediscovery_rate"], "rediscovery_rate")
    ensure_numeric_metric(
        knowledge_persistence["knowledge_retention_rate"],
        "knowledge_retention_rate",
    )
    if "context_utilization_rate" in knowledge_persistence:
        ensure_numeric_metric(
            knowledge_persistence["context_utilization_rate"],
            "context_utilization_rate",
        )
    if "reuse_rate" in knowledge_persistence:
        ensure_numeric_metric(
            knowledge_persistence["reuse_rate"],
            "reuse_rate",
        )

    memory_efficiency = validate_required_section(
        result,
        "memory_efficiency",
        {
            "context_growth_rate",
            "token_efficiency",
            "token_reduction_ratio",
            "memory_compression_ratio",
        },
    )
    ensure_numeric_metric(memory_efficiency["context_growth_rate"], "context_growth_rate")
    ensure_numeric_metric(memory_efficiency["token_efficiency"], "token_efficiency")
    ensure_numeric_metric(memory_efficiency["token_reduction_ratio"], "token_reduction_ratio")
    ensure_numeric_metric(
        memory_efficiency["memory_compression_ratio"],
        "memory_compression_ratio",
    )

    retrieval_metrics = validate_required_section(
        result,
        "retrieval_metrics",
        {
            "retrieval_precision",
            "files_read_per_query",
            "tokens_read_per_query",
            "time_to_context_ms",
        },
    )
    ensure_numeric_metric(retrieval_metrics["retrieval_precision"], "retrieval_precision")
    ensure_numeric_metric(retrieval_metrics["files_read_per_query"], "files_read_per_query")
    ensure_numeric_metric(retrieval_metrics["tokens_read_per_query"], "tokens_read_per_query")
    ensure_numeric_metric(retrieval_metrics["time_to_context_ms"], "time_to_context_ms")

    persistence_integrity = validate_required_section(
        result,
        "persistence_integrity",
        {
            "structural_integrity_score",
            "controlled_mutations_ratio",
        },
    )
    ensure_numeric_metric(
        persistence_integrity["structural_integrity_score"],
        "structural_integrity_score",
    )
    ensure_numeric_metric(
        persistence_integrity["controlled_mutations_ratio"],
        "controlled_mutations_ratio",
    )
    if "artifact_suggested_count" in persistence_integrity:
        ensure_numeric_metric(
            persistence_integrity["artifact_suggested_count"],
            "artifact_suggested_count",
        )

    task_outcome = validate_required_section(
        result,
        "task_outcome",
        {
            "execution_time_ms",
            "steps_to_completion",
            "task_success",
        },
    )
    ensure_numeric_metric(task_outcome["execution_time_ms"], "execution_time_ms")
    ensure_numeric_metric(task_outcome["steps_to_completion"], "steps_to_completion")
    ensure_boolean_metric(task_outcome["task_success"], "task_success")

    return result


def build_result_json(
    *,
    scenario_id: str,
    adapter: str,
    mode: str,
    reasoning_drift_rate: float,
    replanning_events: int,
    context_loss_events: int,
    plan_retention_rate: float,
    rediscovery_rate: float,
    knowledge_retention_rate: float,
    context_growth_rate: float,
    token_efficiency: float,
    token_reduction_ratio: float,
    memory_compression_ratio: float,
    retrieval_precision: float,
    files_read_per_query: int,
    tokens_read_per_query: int,
    time_to_context_ms: int,
    structural_integrity_score: float,
    controlled_mutations_ratio: float,
    execution_time_ms: int,
    steps_to_completion: int,
    task_success: bool,
    context_utilization_rate: float = 0.0,
    reuse_rate: float = 0.0,
    artifact_suggested_count: int = 0,
    timestamp: str | None = None,
) -> dict[str, Any]:
    validated_scenario_id = validate_scenario_id(scenario_id)
    validated_adapter = validate_adapter_name(adapter)
    validated_mode = validate_benchmark_mode(mode)

    metadata: dict[str, object] = {
        "scenario_id": validated_scenario_id,
        "adapter": validated_adapter,
        "mode": validated_mode,
    }

    if timestamp is not None:
        metadata["timestamp"] = validate_result_timestamp(timestamp)

    result = {
        "metadata": metadata,
        "reasoning_stability": {
            "reasoning_drift_rate": reasoning_drift_rate,
            "replanning_events": replanning_events,
            "context_loss_events": context_loss_events,
            "plan_retention_rate": plan_retention_rate,
        },
        "knowledge_persistence": {
            "rediscovery_rate": rediscovery_rate,
            "knowledge_retention_rate": knowledge_retention_rate,
            "context_utilization_rate": context_utilization_rate,
            "reuse_rate": reuse_rate,
        },
        "memory_efficiency": {
            "context_growth_rate": context_growth_rate,
            "token_efficiency": token_efficiency,
            "token_reduction_ratio": token_reduction_ratio,
            "memory_compression_ratio": memory_compression_ratio,
        },
        "retrieval_metrics": {
            "retrieval_precision": retrieval_precision,
            "files_read_per_query": files_read_per_query,
            "tokens_read_per_query": tokens_read_per_query,
            "time_to_context_ms": time_to_context_ms,
        },
        "persistence_integrity": {
            "structural_integrity_score": structural_integrity_score,
            "controlled_mutations_ratio": controlled_mutations_ratio,
            "artifact_suggested_count": artifact_suggested_count,
        },
        "task_outcome": {
            "execution_time_ms": execution_time_ms,
            "steps_to_completion": steps_to_completion,
            "task_success": task_success,
        },
    }

    validate_result_schema(result)
    return result


def ensure_output_path_writable(
    path: Path,
    *,
    overwrite: bool,
    artifact_label: str,
) -> None:
    if not path.exists():
        return
    if not path.is_file():
        raise ValueError(f"{artifact_label} path is not a file: {path}")
    if not overwrite:
        raise FileExistsError(
            f"{artifact_label} already exists; explicit overwrite is required: {path}"
        )


def save_result_json(
    path: Path,
    result: dict[str, Any],
    *,
    overwrite: bool = False,
) -> None:
    validate_result_schema(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label="result json",
    )
    _remove_legacy_artifact(
        path,
        canonical_suffix=RESULT_JSON_SUFFIX,
        legacy_suffix=LEGACY_RESULT_JSON_SUFFIX,
    )

    with path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def save_raw_log(path: Path, text: str, *, overwrite: bool = False) -> None:
    if not isinstance(text, str):
        raise ValueError("raw log text must be a string")

    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label="trace log",
    )
    _remove_legacy_artifact(
        path,
        canonical_suffix=TRACE_LOG_SUFFIX,
        legacy_suffix=LEGACY_TRACE_LOG_SUFFIX,
    )
    path.write_text(text, encoding="utf-8")


def load_result_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"result json not found: {path}")
    if not path.is_file():
        raise ValueError(f"result json path is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        result = json.load(handle)

    if not isinstance(result, dict):
        raise ValueError(f"result json must contain an object: {path}")

    return validate_result_schema(result)


def _remove_legacy_artifact(
    path: Path,
    *,
    canonical_suffix: str,
    legacy_suffix: str,
) -> None:
    filename = path.name
    if not filename.endswith(canonical_suffix):
        return

    legacy_name = filename[: -len(canonical_suffix)] + legacy_suffix
    legacy_path = path.with_name(legacy_name)
    if not legacy_path.exists():
        return
    if not legacy_path.is_file():
        raise ValueError(f"legacy artifact path is not a file: {legacy_path}")

    legacy_path.unlink()


__all__ = [
    "build_result_json",
    "ensure_output_path_writable",
    "ensure_boolean_metric",
    "ensure_numeric_metric",
    "load_result_json",
    "REQUIRED_BOOLEAN_RESULT_METRIC_NAMES",
    "REQUIRED_NUMERIC_RESULT_METRIC_NAMES",
    "save_raw_log",
    "save_result_json",
    "validate_adapter_name",
    "validate_required_section",
    "validate_result_schema",
    "validate_result_timestamp",
]
