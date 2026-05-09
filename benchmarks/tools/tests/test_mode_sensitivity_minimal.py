# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))

from benchmark_adapters.common.benchmark_modes import BASELINE, PR_LIGHT, PR_LIGHT_BRAIN
from benchmark_adapters.gemini import adapter as gemini_adapter
from reasoning_brain_storage.tools import BrainRef, initialize_brain


class MinimalModeSensitivityTests(unittest.TestCase):
    def test_modes_show_structural_context_sensitivity(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(repo_root)
            persisted_decision_path = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "decision_use_cache.json"
            )

            decision_output = (
                "Final Answer:\nUse the cached parse result.\n\n"
                "Artifact Suggestion:\n"
                '{"id":"decision_use_cache","type":"decision","summary":"use cached parse result"}'
            )
            none_output = "Final Answer:\nAcknowledged.\n\nArtifact Suggestion:\nNONE"

            baseline_result = gemini_adapter.run_scenario(
                "sc_test_mode_sensitivity",
                mode=BASELINE,
                task_text="Follow the scenario deterministically.",
                agent_output=decision_output,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )
            pr_light_result = gemini_adapter.run_scenario(
                "sc_test_mode_sensitivity",
                mode=PR_LIGHT,
                task_text="Follow the scenario deterministically.",
                agent_output=decision_output,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )
            runtime_working_context_after_pr_light = _load_runtime_working_context(repo_root)
            persisted_decision_exists_after_pr_light = persisted_decision_path.exists()
            pr_light_brain_run_1 = gemini_adapter.run_scenario(
                "sc_test_mode_sensitivity",
                mode=PR_LIGHT_BRAIN,
                task_text="Follow the scenario deterministically.",
                agent_output=decision_output,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            runtime_working_context_after_run_1 = _load_runtime_working_context(repo_root)
            self.assertEqual(
                runtime_working_context_after_run_1,
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": ["decision_use_cache"],
                    "open_issues": [],
                },
            )

            pr_light_brain_run_2 = gemini_adapter.run_scenario(
                "sc_test_mode_sensitivity",
                mode=PR_LIGHT_BRAIN,
                task_text="Follow the scenario deterministically.",
                agent_output=none_output,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            runtime_working_context_after_run_2 = _load_runtime_working_context(repo_root)
            self.assertEqual(
                baseline_result["context"],
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
            self.assertIsNone(baseline_result["artifact_suggestion"])
            self.assertEqual(
                pr_light_result["context"],
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
            self.assertEqual(
                pr_light_result["artifact_suggestion"],
                {
                    "id": "decision_use_cache",
                    "type": "decision",
                    "summary": "use cached parse result",
                },
            )
            self.assertEqual(
                runtime_working_context_after_pr_light,
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
            self.assertFalse(persisted_decision_exists_after_pr_light)
            self.assertEqual(
                pr_light_brain_run_1["context"],
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
            self.assertEqual(
                pr_light_brain_run_1["artifact_suggestion"],
                {
                    "id": "decision_use_cache",
                    "type": "decision",
                    "summary": "use cached parse result",
                },
            )
            self.assertEqual(
                pr_light_brain_run_2["context"],
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": ["decision_use_cache"],
                    "open_issues": [],
                },
            )

            self.assertEqual(runtime_working_context_after_run_2, pr_light_brain_run_2["context"])
            self.assertTrue(persisted_decision_path.exists())

            self.assertNotEqual(pr_light_brain_run_2["context"], baseline_result["context"])
            self.assertNotEqual(pr_light_brain_run_2["context"], pr_light_result["context"])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)


def _build_minimal_benchmark_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=False)

    _write_scenario(repo_root)
    _copy_canonical_empty_template(repo_root)
    _initialize_runtime_and_seeded_brains(repo_root)


def _write_scenario(repo_root: Path) -> None:
    scenarios_root = repo_root / "benchmarks" / "scenarios"
    scenarios_root.mkdir(parents=True, exist_ok=True)

    scenario_id = "sc_test_mode_sensitivity"
    (scenarios_root / f"{scenario_id}.md").write_text(
        "# Test Scenario\n\nMake one deterministic decision.\n",
        encoding="utf-8",
    )
    (scenarios_root / f"{scenario_id}.json").write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "scenario_name": "Mode Sensitivity Test",
                "scenario_type": "integration",
                "description": "Minimal scenario for validating mode sensitivity with a decision artifact.",
                "steps": [
                    {
                        "step_id": "step_1",
                        "instruction": "Return a final answer and, when appropriate, one decision artifact suggestion.",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _copy_canonical_empty_template(repo_root: Path) -> None:
    source_empty_root = REPO_ROOT / "reasoning_brain_storage" / "templates" / "empty"
    target_empty_root = repo_root / "reasoning_brain_storage" / "templates" / "empty"
    target_empty_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_empty_root, target_empty_root)


def _initialize_runtime_and_seeded_brains(repo_root: Path) -> None:
    empty_root = repo_root / "reasoning_brain_storage" / "templates" / "empty"
    benchmarks_root = repo_root / "reasoning_brain_storage" / "benchmarks"
    runtime_root = benchmarks_root / "runtime"
    seeded_root = benchmarks_root / "seeded"

    initialize_brain(
        source=BrainRef(type="empty", path=empty_root),
        target_root=runtime_root,
    )
    initialize_brain(
        source=BrainRef(type="empty", path=empty_root),
        target_root=seeded_root,
    )


def _load_runtime_working_context(repo_root: Path) -> dict[str, object]:
    working_context_path = (
        repo_root
        / "reasoning_brain_storage"
        / "benchmarks"
        / "runtime"
        / "views"
        / "working_context.json"
    )
    return json.loads(working_context_path.read_text(encoding="utf-8"))


def _test_repo_root() -> Path:
    temp_root = Path(__file__).resolve().parent / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root / f"repo_{uuid4().hex}"


if __name__ == "__main__":
    unittest.main()
