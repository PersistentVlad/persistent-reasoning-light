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

from benchmark_adapters.common.benchmark_modes import PR_LIGHT_BRAIN
from benchmark_adapters.gemini import adapter as gemini_adapter
from reasoning_brain_storage.tools import BrainRef, initialize_brain


class PRLightBrainGeminiIntegrationTests(unittest.TestCase):
    def test_pr_light_brain_decision_suggestion_updates_next_loaded_context(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(repo_root)

            first_result = gemini_adapter.run_scenario(
                "sc_test_decision",
                mode=PR_LIGHT_BRAIN,
                task_text="Follow the scenario and suggest one decision artifact.",
                agent_output=(
                    "Final Answer:\nUse the cached parse result.\n\n"
                    "Artifact Suggestion:\n"
                    '{"id":"decision_cached_parse_result","type":"decision","summary":"use cached parse result"}'
                ),
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            runtime_root = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
            )
            persisted_path = (
                runtime_root
                / "brain"
                / "decisions"
                / "decision_cached_parse_result.json"
            )
            self.assertTrue(persisted_path.exists())

            working_context_path = runtime_root / "views" / "working_context.json"
            working_context = json.loads(working_context_path.read_text(encoding="utf-8"))
            self.assertEqual(
                working_context["decisions"],
                ["decision_cached_parse_result"],
            )
            self.assertEqual(working_context["constraints"], [])
            self.assertEqual(working_context["open_issues"], [])
            self.assertIsNone(working_context["active_task"])

            second_result = gemini_adapter.run_scenario(
                "sc_test_decision",
                mode=PR_LIGHT_BRAIN,
                task_text="Follow the scenario again.",
                agent_output="Final Answer:\nAcknowledged.\n\nArtifact Suggestion:\nNONE",
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            self.assertEqual(first_result["artifact_suggestion"]["type"], "decision")
            self.assertEqual(second_result["artifact_suggestion"], None)
            self.assertEqual(
                second_result["context"]["decisions"],
                ["decision_cached_parse_result"],
            )
            self.assertEqual(second_result["context"]["constraints"], [])
            self.assertEqual(second_result["context"]["open_issues"], [])
            self.assertIsNone(second_result["context"]["active_task"])
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

    scenario_id = "sc_test_decision"
    (scenarios_root / f"{scenario_id}.md").write_text(
        "# Test Scenario\n\nMake one deterministic decision.\n",
        encoding="utf-8",
    )
    (scenarios_root / f"{scenario_id}.json").write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "scenario_name": "Decision Persistence Test",
                "scenario_type": "integration",
                "description": "Minimal benchmark scenario for PR_LIGHT_BRAIN decision persistence.",
                "steps": [
                    {
                        "step_id": "step_1",
                        "instruction": "Return a final answer and one decision artifact suggestion.",
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
    source_empty_root = _repo_root() / "reasoning_brain_storage" / "templates" / "empty"
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


def _repo_root() -> Path:
    return REPO_ROOT


def _test_repo_root() -> Path:
    temp_root = Path(__file__).resolve().parent / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root / f"repo_{uuid4().hex}"


if __name__ == "__main__":
    unittest.main()
