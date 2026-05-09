# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Run baseline benchmark scenarios for Persistent Reasoning Light.

This script executes all configured scenarios in baseline mode using the
selected benchmark adapter, then derives *.result.json from *.events.jsonl.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple


# Temporary PoC import bootstrap.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))


import benchmark_adapters.gemini.adapter as gemini_adapter
import benchmark_adapters.openai_codex.adapter as openai_codex_adapter
from benchmark_adapters.common.benchmark_modes import BASELINE
from benchmark_adapters.common.benchmark_paths import get_benchmark_paths, result_json_path
from benchmarks.tools.compute_metrics_from_events import derive_result_artifact


SCENARIOS = [
    "sc_0_interrupt_compress_continue",
    "sc_1_context_drift",
    "sc_2_context_compression",
    "sc_03_math_state_loss",
    "sc_04_chain_collapse",
    "sc_5_math_reasoning",
    "sc_06_plan_reset",
]

DEFAULT_TASK = "Execute the scenario faithfully and provide structured reasoning."
SUPPORTED_BACKENDS = ("gemini", "openai_codex")
DEFAULT_BACKEND = "gemini"
DEFAULT_SCENARIO_DELAY_SECONDS = 20
OVERWRITE_EXISTING_ARTIFACTS = True


class BackendSelection(NamedTuple):
    backend: str
    adapter_name: str
    run_scenario: Callable[..., dict[str, Any]]
    get_benchmark_agent_metadata: Callable[..., dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run baseline benchmark scenarios with a selectable backend."
    )
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default=DEFAULT_BACKEND,
        help="Benchmark execution backend to use.",
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
    *,
    repo_root: Path,
    backend: BackendSelection,
) -> None:
    """
    Run one scenario in baseline mode and derive result.json from events.jsonl.
    """
    print(f"[RUN][baseline] scenario={scenario_id} backend={backend.backend}")

    result = backend.run_scenario(
        scenario_id,
        mode=BASELINE,
        task_text=DEFAULT_TASK,
        agent_output=None,
        adapter_name=backend.adapter_name,
        repo_root=repo_root,
        overwrite_existing_artifacts=OVERWRITE_EXISTING_ARTIFACTS,
    )

    events_path = result["event_log_path"]
    paths = get_benchmark_paths(repo_root)
    json_path = result_json_path(paths, BASELINE, scenario_id)
    derive_result_artifact(
        events_path,
        output_path=json_path,
        adapter_name=backend.adapter_name,
        overwrite=OVERWRITE_EXISTING_ARTIFACTS,
    )

    print(f"[OK][baseline] result saved: {json_path}")


def run_all(repo_root: Path, *, backend: BackendSelection) -> None:
    """
    Run all configured baseline scenarios.
    """
    for index, scenario_id in enumerate(SCENARIOS):
        run_single(
            scenario_id,
            repo_root=repo_root,
            backend=backend,
        )
        if index < len(SCENARIOS) - 1:
            print(
                "[PAUSE][baseline] "
                f"sleeping {DEFAULT_SCENARIO_DELAY_SECONDS}s before next scenario"
            )
            time.sleep(DEFAULT_SCENARIO_DELAY_SECONDS)


def main() -> None:
    args = parse_args()
    backend = resolve_backend(args.backend)

    print("=== Run Baseline Benchmark ===")
    print(f"repo_root: {REPO_ROOT}")
    print(f"scenarios: {len(SCENARIOS)}")
    print(f"backend: {backend.backend}")
    print("execution_mode: real benchmark execution via selected adapter")
    print()

    run_all(REPO_ROOT, backend=backend)

    print()
    print("=== Baseline benchmark run complete ===")


if __name__ == "__main__":
    main()
