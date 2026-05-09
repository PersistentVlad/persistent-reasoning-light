# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Run benchmark preflight validation for Persistent Reasoning Light.

This tool validates environment and contract prerequisites before benchmark
execution begins. It is intentionally explicit and fail-fast.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))


from benchmark_adapters.common.benchmark_modes import (  # noqa: E402
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmark_adapters.common.benchmark_paths import (  # noqa: E402
    CANONICAL_RESULT_ARTIFACT_SUFFIXES,
    EVENTS_JSONL_SUFFIX,
    RESULT_JSON_SUFFIX,
    TRACE_LOG_SUFFIX,
    BenchmarkPaths,
    get_benchmark_paths,
    result_events_path,
    result_json_path,
    result_log_path,
    validate_required_benchmark_roots,
)
from benchmark_adapters.common.result_utils import (  # noqa: E402
    REQUIRED_NUMERIC_RESULT_METRIC_NAMES,
)
from benchmarks.tools.generate_quickchart_radar_svg import (  # noqa: E402
    load_json as load_tool_json,
    validate_required_radar_template_set,
    validate_radar_definition,
)
from benchmarks.tools.normalize_metrics import (  # noqa: E402
    validate_metric_definition_coverage,
)


METRICS_DIR = TOOLS_DIR / "metrics"
RADAR_CHARTS_DIR = TOOLS_DIR / "radar_charts"

SUPPORTED_BACKENDS = ("gemini", "openai_codex")
DEFAULT_BACKEND = "gemini"

COMMON_REQUIRED_IMPORTS = (
    "benchmark_adapters.common.benchmark_paths",
    "core.context_loader",
    "benchmarks.tools.compute_metrics_from_events",
    "benchmarks.tools.compare_results",
    "benchmarks.tools.generate_summary_report",
    "benchmarks.tools.generate_quickchart_radar_svg",
)

REQUIRED_METRIC_DEFINITION_FILES = (
    "metric_context_growth_rate.json",
    "metric_context_loss_events.json",
    "metric_controlled_mutations_ratio.json",
    "metric_execution_time_ms.json",
    "metric_files_read_per_query.json",
    "metric_knowledge_retention_rate.json",
    "metric_memory_compression_ratio.json",
    "metric_plan_retention_rate.json",
    "metric_reasoning_drift_rate.json",
    "metric_rediscovery_rate.json",
    "metric_replanning_events.json",
    "metric_retrieval_precision.json",
    "metric_steps_to_completion.json",
    "metric_structural_integrity_score.json",
    "metric_time_to_context_ms.json",
    "metric_token_efficiency.json",
    "metric_token_reduction_ratio.json",
    "metric_tokens_read_per_query.json",
)

REQUIRED_RADAR_CONFIG_FILES = (
    "radar_context_efficiency.json",
    "radar_operational_cost.json",
    "radar_reasoning_integrity.json",
    "radar_reasoning_stability.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run benchmark preflight validation for a selectable backend."
    )
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default=DEFAULT_BACKEND,
        help="Benchmark execution backend to validate.",
    )
    return parser.parse_args()


def run_preflight(
    repo_root: Path | None = None,
    *,
    backend: str = DEFAULT_BACKEND,
) -> None:
    resolved_repo_root = repo_root.resolve() if repo_root else REPO_ROOT
    paths = get_benchmark_paths(resolved_repo_root)

    _validate_required_imports(backend)
    _validate_key_directories(paths)
    validate_required_benchmark_roots(paths)
    _validate_required_metric_definition_files()
    _validate_required_radar_config_files()
    _validate_artifact_suffix_contract(paths)


def _validate_required_imports(backend: str) -> None:
    for module_name in _required_imports_for_backend(backend):
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            raise RuntimeError(
                f"preflight import check failed for '{module_name}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc


def _required_imports_for_backend(backend: str) -> tuple[str, ...]:
    if backend == "gemini":
        return (
            "benchmark_adapters.gemini.adapter",
            "reasoning_adapters.gemini.adapter",
            *COMMON_REQUIRED_IMPORTS,
        )

    if backend == "openai_codex":
        return (
            "benchmark_adapters.openai_codex.adapter",
            "reasoning_adapters.codex.adapter",
            *COMMON_REQUIRED_IMPORTS,
        )

    raise ValueError(f"unsupported backend: {backend}")


def _validate_key_directories(paths: BenchmarkPaths) -> None:
    required_directories = {
        "repo_root": paths.repo_root,
        "benchmarks_root": paths.benchmarks_root,
        "scenarios_root": paths.scenarios_root,
        "results_root": paths.results_root,
        "reports_root": paths.reports_root,
        "empty_brain_root": paths.empty_brain_root,
        "seeded_brain_root": paths.seeded_brain_root,
        "runtime_brain_root": paths.runtime_brain_root,
        "metrics_dir": METRICS_DIR,
        "radar_charts_dir": RADAR_CHARTS_DIR,
    }

    for label, path in required_directories.items():
        if not path.exists():
            raise FileNotFoundError(
                f"preflight directory check failed: required directory '{label}' "
                f"is missing: {path}"
            )
        if not path.is_dir():
            raise ValueError(
                f"preflight directory check failed: expected directory for '{label}': {path}"
            )


def _validate_required_metric_definition_files() -> None:
    for filename in REQUIRED_METRIC_DEFINITION_FILES:
        path = METRICS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"preflight metric definition check failed: required file is missing: {path}"
            )
        if not path.is_file():
            raise ValueError(
                f"preflight metric definition check failed: expected file but found non-file path: {path}"
            )

    validate_metric_definition_coverage(
        REQUIRED_NUMERIC_RESULT_METRIC_NAMES,
        metrics_dir=METRICS_DIR,
    )


def _validate_required_radar_config_files() -> None:
    validate_required_radar_template_set(radar_charts_dir=RADAR_CHARTS_DIR)

    for filename in REQUIRED_RADAR_CONFIG_FILES:
        path = RADAR_CHARTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"preflight radar config check failed: required file is missing: {path}"
            )
        if not path.is_file():
            raise ValueError(
                f"preflight radar config check failed: expected file but found non-file path: {path}"
            )

        validate_radar_definition(
            load_tool_json(path),
            metrics_dir=METRICS_DIR,
        )


def _validate_artifact_suffix_contract(paths: BenchmarkPaths) -> None:
    expected_suffixes = {
        TRACE_LOG_SUFFIX,
        EVENTS_JSONL_SUFFIX,
        RESULT_JSON_SUFFIX,
    }
    actual_suffixes = set(CANONICAL_RESULT_ARTIFACT_SUFFIXES)
    if actual_suffixes != expected_suffixes:
        raise ValueError(
            "preflight artifact contract check failed: canonical artifact suffixes "
            f"must be {sorted(expected_suffixes)}, got {sorted(actual_suffixes)}"
        )

    scenario_id = "sc_preflight_contract_probe"
    expected_paths = {
        "trace": scenario_id + TRACE_LOG_SUFFIX,
        "events": scenario_id + EVENTS_JSONL_SUFFIX,
        "result": scenario_id + RESULT_JSON_SUFFIX,
    }
    actual_paths = {
        "trace": result_log_path(paths, BASELINE, scenario_id).name,
        "events": result_events_path(paths, PR_EPHEMERAL, scenario_id).name,
        "result": result_json_path(paths, PR_LIGHT_BRAIN, scenario_id).name,
    }

    for label, expected_name in expected_paths.items():
        actual_name = actual_paths[label]
        if actual_name != expected_name:
            raise ValueError(
                "preflight artifact contract check failed: "
                f"{label} artifact name must be '{expected_name}', got '{actual_name}'"
            )


def main() -> None:
    args = parse_args()
    run_preflight(backend=args.backend)
    print(f"benchmark preflight check passed (backend={args.backend})")


if __name__ == "__main__":
    main()
