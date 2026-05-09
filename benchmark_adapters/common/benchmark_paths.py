# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark path utilities for Persistent Reasoning Light.

This module defines repository-relative benchmark paths and deterministic helpers
for scenarios, results, reports, and isolated benchmark reasoning brain roots.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .benchmark_modes import (
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
    validate_benchmark_mode,
)

TRACE_LOG_SUFFIX = ".trace.log"
EVENTS_JSONL_SUFFIX = ".events.jsonl"
RESULT_JSON_SUFFIX = ".result.json"
LEGACY_TRACE_LOG_SUFFIX = ".log"
LEGACY_RESULT_JSON_SUFFIX = ".json"

CANONICAL_RESULT_ARTIFACT_SUFFIXES = (
    TRACE_LOG_SUFFIX,
    RESULT_JSON_SUFFIX,
    EVENTS_JSONL_SUFFIX,
)

RESULT_CLEANUP_SUFFIXES = (
    TRACE_LOG_SUFFIX,
    RESULT_JSON_SUFFIX,
    EVENTS_JSONL_SUFFIX,
    LEGACY_TRACE_LOG_SUFFIX,
    LEGACY_RESULT_JSON_SUFFIX,
)


@dataclass(frozen=True)
class BenchmarkPaths:
    repo_root: Path

    @property
    def benchmarks_root(self) -> Path:
        return self.repo_root / "benchmarks"

    @property
    def scenarios_root(self) -> Path:
        return self.benchmarks_root / "scenarios"

    @property
    def results_root(self) -> Path:
        return self.benchmarks_root / "results"

    @property
    def reports_root(self) -> Path:
        return self.benchmarks_root / "reports"

    @property
    def empty_brain_root(self) -> Path:
        return self.repo_root / "reasoning_brain_storage" / "templates" / "empty"

    @property
    def seeded_brain_root(self) -> Path:
        return self.repo_root / "reasoning_brain_storage" / "benchmarks" / "seeded"

    @property
    def runtime_brain_root(self) -> Path:
        return self.repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"


def resolve_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve()).resolve()

    for candidate in [current, *current.parents]:
        if (
            (candidate / "benchmarks").exists()
            and (candidate / "benchmark_adapters").exists()
        ):
            return candidate

    raise FileNotFoundError("repository root not found from current path")


def get_benchmark_paths(repo_root: Path | None = None) -> BenchmarkPaths:
    root = repo_root.resolve() if repo_root else resolve_repo_root()
    return BenchmarkPaths(repo_root=root)


def scenario_markdown_path(paths: BenchmarkPaths, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return paths.scenarios_root / f"{validated_id}.md"


def scenario_json_path(paths: BenchmarkPaths, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return paths.scenarios_root / f"{validated_id}.json"


def scenario_metadata_path(paths: BenchmarkPaths, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return paths.scenarios_root / f"{validated_id}.metadata.json"


def mode_results_dir(paths: BenchmarkPaths, mode: str) -> Path:
    validated_mode = validate_benchmark_mode(mode)
    return paths.results_root / validated_mode


def result_log_path(paths: BenchmarkPaths, mode: str, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return mode_results_dir(paths, mode) / f"{validated_id}{TRACE_LOG_SUFFIX}"


def result_json_path(paths: BenchmarkPaths, mode: str, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return mode_results_dir(paths, mode) / f"{validated_id}{RESULT_JSON_SUFFIX}"


def result_events_path(paths: BenchmarkPaths, mode: str, scenario_id: str) -> Path:
    validated_id = validate_scenario_id(scenario_id)
    return mode_results_dir(paths, mode) / f"{validated_id}{EVENTS_JSONL_SUFFIX}"


def benchmark_brain_root_for_mode(paths: BenchmarkPaths, mode: str) -> Path | None:
    validated_mode = validate_benchmark_mode(mode)

    if validated_mode == BASELINE:
        return None
    if validated_mode == PR_EPHEMERAL:
        return paths.empty_brain_root
    if validated_mode == PR_LIGHT_BRAIN:
        return paths.runtime_brain_root

    raise ValueError(f"unsupported benchmark mode: '{validated_mode}'")


def ensure_benchmark_output_dirs(paths: BenchmarkPaths) -> None:
    paths.results_root.mkdir(parents=True, exist_ok=True)
    paths.reports_root.mkdir(parents=True, exist_ok=True)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        mode_results_dir(paths, mode).mkdir(parents=True, exist_ok=True)


def validate_required_benchmark_roots(paths: BenchmarkPaths) -> None:
    required = [
        paths.benchmarks_root,
        paths.scenarios_root,
        paths.empty_brain_root,
        paths.seeded_brain_root,
        paths.runtime_brain_root,
        paths.empty_brain_root / "views" / "working_context.json",
        paths.seeded_brain_root / "views" / "working_context.json",
        paths.runtime_brain_root / "views" / "working_context.json",
    ]

    missing = [path for path in required if not path.exists()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"required benchmark paths are missing: {joined}")


def validate_scenario_id(scenario_id: str) -> str:
    if not isinstance(scenario_id, str):
        raise ValueError("scenario_id must be a string")

    cleaned = scenario_id.strip()
    if not cleaned:
        raise ValueError("scenario_id must not be empty")
    if cleaned != scenario_id:
        raise ValueError("scenario_id must not contain surrounding whitespace")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("scenario_id must not contain path separators")
    if cleaned.endswith(".md") or cleaned.endswith(".json"):
        raise ValueError("scenario_id must not include file extension")

    return cleaned


__all__ = [
    "CANONICAL_RESULT_ARTIFACT_SUFFIXES",
    "BenchmarkPaths",
    "EVENTS_JSONL_SUFFIX",
    "LEGACY_RESULT_JSON_SUFFIX",
    "LEGACY_TRACE_LOG_SUFFIX",
    "benchmark_brain_root_for_mode",
    "ensure_benchmark_output_dirs",
    "get_benchmark_paths",
    "mode_results_dir",
    "resolve_repo_root",
    "result_events_path",
    "RESULT_CLEANUP_SUFFIXES",
    "RESULT_JSON_SUFFIX",
    "result_json_path",
    "result_log_path",
    "scenario_json_path",
    "scenario_metadata_path",
    "scenario_markdown_path",
    "TRACE_LOG_SUFFIX",
    "validate_required_benchmark_roots",
    "validate_scenario_id",
]
