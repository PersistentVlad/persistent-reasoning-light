# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Run benchmark pipeline for Persistent Reasoning Light.

Current behavior:
1. Execute benchmark artifact flow across supported modes
2. Derive .result.json from .events.jsonl
3. Optionally run comparison and report generation

Important:
- backend selection is explicit
- the selected benchmark adapter owns prompt construction, execution, event logging, and raw trace logging
- result, comparison, and report stages remain downstream of event artifacts
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple


# Temporary PoC import bootstrap.
# This is acceptable for a top-level script during the current packaging stage,
# but it is not the intended long-term import strategy.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))


import benchmark_adapters.gemini.adapter as gemini_adapter
import benchmark_adapters.openai_codex.adapter as openai_codex_adapter
from benchmark_adapters.common.benchmark_modes import (
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmark_adapters.common.benchmark_paths import (
    get_benchmark_paths,
    result_json_path,
    scenario_json_path,
)
from benchmark_adapters.common.scenario_utils import load_benchmark_scenario
from benchmark_adapters.common.scenario_utils import build_resolved_execution_artifact_payload
from benchmarks.tools.compute_metrics_from_events import derive_result_artifact
from benchmarks.tools.preflight_check import run_preflight
from benchmarks.tools.reset_runtime_brain_and_temp_results import (
    clean_temporary_benchmark_results,
)
from benchmarks.tools.post_run_artifact_harvest import (
    run_post_run_artifact_harvest,
)
from benchmarks.tools.generate_retention_layer import (
    generate_retention_artifacts_for_run,
    resolve_scenario_interpretation_contract,
)
from reasoning_brain_storage.tools import (
    BrainRef,
    create_snapshot,
    load_brain,
    prepare_runtime_from_source,
    reset_to_empty,
)


DIAGNOSTIC_SCENARIOS = [
    "sc_00_stateless_direct_transform",
    "sc_01_structural_retention",
    "sc_02_n_back_anomaly_trap",
    "sc_03_math_state_loss",
    "sc_04_chain_collapse",
    "sc_05_digit_span_n_back_hybrid",
    "sc_06_plan_reset",
    "sc_07_trail_making",
    "sc_08_move_clock_hands",
]
KILLER_STRESS_SCENARIO_ID = "sc_99_killer_all_scenarios"
MANDATORY_STRESS_SCENARIOS = (KILLER_STRESS_SCENARIO_ID,)
SCENARIOS = tuple(DIAGNOSTIC_SCENARIOS) + MANDATORY_STRESS_SCENARIOS

BENCHMARK_MODE_LADDER = (
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)

DEFAULT_TASK = "Execute the scenario faithfully and provide structured reasoning."
SHOWCASE_SCENARIO_ID = "sc_99_killer_all_scenarios"
SUPPORTED_BACKENDS = ("gemini", "openai_codex")
DEFAULT_BACKEND = "gemini"
SUPPORTED_ARTIFACT_GENERATOR_MODES = ("legacy", "constrained", "shadow")
DEFAULT_ARTIFACT_GENERATOR_MODE = "legacy"
SUPPORTED_ARTIFACT_FILTER_MODES = ("off", "shadow", "soft")
DEFAULT_ARTIFACT_FILTER_MODE = "off"
SUPPORTED_WORKING_CONTEXT_FORMATS = ("reference_only", "relevant_summaries")
DEFAULT_WORKING_CONTEXT_FORMAT = "reference_only"
DEFAULT_SCENARIO_DELAY_SECONDS = 20
DEFAULT_QUOTA_RETRY_WAIT_SECONDS = 30
OVERWRITE_EXISTING_ARTIFACTS = True
PROFILES_DIR = REPO_ROOT / "benchmarks" / "profiles"
SUPPORTED_BRAIN_MODES = ("accumulative", "static")
SUPPORTED_ORDINARY_BRAIN_IN_TYPES = ("empty", "seeded", "runtime")
SUPPORTED_ORDINARY_BRAIN_OUT_MODES = ("continue", "snapshot", "empty")


class BackendSelection(NamedTuple):
    backend: str
    adapter_name: str
    run_scenario: Callable[..., dict[str, Any]]
    get_benchmark_agent_metadata: Callable[..., dict[str, str]]


class BenchmarkProfile(NamedTuple):
    diagnostic_modes: "DiagnosticModesPolicy"
    brain_mode: str
    brain_in: "BrainInPolicy"
    brain_out: "BrainOutPolicy"
    name: str
    backend: str
    model: str
    scenario_subset: tuple[str, ...]
    showcase: str
    mode_to_key_mapping: str
    timeout_seconds: int
    inter_scenario_delay_seconds: int
    on_429_first: str
    on_429_second: str
    purpose: str
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE
    artifact_filter_mode: str = DEFAULT_ARTIFACT_FILTER_MODE


class ScenarioRunSummary(NamedTuple):
    event_path: Path
    is_quota_exhausted: bool
    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class RunExecutionState(NamedTuple):
    quota_stop_reason: str | None
    total_429_count: int


class BrainInPolicy(NamedTuple):
    type: str
    ref: str | None


class BrainOutPolicy(NamedTuple):
    mode: str
    ref: str | None


class DiagnosticModesPolicy(NamedTuple):
    pr_ephemeral: bool
    post_run_artifact_harvest: bool = False


class ScenarioLayerPlan(NamedTuple):
    diagnostic_scenario_ids: tuple[str, ...]
    stress_scenario_ids: tuple[str, ...]
    all_scenario_ids: tuple[str, ...]


def resolve_ordinary_scenario_layers(
    profile: BenchmarkProfile | None = None,
) -> ScenarioLayerPlan:
    selected_diagnostic_ids = (
        profile.scenario_subset if profile is not None else tuple(DIAGNOSTIC_SCENARIOS)
    )
    normalized_diagnostics = tuple(
        scenario_id
        for scenario_id in _ordered_unique_scenario_ids(selected_diagnostic_ids)
        if scenario_id not in MANDATORY_STRESS_SCENARIOS
    )
    all_scenario_ids = normalized_diagnostics + MANDATORY_STRESS_SCENARIOS
    return ScenarioLayerPlan(
        diagnostic_scenario_ids=normalized_diagnostics,
        stress_scenario_ids=MANDATORY_STRESS_SCENARIOS,
        all_scenario_ids=all_scenario_ids,
    )


def write_scenario_layer_manifest(
    repo_root: Path,
    *,
    run_id: str,
    diagnostic_scenario_ids: tuple[str, ...],
    stress_scenario_ids: tuple[str, ...],
) -> Path:
    manifest_path = repo_root / "benchmarks" / "reports" / run_id / "scenario_layers.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    scenarios: list[dict[str, Any]] = []
    ordered_ids = diagnostic_scenario_ids + stress_scenario_ids
    for index, scenario_id in enumerate(ordered_ids, start=1):
        stress_case = scenario_id in stress_scenario_ids
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "execution_order": index,
                "stress_case": stress_case,
                "scenario_role": "integration_stress" if stress_case else "diagnostic",
            }
        )

    payload = {
        "diagnostic_scenario_ids": list(diagnostic_scenario_ids),
        "stress_scenario_ids": list(stress_scenario_ids),
        "scenarios": scenarios,
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest_path


def write_scenario_interpretation_support_manifest(
    repo_root: Path,
    *,
    run_id: str,
    diagnostic_scenario_ids: tuple[str, ...],
    stress_scenario_ids: tuple[str, ...],
) -> Path:
    paths = get_benchmark_paths(repo_root)
    manifest_path = (
        repo_root
        / "benchmarks"
        / "reports"
        / run_id
        / "scenario_interpretation_support.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    ordered_ids = diagnostic_scenario_ids + stress_scenario_ids
    scenarios: list[dict[str, Any]] = []
    for scenario_id in ordered_ids:
        scenario = load_benchmark_scenario(paths, scenario_id)
        scenario_type = _require_string_config_field(
            scenario.config,
            "scenario_type",
            scenario_id,
        )
        scenario_role = (
            "integration_stress" if scenario_id in stress_scenario_ids else "diagnostic"
        )
        interpretation_contract = resolve_scenario_interpretation_contract(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            scenario_config=scenario.config,
        )
        entry: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "scenario_role": scenario_role,
            "interpretation_variant": interpretation_contract["interpretation_variant"],
            "layer_support": interpretation_contract["layer_support"],
        }
        reason = interpretation_contract.get("reason")
        if isinstance(reason, str) and reason.strip():
            entry["reason"] = reason.strip()
        scenarios.append(entry)

    payload = {
        "run_id": run_id,
        "scenarios": scenarios,
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest_path


def write_resolved_execution_artifacts(
    repo_root: Path,
    *,
    run_id: str,
    scenario_ids: tuple[str, ...],
) -> list[Path]:
    paths = get_benchmark_paths(repo_root)
    scenarios_dir = repo_root / "benchmarks" / "reports" / run_id / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for scenario_id in scenario_ids:
        if not scenario_json_path(paths, scenario_id).exists():
            continue
        payload = build_resolved_execution_artifact_payload(
            paths,
            scenario_id=scenario_id,
        )
        if payload is None:
            continue
        output_path = scenarios_dir / f"{_scenario_resolved_artifact_stem(scenario_id)}_resolved.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        written_paths.append(output_path)
    return written_paths


def _ordered_unique_scenario_ids(scenario_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for scenario_id in scenario_ids:
        if scenario_id in seen:
            continue
        seen.add(scenario_id)
        ordered.append(scenario_id)
    return tuple(ordered)


def _scenario_resolved_artifact_stem(scenario_id: str) -> str:
    parts = scenario_id.split("_")
    if len(parts) >= 2 and parts[0] == "sc":
        return f"{parts[0]}_{parts[1]}"
    return scenario_id


def _require_string_config_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"scenario '{label}' field '{field_name}' must be a non-empty string")
    return value.strip()


def resolve_execution_modes(
    profile: BenchmarkProfile | None = None,
) -> tuple[str, ...]:
    if profile is not None and profile.diagnostic_modes.pr_ephemeral:
        return BENCHMARK_MODE_LADDER
    return (BASELINE, PR_LIGHT_BRAIN)


def _normalize_token_usage(value: object) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "prompt_tokens": _normalize_optional_token_count(value.get("prompt_tokens")),
        "output_tokens": _normalize_optional_token_count(value.get("output_tokens")),
        "total_tokens": _normalize_optional_token_count(value.get("total_tokens")),
    }


def _normalize_optional_token_count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the benchmark pipeline with a selectable backend."
    )
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default=None,
        help="Benchmark execution backend to use.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional benchmark run profile name (without .json extension).",
    )
    parser.add_argument(
        "--artifact-generator-mode",
        choices=SUPPORTED_ARTIFACT_GENERATOR_MODES,
        default=None,
        help="Artifact generator prompt mode to pass to the selected benchmark adapter.",
    )
    parser.add_argument(
        "--artifact-filter-mode",
        choices=SUPPORTED_ARTIFACT_FILTER_MODES,
        default=None,
        help="Artifact filter diagnostic mode to pass to the selected benchmark adapter.",
    )
    parser.add_argument(
        "--working-context-format",
        choices=SUPPORTED_WORKING_CONTEXT_FORMATS,
        default=None,
        help="Working context prompt format to pass to the selected benchmark adapter.",
    )
    return parser.parse_args()


def resolve_backend(backend: str) -> BackendSelection:
    if backend == "gemini":
        return BackendSelection(
            backend="gemini",
            adapter_name=gemini_adapter.DEFAULT_ADAPTER_NAME,
            run_scenario=gemini_adapter.run_scenario,
            get_benchmark_agent_metadata=gemini_adapter.get_benchmark_agent_metadata,
        )

    if backend == "openai_codex":
        return BackendSelection(
            backend="openai_codex",
            adapter_name=openai_codex_adapter.DEFAULT_ADAPTER_NAME,
            run_scenario=openai_codex_adapter.run_scenario,
            get_benchmark_agent_metadata=openai_codex_adapter.get_benchmark_agent_metadata,
        )

    raise ValueError(f"unsupported backend: {backend}")


def run_single(
    scenario_id: str,
    mode: str,
    *,
    repo_root: Path,
    backend: BackendSelection,
    profile: BenchmarkProfile | None = None,
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
    artifact_filter_mode: str = DEFAULT_ARTIFACT_FILTER_MODE,
) -> ScenarioRunSummary:
    """
    Run a single scenario in a single mode using the selected benchmark backend.
    """
    print(f"[RUN] scenario={scenario_id} mode={mode} backend={backend.backend}")

    scenario_kwargs: dict[str, Any] = {
        "mode": mode,
        "task_text": DEFAULT_TASK,
        "agent_output": None,
        "adapter_name": backend.adapter_name,
        "repo_root": repo_root,
        "overwrite_existing_artifacts": OVERWRITE_EXISTING_ARTIFACTS,
        "artifact_generator_mode": artifact_generator_mode,
        "working_context_format": working_context_format,
        "artifact_filter_mode": artifact_filter_mode,
    }
    if backend.backend == "gemini" and profile is not None:
        scenario_kwargs["model"] = profile.model
        scenario_kwargs["timeout_seconds"] = profile.timeout_seconds

    result = backend.run_scenario(
        scenario_id,
        **scenario_kwargs,
    )
    token_usage = _normalize_token_usage(result.get("token_usage"))

    event_path = result["event_log_path"]
    paths = get_benchmark_paths(repo_root)
    json_path = result_json_path(paths, mode, scenario_id)
    derive_result_artifact(
        event_path,
        output_path=json_path,
        adapter_name=backend.adapter_name,
        overwrite=OVERWRITE_EXISTING_ARTIFACTS,
    )

    print(
        "[OK] result saved: "
        f"{json_path} prompt_tokens={token_usage['prompt_tokens']} "
        f"output_tokens={token_usage['output_tokens']} total_tokens={token_usage['total_tokens']}"
    )
    return ScenarioRunSummary(
        event_path=event_path,
        is_quota_exhausted=_is_quota_exhausted_event_log(event_path),
        prompt_tokens=token_usage["prompt_tokens"],
        output_tokens=token_usage["output_tokens"],
        total_tokens=token_usage["total_tokens"],
    )


def run_all(
    repo_root: Path,
    *,
    backend: BackendSelection,
    scenario_ids: tuple[str, ...],
    execution_modes: tuple[str, ...],
    inter_scenario_delay_seconds: int,
    quota_policy: BenchmarkProfile | None = None,
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
    artifact_filter_mode: str = DEFAULT_ARTIFACT_FILTER_MODE,
) -> RunExecutionState:
    """
    Run all configured scenarios across all configured modes.
    """
    total_429_count = 0
    for mode in execution_modes:
        consecutive_429_count = 0
        for index, scenario_id in enumerate(scenario_ids):
            summary = run_single(
                scenario_id,
                mode,
                repo_root=repo_root,
                backend=backend,
                profile=quota_policy,
                artifact_generator_mode=artifact_generator_mode,
                working_context_format=working_context_format,
                artifact_filter_mode=artifact_filter_mode,
            )
            if summary.is_quota_exhausted:
                total_429_count += 1
                consecutive_429_count += 1
                if quota_policy is not None and quota_policy.on_429_first == "wait_30s_retry_once":
                    if consecutive_429_count == 1:
                        print(
                            "[WARN] quota 429 detected "
                            f"(mode={mode} scenario={scenario_id}); waiting "
                            f"{DEFAULT_QUOTA_RETRY_WAIT_SECONDS}s before one retry"
                        )
                        time.sleep(DEFAULT_QUOTA_RETRY_WAIT_SECONDS)
                        retry_summary = run_single(
                            scenario_id,
                            mode,
                            repo_root=repo_root,
                            backend=backend,
                            profile=quota_policy,
                            artifact_generator_mode=artifact_generator_mode,
                            working_context_format=working_context_format,
                            artifact_filter_mode=artifact_filter_mode,
                        )
                        if retry_summary.is_quota_exhausted:
                            total_429_count += 1
                            consecutive_429_count += 1
                        else:
                            consecutive_429_count = 0
                            continue

                    if (
                        consecutive_429_count >= 2
                        and quota_policy.on_429_second == "stop_run"
                    ):
                        quota_stop_reason = (
                            f"quota_exhausted mode={mode} scenario={scenario_id}"
                        )
                        print(f"[WARN] {quota_stop_reason}; stopping run gracefully")
                        return RunExecutionState(
                            quota_stop_reason=quota_stop_reason,
                            total_429_count=total_429_count,
                        )
                continue

            consecutive_429_count = 0
            if index < len(scenario_ids) - 1:
                print(
                    f"[PAUSE] mode={mode} "
                    f"sleeping {inter_scenario_delay_seconds}s before next scenario"
                )
                time.sleep(inter_scenario_delay_seconds)
    return RunExecutionState(
        quota_stop_reason=None,
        total_429_count=total_429_count,
    )


def run_post_processing(
    repo_root: Path,
    *,
    run_id: str,
    agent_metadata: dict[str, str],
    backend: BackendSelection,
    scenario_ids: tuple[str, ...],
    showcase_scenario_id: str,
    run_metadata: dict[str, Any],
) -> None:
    """
    Run optional comparison and report generation stages.

    These stages are not required for validating the execution scaffold itself.
    """
    reports_root = repo_root / "benchmarks" / "reports"
    run_reports_dir = reports_root / run_id
    scenarios_dir = run_reports_dir / "scenarios"
    charts_dir = run_reports_dir / "charts"
    compared_summary_report_path = run_reports_dir / "compared_summary_report.md"
    comparison_summary_path = run_reports_dir / "comparison_summary.json"

    from benchmarks.tools.compare_results import generate_comparison_artifact
    from benchmarks.tools.generate_summary_report import (
        generate_run_summary_report_artifact,
    )

    comparison_paths: list[Path] = []
    for scenario_id in scenario_ids:
        print(f"[POST] scenario={scenario_id} comparing results")
        comparison_path = scenarios_dir / f"{scenario_id}.comparison.json"

        generate_comparison_artifact(
            scenario_id,
            adapter_name=backend.adapter_name,
            output_path=comparison_path,
            repo_root=repo_root,
            overwrite=OVERWRITE_EXISTING_ARTIFACTS,
        )
        print(f"[POST] comparison saved: {comparison_path}")
        comparison_paths.append(comparison_path)

    report_path, written_summary_path, chart_paths, warnings = (
        generate_run_summary_report_artifact(
            comparison_paths,
            run_id=run_id,
            agent_metadata=agent_metadata,
            run_metadata=run_metadata,
            output_path=compared_summary_report_path,
            comparison_summary_output_path=comparison_summary_path,
            charts_dir=charts_dir,
            showcase_scenario_id=showcase_scenario_id,
            overwrite=OVERWRITE_EXISTING_ARTIFACTS,
        )
    )

    if written_summary_path is not None:
        print(f"[POST] comparison summary saved: {written_summary_path}")
    print(f"[POST] report saved: {report_path}")
    if chart_paths:
        print(f"[POST] showcase charts saved: {len(chart_paths)}")
    if warnings:
        print("[POST] warnings:")
        for warning in warnings:
            print(f"- {warning}")

    print("[POST] done")


def build_run_id(*, adapter_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{adapter_name}"


def apply_pre_run_brain_lifecycle(
    repo_root: Path,
    *,
    profile: BenchmarkProfile | None = None,
) -> None:
    paths = get_benchmark_paths(repo_root)
    effective_profile = profile or _default_benchmark_profile()

    if effective_profile.brain_in.type == "empty":
        prepare_runtime_from_source(
            source=BrainRef(type="empty", path=paths.empty_brain_root),
            runtime_root=paths.runtime_brain_root,
        )
        return

    if effective_profile.brain_in.type == "seeded":
        prepare_runtime_from_source(
            source=BrainRef(type="seeded", path=paths.seeded_brain_root),
            runtime_root=paths.runtime_brain_root,
        )
        return

    if effective_profile.brain_in.type == "runtime":
        load_brain(root=paths.runtime_brain_root)
        return

    raise ValueError(
        "unsupported ordinary-run brain_in.type: "
        f"{effective_profile.brain_in.type}"
    )


def apply_post_run_brain_lifecycle(
    repo_root: Path,
    *,
    run_id: str,
    profile: BenchmarkProfile | None = None,
) -> None:
    paths = get_benchmark_paths(repo_root)
    effective_profile = profile or _default_benchmark_profile()

    if effective_profile.brain_out.mode == "continue":
        return

    if effective_profile.brain_out.mode == "snapshot":
        snapshot_root = _ordinary_run_snapshot_root(
            repo_root=repo_root,
            run_id=run_id,
        )
        snapshot_root.parent.mkdir(parents=True, exist_ok=True)
        create_snapshot(
            source_root=paths.runtime_brain_root,
            snapshot_root=snapshot_root,
        )
        if effective_profile.brain_mode == "static":
            reset_to_empty(
                empty_template_root=paths.empty_brain_root,
                runtime_root=paths.runtime_brain_root,
            )
        return

    if effective_profile.brain_out.mode == "empty":
        reset_to_empty(
            empty_template_root=paths.empty_brain_root,
            runtime_root=paths.runtime_brain_root,
        )
        return

    raise ValueError(
        "unsupported ordinary-run brain_out.mode: "
        f"{effective_profile.brain_out.mode}"
    )


def _ordinary_run_snapshot_root(*, repo_root: Path, run_id: str) -> Path:
    return repo_root / "reasoning_brain_storage" / "snapshots" / run_id


def load_profile(profile_name: str) -> BenchmarkProfile:
    if not isinstance(profile_name, str):
        raise ValueError("profile must be a string")
    cleaned_profile_name = profile_name.strip()
    if not cleaned_profile_name:
        raise ValueError("profile must not be empty")

    profile_path = PROFILES_DIR / f"{cleaned_profile_name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"profile file not found: {profile_path}")
    if not profile_path.is_file():
        raise ValueError(f"profile path is not a file: {profile_path}")

    with profile_path.open("r", encoding="utf-8") as handle:
        raw_profile = json.load(handle)

    if not isinstance(raw_profile, dict):
        raise ValueError("profile file must contain an object")

    execution = _require_profile_object(raw_profile, "execution")
    quota_policy = _require_profile_object(raw_profile, "quota_policy")
    scenario_subset = _require_profile_string_list(raw_profile, "scenario_subset")
    showcase = _require_profile_string(raw_profile, "showcase")
    if showcase not in scenario_subset and showcase not in MANDATORY_STRESS_SCENARIOS:
        raise ValueError(
            "profile showcase must be included in scenario_subset or be a mandatory stress scenario"
        )

    backend = _require_profile_string(raw_profile, "backend")
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"unsupported profile backend: {backend}")

    mode_to_key_mapping = _require_profile_string(raw_profile, "mode_to_key_mapping")
    if mode_to_key_mapping != "strict":
        raise ValueError("profile mode_to_key_mapping must be 'strict'")

    on_429_first = _require_profile_string(quota_policy, "on_429_first")
    on_429_second = _require_profile_string(quota_policy, "on_429_second")
    working_context_format = _load_working_context_format(raw_profile)
    artifact_generator_mode = _load_artifact_generator_mode(raw_profile)
    artifact_filter_mode = _load_artifact_filter_mode(raw_profile)
    if on_429_first != "wait_30s_retry_once":
        raise ValueError("profile quota_policy.on_429_first must be 'wait_30s_retry_once'")
    if on_429_second != "stop_run":
        raise ValueError("profile quota_policy.on_429_second must be 'stop_run'")

    brain_mode = _load_brain_mode(raw_profile)
    diagnostic_modes = _load_diagnostic_modes_policy(raw_profile)
    brain_in = _load_brain_in_policy(raw_profile)
    brain_out = _load_brain_out_policy(raw_profile)
    _validate_ordinary_run_lifecycle(
        brain_mode=brain_mode,
        brain_in=brain_in,
        brain_out=brain_out,
    )

    return BenchmarkProfile(
        diagnostic_modes=diagnostic_modes,
        brain_mode=brain_mode,
        brain_in=brain_in,
        brain_out=brain_out,
        name=_require_profile_string(raw_profile, "name"),
        backend=backend,
        model=_require_profile_string(raw_profile, "model"),
        scenario_subset=tuple(scenario_subset),
        showcase=showcase,
        mode_to_key_mapping=mode_to_key_mapping,
        timeout_seconds=_require_profile_int(execution, "timeout_seconds"),
        inter_scenario_delay_seconds=_require_profile_int(
            execution,
            "inter_scenario_delay_seconds",
        ),
        on_429_first=on_429_first,
        on_429_second=on_429_second,
        working_context_format=working_context_format,
        artifact_generator_mode=artifact_generator_mode,
        artifact_filter_mode=artifact_filter_mode,
        purpose=_require_profile_string(raw_profile, "purpose"),
    )


def _default_benchmark_profile() -> BenchmarkProfile:
    return BenchmarkProfile(
        diagnostic_modes=DiagnosticModesPolicy(
            pr_ephemeral=False,
            post_run_artifact_harvest=False,
        ),
        brain_mode="accumulative",
        brain_in=BrainInPolicy(type="empty", ref=None),
        brain_out=BrainOutPolicy(mode="continue", ref=None),
        name="__default__",
        backend=DEFAULT_BACKEND,
        model="",
        scenario_subset=tuple(DIAGNOSTIC_SCENARIOS),
        showcase=SHOWCASE_SCENARIO_ID,
        mode_to_key_mapping="strict",
        timeout_seconds=30,
        inter_scenario_delay_seconds=DEFAULT_SCENARIO_DELAY_SECONDS,
        on_429_first="wait_30s_retry_once",
        on_429_second="stop_run",
        working_context_format=DEFAULT_WORKING_CONTEXT_FORMAT,
        artifact_generator_mode=DEFAULT_ARTIFACT_GENERATOR_MODE,
        artifact_filter_mode=DEFAULT_ARTIFACT_FILTER_MODE,
        purpose="implicit_default",
    )


def _load_diagnostic_modes_policy(raw_profile: dict[str, Any]) -> DiagnosticModesPolicy:
    value = raw_profile.get("diagnostic_modes")
    if value is None:
        return DiagnosticModesPolicy(
            pr_ephemeral=False,
            post_run_artifact_harvest=False,
        )
    if not isinstance(value, dict):
        raise ValueError("profile field 'diagnostic_modes' must be an object")

    pr_ephemeral = value.get("pr_ephemeral", False)
    if not isinstance(pr_ephemeral, bool):
        raise ValueError("profile field 'diagnostic_modes.pr_ephemeral' must be a boolean")
    post_run_artifact_harvest = value.get("post_run_artifact_harvest", False)
    if not isinstance(post_run_artifact_harvest, bool):
        raise ValueError(
            "profile field 'diagnostic_modes.post_run_artifact_harvest' must be a boolean"
        )

    return DiagnosticModesPolicy(
        pr_ephemeral=pr_ephemeral,
        post_run_artifact_harvest=post_run_artifact_harvest,
    )


def _post_run_harvest_runtime_available(
    profile: BenchmarkProfile | None,
) -> bool:
    return True


def _post_run_harvest_skip_reason(
    *,
    profile: BenchmarkProfile | None,
    execution_completed: bool,
) -> str | None:
    effective_profile = profile or _default_benchmark_profile()
    if not effective_profile.diagnostic_modes.post_run_artifact_harvest:
        return "disabled"
    if not execution_completed:
        return "benchmark_execution_incomplete"
    return None


def _require_profile_object(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"profile field '{field_name}' must be an object")
    return value


def _require_profile_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"profile field '{field_name}' must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"profile field '{field_name}' must not be empty")
    return cleaned


def _load_brain_mode(raw_profile: dict[str, Any]) -> str:
    value = raw_profile.get("brain_mode")
    if value is None:
        return "accumulative"

    if not isinstance(value, str):
        raise ValueError("profile field 'brain_mode' must be a string")

    cleaned = value.strip()
    if cleaned not in SUPPORTED_BRAIN_MODES:
        supported = ", ".join(SUPPORTED_BRAIN_MODES)
        raise ValueError(
            f"unsupported profile brain_mode: {cleaned}. Supported: {supported}"
        )
    return cleaned


def _load_working_context_format(raw_profile: dict[str, Any]) -> str:
    value = raw_profile.get("working_context_format", DEFAULT_WORKING_CONTEXT_FORMAT)
    if not isinstance(value, str):
        raise ValueError("profile field 'working_context_format' must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError(
            "profile field 'working_context_format' must not contain surrounding whitespace"
        )
    if cleaned not in SUPPORTED_WORKING_CONTEXT_FORMATS:
        supported = ", ".join(SUPPORTED_WORKING_CONTEXT_FORMATS)
        raise ValueError(
            f"unsupported profile working_context_format: {cleaned}. Supported: {supported}"
        )
    return cleaned


def _load_artifact_generator_mode(raw_profile: dict[str, Any]) -> str:
    value = raw_profile.get("artifact_generator_mode", DEFAULT_ARTIFACT_GENERATOR_MODE)
    if not isinstance(value, str):
        raise ValueError("profile field 'artifact_generator_mode' must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError(
            "profile field 'artifact_generator_mode' must not contain surrounding whitespace"
        )
    if cleaned not in SUPPORTED_ARTIFACT_GENERATOR_MODES:
        supported = ", ".join(SUPPORTED_ARTIFACT_GENERATOR_MODES)
        raise ValueError(
            f"unsupported profile artifact_generator_mode: {cleaned}. Supported: {supported}"
        )
    return cleaned


def _load_artifact_filter_mode(raw_profile: dict[str, Any]) -> str:
    value = raw_profile.get("artifact_filter_mode", DEFAULT_ARTIFACT_FILTER_MODE)
    if not isinstance(value, str):
        raise ValueError("profile field 'artifact_filter_mode' must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError(
            "profile field 'artifact_filter_mode' must not contain surrounding whitespace"
        )
    if cleaned not in SUPPORTED_ARTIFACT_FILTER_MODES:
        supported = ", ".join(SUPPORTED_ARTIFACT_FILTER_MODES)
        raise ValueError(
            f"unsupported profile artifact_filter_mode: {cleaned}. Supported: {supported}"
        )
    return cleaned


def _load_brain_in_policy(raw_profile: dict[str, Any]) -> BrainInPolicy:
    value = raw_profile.get("brain_in")
    if value is None:
        return BrainInPolicy(type="empty", ref=None)
    if not isinstance(value, dict):
        raise ValueError("profile field 'brain_in' must be an object")

    brain_in_type = _require_profile_string(value, "type")
    if brain_in_type not in SUPPORTED_ORDINARY_BRAIN_IN_TYPES:
        supported = ", ".join(SUPPORTED_ORDINARY_BRAIN_IN_TYPES)
        raise ValueError(
            f"unsupported ordinary-run brain_in.type: {brain_in_type}. Supported: {supported}"
        )

    brain_in_ref = _require_optional_profile_string_or_null(value, "ref")
    if brain_in_ref is not None:
        raise ValueError("profile field 'brain_in.ref' is not supported for this step")

    return BrainInPolicy(type=brain_in_type, ref=brain_in_ref)


def _load_brain_out_policy(raw_profile: dict[str, Any]) -> BrainOutPolicy:
    value = raw_profile.get("brain_out")
    if value is None:
        return BrainOutPolicy(mode="continue", ref=None)
    if not isinstance(value, dict):
        raise ValueError("profile field 'brain_out' must be an object")

    brain_out_mode = _require_profile_string(value, "mode")
    if brain_out_mode not in SUPPORTED_ORDINARY_BRAIN_OUT_MODES:
        supported = ", ".join(SUPPORTED_ORDINARY_BRAIN_OUT_MODES)
        raise ValueError(
            f"unsupported ordinary-run brain_out.mode: {brain_out_mode}. Supported: {supported}"
        )

    brain_out_ref = _require_optional_profile_string_or_null(value, "ref")
    if brain_out_ref is not None:
        raise ValueError("profile field 'brain_out.ref' is not supported for this step")

    return BrainOutPolicy(mode=brain_out_mode, ref=brain_out_ref)


def _require_optional_profile_string_or_null(
    data: dict[str, Any],
    field_name: str,
) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"profile field '{field_name}' must be a string or null")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"profile field '{field_name}' must not be empty")
    return cleaned


def _validate_ordinary_run_lifecycle(
    *,
    brain_mode: str,
    brain_in: BrainInPolicy,
    brain_out: BrainOutPolicy,
) -> None:
    if brain_in.type not in SUPPORTED_ORDINARY_BRAIN_IN_TYPES:
        raise ValueError(
            f"unsupported ordinary-run brain_in.type: {brain_in.type}"
        )

    if brain_mode == "accumulative" and brain_out.mode != "continue":
        if brain_out.mode == "snapshot":
            return
        raise ValueError(
            "ordinary-run brain_mode='accumulative' requires brain_out.mode in {'continue', 'snapshot'}"
        )

    if brain_mode == "static" and brain_out.mode != "empty":
        if brain_out.mode == "snapshot":
            return
        raise ValueError(
            "ordinary-run brain_mode='static' requires brain_out.mode in {'empty', 'snapshot'}"
        )


def _require_profile_int(data: dict[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"profile field '{field_name}' must be an integer")
    if value <= 0:
        raise ValueError(f"profile field '{field_name}' must be greater than zero")
    return value


def _require_profile_string_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"profile field '{field_name}' must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"profile field '{field_name}' must contain only strings"
            )
        cleaned = item.strip()
        if not cleaned:
            raise ValueError(
                f"profile field '{field_name}' must not contain empty strings"
            )
        normalized.append(cleaned)
    return normalized


def _load_terminal_event(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    if not lines:
        raise ValueError(f"event log must not be empty: {path}")
    event = json.loads(lines[-1])
    if not isinstance(event, dict):
        raise ValueError(f"terminal event must be an object: {path}")
    return event


def _is_quota_exhausted_event_log(path: Path) -> bool:
    event = _load_terminal_event(path)
    if event.get("event_type") != "task_failed":
        return False
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return False
    failure_reason = payload.get("failure_reason")
    if not isinstance(failure_reason, str):
        return False
    return "429" in failure_reason or "RESOURCE_EXHAUSTED" in failure_reason


def main() -> None:
    args = parse_args()
    repo_root = REPO_ROOT
    profile = load_profile(args.profile) if args.profile is not None else None
    if args.backend is not None and profile is not None and args.backend != profile.backend:
        raise ValueError(
            "explicit --backend conflicts with profile backend: "
            f"{args.backend} != {profile.backend}"
        )

    selected_backend_name = (
        profile.backend
        if profile is not None
        else (args.backend if args.backend is not None else DEFAULT_BACKEND)
    )
    backend = resolve_backend(selected_backend_name)
    scenario_plan = resolve_ordinary_scenario_layers(profile)
    execution_modes = resolve_execution_modes(profile)
    scenario_ids = scenario_plan.all_scenario_ids
    showcase_scenario_id = profile.showcase if profile is not None else SHOWCASE_SCENARIO_ID
    inter_scenario_delay_seconds = (
        profile.inter_scenario_delay_seconds
        if profile is not None
        else DEFAULT_SCENARIO_DELAY_SECONDS
    )
    artifact_generator_mode = (
        args.artifact_generator_mode
        if args.artifact_generator_mode is not None
        else (
            getattr(profile, "artifact_generator_mode", DEFAULT_ARTIFACT_GENERATOR_MODE)
            if profile is not None
            else DEFAULT_ARTIFACT_GENERATOR_MODE
        )
    )
    artifact_filter_mode = (
        args.artifact_filter_mode
        if args.artifact_filter_mode is not None
        else (
            getattr(profile, "artifact_filter_mode", DEFAULT_ARTIFACT_FILTER_MODE)
            if profile is not None
            else DEFAULT_ARTIFACT_FILTER_MODE
        )
    )
    working_context_format = (
        args.working_context_format
        if args.working_context_format is not None
        else (
            getattr(profile, "working_context_format", DEFAULT_WORKING_CONTEXT_FORMAT)
            if profile is not None
            else DEFAULT_WORKING_CONTEXT_FORMAT
        )
    )

    if backend.backend == "gemini":
        agent_metadata = backend.get_benchmark_agent_metadata(
            adapter_name=backend.adapter_name,
            model=profile.model if profile is not None else None,
        )
    else:
        agent_metadata = backend.get_benchmark_agent_metadata(
            adapter_name=backend.adapter_name
        )
    run_id = build_run_id(adapter_name=agent_metadata["adapter"])

    print("=== Persistent Reasoning Benchmark Pipeline ===")
    print(f"repo_root: {repo_root}")
    print(f"scenarios: {len(scenario_ids)}")
    print(f"diagnostic_scenarios: {len(scenario_plan.diagnostic_scenario_ids)}")
    print(f"stress_scenarios: {len(scenario_plan.stress_scenario_ids)}")
    print(f"modes: {execution_modes}")
    print(f"backend: {backend.backend}")
    print(f"artifact_generator_mode: {artifact_generator_mode}")
    print(f"artifact_filter_mode: {artifact_filter_mode}")
    print(f"working_context_format: {working_context_format}")
    if profile is not None:
        print(f"profile: {profile.name}")
        print(f"model: {profile.model}")
        print(f"diagnostic_modes.pr_ephemeral: {str(profile.diagnostic_modes.pr_ephemeral).lower()}")
        print(
            "diagnostic_modes.post_run_artifact_harvest: "
            f"{str(profile.diagnostic_modes.post_run_artifact_harvest).lower()}"
        )
        print(f"brain_mode: {profile.brain_mode}")
        print(f"brain_in.type: {profile.brain_in.type}")
        print(f"brain_out.mode: {profile.brain_out.mode}")
    print(f"run_id: {run_id}")
    print("execution_mode: real benchmark execution via selected adapter")
    print()

    print("[PREP] applying storage-governed pre-run brain lifecycle")
    apply_pre_run_brain_lifecycle(repo_root, profile=profile)
    print("[PREP] brain lifecycle complete")
    print()

    print("[PREP] cleaning temporary benchmark result artifacts")
    clean_temporary_benchmark_results(repo_root)
    print("[PREP] result cleanup complete")
    print()

    print("[PREFLIGHT] validating benchmark environment")
    run_preflight(repo_root, backend=backend.backend)
    print("[PREFLIGHT] passed")
    print()

    print("[PREP] resolving composition-backed execution scenarios")
    resolved_artifact_paths = write_resolved_execution_artifacts(
        repo_root,
        run_id=run_id,
        scenario_ids=scenario_ids,
    )
    if resolved_artifact_paths:
        for artifact_path in resolved_artifact_paths:
            print(f"[PREP] resolved execution artifact saved: {artifact_path}")
    else:
        print("[PREP] no composition-backed execution artifacts required")
    print()

    execution_completed = False

    try:
        execution_state = run_all(
            repo_root,
            backend=backend,
            scenario_ids=scenario_ids,
            execution_modes=execution_modes,
            inter_scenario_delay_seconds=inter_scenario_delay_seconds,
            quota_policy=profile,
            artifact_generator_mode=artifact_generator_mode,
            working_context_format=working_context_format,
            artifact_filter_mode=artifact_filter_mode,
        )
        execution_completed = True

        print()
        print("=== Benchmark execution complete ===")
        print()

        run_metadata = {
            "backend": backend.backend,
            "provider_profile": profile.name if profile is not None else None,
            "diagnostic_modes": {
                "pr_ephemeral": (
                    profile.diagnostic_modes.pr_ephemeral if profile is not None else False
                ),
                "post_run_artifact_harvest": (
                    profile.diagnostic_modes.post_run_artifact_harvest
                    if profile is not None
                    else False
                ),
            },
            "executed_modes": list(execution_modes),
            "mode_to_key_mapping_enabled": (
                bool(profile is not None and backend.backend == "gemini" and profile.mode_to_key_mapping == "strict")
                if profile is not None
                else False
            ),
            "inter_scenario_delay_seconds": inter_scenario_delay_seconds,
            "quota_stop_reason": execution_state.quota_stop_reason,
            "429_count_total": execution_state.total_429_count,
            "selected_scenario_subset": list(scenario_ids),
            "showcase_scenario_id": showcase_scenario_id,
        }

        scenario_layer_manifest_path = write_scenario_layer_manifest(
            repo_root,
            run_id=run_id,
            diagnostic_scenario_ids=scenario_plan.diagnostic_scenario_ids,
            stress_scenario_ids=scenario_plan.stress_scenario_ids,
        )
        print(f"[POST] scenario layers saved: {scenario_layer_manifest_path}")
        interpretation_support_manifest_path = write_scenario_interpretation_support_manifest(
            repo_root,
            run_id=run_id,
            diagnostic_scenario_ids=scenario_plan.diagnostic_scenario_ids,
            stress_scenario_ids=scenario_plan.stress_scenario_ids,
        )
        print(
            "[POST] scenario interpretation support saved: "
            f"{interpretation_support_manifest_path}"
        )

        try:
            run_post_processing(
                repo_root,
                run_id=run_id,
                agent_metadata=agent_metadata,
                backend=backend,
                scenario_ids=scenario_ids,
                showcase_scenario_id=showcase_scenario_id,
                run_metadata=run_metadata,
            )
        except Exception as exc:
            print(
                f"[WARN] post-processing failed: {type(exc).__name__}: {exc}"
            )
        try:
            retention_artifacts = generate_retention_artifacts_for_run(
                repo_root=repo_root,
                run_id=run_id,
                scenario_ids=scenario_ids,
                source_modes=execution_modes,
                overwrite=OVERWRITE_EXISTING_ARTIFACTS,
            )
            for retention_layer_path, retention_summary_path in retention_artifacts:
                print(f"[POST] retention layer saved: {retention_layer_path}")
                print(f"[POST] retention summary saved: {retention_summary_path}")
        except Exception as exc:
            print(
                f"[WARN] retention generation failed: {type(exc).__name__}: {exc}"
            )
    finally:
        print()
        harvest_report_path = run_post_run_artifact_harvest(
            repo_root=repo_root,
            run_id=run_id,
            scenario_ids=scenario_ids,
            source_modes=execution_modes,
            enabled=bool(
                profile is not None and profile.diagnostic_modes.post_run_artifact_harvest
            ),
            runtime_available=_post_run_harvest_runtime_available(profile)
            and execution_completed,
            skip_reason=_post_run_harvest_skip_reason(
                profile=profile,
                execution_completed=execution_completed,
            ),
        )
        print(f"[FINALIZE] post-run artifact harvest report saved: {harvest_report_path}")
        print("[FINALIZE] applying storage-governed post-run brain lifecycle")
        apply_post_run_brain_lifecycle(repo_root, run_id=run_id, profile=profile)
        print("[FINALIZE] brain lifecycle complete")


if __name__ == "__main__":
    main()
