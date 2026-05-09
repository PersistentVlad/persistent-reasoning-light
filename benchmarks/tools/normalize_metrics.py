# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Normalize benchmark result metrics for comparative visualization.

This module converts raw benchmark metrics from *.result.json artifacts into
normalized 0..1 values suitable for radar charts, summary scoring, and other
comparative visual layers.

It does not redefine raw benchmark truth.
Canonical raw metrics remain stored in result.json artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
METRICS_DIR = TOOLS_DIR / "metrics"


# Default normalization thresholds for comparative visualization.
# These values are heuristic PoC defaults for radar/scoring layers and do not
# redefine the canonical raw benchmark metrics stored in result.json.
DEFAULT_NORMALIZATION_CONFIG: dict[str, dict[str, float]] = {
    "reasoning_drift_rate": {
        "bad_threshold": 1.0,
        "excellent_threshold": 0.0,
    },
    "replanning_events": {
        "bad_threshold": 10.0,
        "excellent_threshold": 0.0,
    },
    "context_loss_events": {
        "bad_threshold": 10.0,
        "excellent_threshold": 0.0,
    },
    "plan_retention_rate": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "rediscovery_rate": {
        "bad_threshold": 1.0,
        "excellent_threshold": 0.0,
    },
    "knowledge_retention_rate": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "context_utilization_rate": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "reuse_rate": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "context_growth_rate": {
        "bad_threshold": 1.0,
        "excellent_threshold": 0.0,
    },
    "token_efficiency": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "token_reduction_ratio": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "memory_compression_ratio": {
        "bad_threshold": 1.0,
        "excellent_threshold": 10.0,
    },
    "retrieval_precision": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "files_read_per_query": {
        "bad_threshold": 20.0,
        "excellent_threshold": 0.0,
    },
    "tokens_read_per_query": {
        "bad_threshold": 20000.0,
        "excellent_threshold": 0.0,
    },
    "time_to_context_ms": {
        "bad_threshold": 10000.0,
        "excellent_threshold": 0.0,
    },
    "structural_integrity_score": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "controlled_mutations_ratio": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
    "artifact_suggested_count": {
        "bad_threshold": 0.0,
        "excellent_threshold": 5.0,
    },
    "execution_time_ms": {
        "bad_threshold": 600000.0,
        "excellent_threshold": 0.0,
    },
    "steps_to_completion": {
        "bad_threshold": 100.0,
        "excellent_threshold": 1.0,
    },
    "task_success": {
        "bad_threshold": 0.0,
        "excellent_threshold": 1.0,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"json file not found: {path}")
    if not path.is_file():
        raise ValueError(f"json path is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"json file must contain an object: {path}")

    return data


def load_metric_definition(metric_name: str, *, metrics_dir: Path = METRICS_DIR) -> dict[str, Any]:
    metric_path = metrics_dir / f"metric_{metric_name}.json"
    return load_json(metric_path)


def validate_metric_definition_coverage(
    metric_names: list[str] | tuple[str, ...] | set[str],
    *,
    metrics_dir: Path = METRICS_DIR,
) -> None:
    missing_metric_definitions = sorted(
        metric_name
        for metric_name in metric_names
        if not (metrics_dir / f"metric_{metric_name}.json").is_file()
    )
    if missing_metric_definitions:
        joined = ", ".join(missing_metric_definitions)
        raise ValueError(
            f"metric definition coverage is incomplete; missing definitions for: {joined}"
        )


def validate_normalization_config_coverage(
    metric_names: list[str] | tuple[str, ...] | set[str],
    *,
    normalization_config: dict[str, dict[str, float]] | None = None,
) -> None:
    config = (
        DEFAULT_NORMALIZATION_CONFIG
        if normalization_config is None
        else normalization_config
    )
    missing_normalization_entries = sorted(
        metric_name
        for metric_name in metric_names
        if metric_name not in config
    )
    if missing_normalization_entries:
        joined = ", ".join(missing_normalization_entries)
        raise ValueError(
            "normalization config coverage is incomplete; "
            f"missing entries for: {joined}"
        )


def flatten_result_metrics(result: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}

    for section_name, section_value in result.items():
        if section_name == "metadata":
            continue
        if not isinstance(section_value, dict):
            continue

        for field_name, field_value in section_value.items():
            if isinstance(field_value, bool):
                metrics[field_name] = 1.0 if field_value else 0.0
            elif isinstance(field_value, (int, float)):
                metrics[field_name] = float(field_value)

    return metrics


def get_raw_metric_value(result: dict[str, Any], metric_name: str) -> float:
    flattened = flatten_result_metrics(result)
    if metric_name not in flattened:
        raise ValueError(f"metric '{metric_name}' not found in benchmark results")
    return flattened[metric_name]


def normalize_metric_value(
    metric_name: str,
    raw_value: float,
    *,
    normalization_config: dict[str, dict[str, float]] | None = None,
    metrics_dir: Path = METRICS_DIR,
) -> float:
    config = (
        DEFAULT_NORMALIZATION_CONFIG
        if normalization_config is None
        else normalization_config
    )

    if metric_name not in config:
        raise ValueError(f"normalization config not found for metric: {metric_name}")

    metric_def = load_metric_definition(metric_name, metrics_dir=metrics_dir)

    metric_direction = _require_metric_definition_field(
        metric_def,
        "metric_direction",
        metric_name,
    )
    metric_range = _require_metric_definition_field(
        metric_def,
        "metric_range",
        metric_name,
    )

    metric_config = config[metric_name]
    if "bad_threshold" not in metric_config:
        raise ValueError(f"bad_threshold missing for metric: {metric_name}")
    if "excellent_threshold" not in metric_config:
        raise ValueError(f"excellent_threshold missing for metric: {metric_name}")

    bad_threshold = metric_config["bad_threshold"]
    excellent_threshold = metric_config["excellent_threshold"]

    if metric_range == "binary":
        if raw_value >= excellent_threshold:
            return 1.0
        return 0.0

    if metric_direction == "higher_is_better":
        return _normalize_higher_is_better(
            raw_value,
            bad_threshold=bad_threshold,
            excellent_threshold=excellent_threshold,
        )

    if metric_direction == "lower_is_better":
        return _normalize_lower_is_better(
            raw_value,
            bad_threshold=bad_threshold,
            excellent_threshold=excellent_threshold,
        )

    raise ValueError(
        f"unsupported metric_direction '{metric_direction}' for metric: {metric_name}"
    )


def normalize_metrics_for_radar(
    *,
    baseline_metrics: dict[str, float],
    pr_ephemeral_metrics: dict[str, float] | None,
    pr_light_brain_metrics: dict[str, float],
    metric_names: list[str],
    metrics_dir: Path = METRICS_DIR,
    normalization_config: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    normalized = {
        "baseline": {},
        "pr_light_brain": {},
    }
    if pr_ephemeral_metrics is not None:
        normalized["pr_ephemeral"] = {}

    for metric_name in metric_names:
        normalized["baseline"][metric_name] = normalize_metric_value(
            metric_name,
            baseline_metrics[metric_name],
            normalization_config=normalization_config,
            metrics_dir=metrics_dir,
        )
        if pr_ephemeral_metrics is not None:
            normalized["pr_ephemeral"][metric_name] = normalize_metric_value(
                metric_name,
                pr_ephemeral_metrics[metric_name],
                normalization_config=normalization_config,
                metrics_dir=metrics_dir,
            )
        normalized["pr_light_brain"][metric_name] = normalize_metric_value(
            metric_name,
            pr_light_brain_metrics[metric_name],
            normalization_config=normalization_config,
            metrics_dir=metrics_dir,
        )

    return normalized


def _normalize_higher_is_better(
    value: float,
    *,
    bad_threshold: float,
    excellent_threshold: float,
) -> float:
    if excellent_threshold <= bad_threshold:
        raise ValueError(
            "excellent_threshold must be greater than bad_threshold for higher_is_better metrics"
        )

    if value <= bad_threshold:
        return 0.0
    if value >= excellent_threshold:
        return 1.0

    normalized = (value - bad_threshold) / (excellent_threshold - bad_threshold)
    return _round_and_clamp(normalized)


def _normalize_lower_is_better(
    value: float,
    *,
    bad_threshold: float,
    excellent_threshold: float,
) -> float:
    if excellent_threshold >= bad_threshold:
        raise ValueError(
            "excellent_threshold must be less than bad_threshold for lower_is_better metrics"
        )

    if value >= bad_threshold:
        return 0.0
    if value <= excellent_threshold:
        return 1.0

    normalized = (bad_threshold - value) / (bad_threshold - excellent_threshold)
    return _round_and_clamp(normalized)


def _require_metric_definition_field(
    metric_def: dict[str, Any],
    field_name: str,
    metric_name: str,
) -> Any:
    if field_name not in metric_def:
        raise ValueError(
            f"metric definition for '{metric_name}' is missing field: {field_name}"
        )
    return metric_def[field_name]


def _round_and_clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def main() -> None:
    """
    Run a small normalization demo using inline example benchmark results.
    """
    example_result = {
        "metadata": {
            "scenario_id": "sc_0_interrupt_compress_continue",
            "adapter": "openai_codex",
            "mode": "pr_ephemeral",
        },
        "reasoning_stability": {
            "reasoning_drift_rate": 0.08,
            "replanning_events": 1,
            "context_loss_events": 0,
            "plan_retention_rate": 0.93,
        },
        "knowledge_persistence": {
            "rediscovery_rate": 0.12,
            "knowledge_retention_rate": 0.89,
        },
        "memory_efficiency": {
            "context_growth_rate": 0.21,
            "token_efficiency": 0.74,
            "token_reduction_ratio": 0.31,
            "memory_compression_ratio": 3.2,
        },
        "retrieval_metrics": {
            "retrieval_precision": 0.82,
            "files_read_per_query": 5,
            "tokens_read_per_query": 4200,
            "time_to_context_ms": 180,
        },
        "persistence_integrity": {
            "structural_integrity_score": 0.96,
            "controlled_mutations_ratio": 0.91,
        },
        "task_outcome": {
            "execution_time_ms": 8200,
            "steps_to_completion": 12,
            "task_success": true
        }
    }

    flattened = flatten_result_metrics(example_result)
    metric_names = sorted(
        metric_name for metric_name in flattened if (METRICS_DIR / f"metric_{metric_name}.json").is_file()
    )

    normalized = {
        metric_name: normalize_metric_value(metric_name, flattened[metric_name])
        for metric_name in metric_names
    }

    print(json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
