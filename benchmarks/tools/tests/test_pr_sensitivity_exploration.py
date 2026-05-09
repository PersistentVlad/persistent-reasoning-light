# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))

from benchmark_adapters.common.benchmark_modes import BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN
from benchmarks import run_experiments as run_experiments_module
from benchmarks.tools import explore_pr_sensitivity as explore_module
from benchmarks.tools.explore_pr_sensitivity import (
    detect_harm,
    detect_plateau,
    explore_pr_sensitivity,
)
from reasoning_brain_storage.tools import BrainRef, initialize_brain


class PRSensitivityExplorationTests(unittest.TestCase):
    def test_run_experiments_import_smoke(self) -> None:
        self.assertTrue(callable(run_experiments_module.main))

    def test_run_experiments_delegates_to_exploration_harness(self) -> None:
        fake_args = SimpleNamespace(
            profile="gemini_flash_lite_latest",
            repo_root=str(REPO_ROOT),
            output_dir=str(REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity"),
            max_runs=3,
            plateau_window=2,
            harm_window=1,
            epsilon_score=0.05,
            epsilon_retrieval=0.05,
        )
        fake_outputs = {
            "summary_path": REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity" / "classification_summary.json",
            "markdown_path": REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity" / "classification_summary.md",
        }

        with patch.object(run_experiments_module, "parse_args", return_value=fake_args), patch.object(
            run_experiments_module,
            "explore_pr_sensitivity",
            return_value=fake_outputs,
        ) as explore_mock, patch.object(
            run_experiments_module,
            "load_profile",
            return_value=SimpleNamespace(diagnostic_modes=SimpleNamespace(pr_ephemeral=False)),
        ) as load_profile_mock, patch("builtins.print") as print_mock:
            run_experiments_module.main()

        load_profile_mock.assert_called_once_with(fake_args.profile)
        explore_mock.assert_called_once_with(
            repo_root=Path(fake_args.repo_root),
            output_dir=Path(fake_args.output_dir),
            scenario_regions=run_experiments_module.DEFAULT_EXPERIMENT_SCENARIO_REGIONS,
            include_pr_ephemeral=False,
            max_runs=fake_args.max_runs,
            plateau_window=fake_args.plateau_window,
            harm_window=fake_args.harm_window,
            epsilon_score=fake_args.epsilon_score,
            epsilon_retrieval=fake_args.epsilon_retrieval,
        )
        self.assertEqual(print_mock.call_count, 2)

    def test_run_experiments_enables_pr_ephemeral_when_profile_requests_it(self) -> None:
        fake_args = SimpleNamespace(
            profile="gemini_flash_latest",
            repo_root=str(REPO_ROOT),
            output_dir=str(REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity"),
            max_runs=3,
            plateau_window=2,
            harm_window=1,
            epsilon_score=0.05,
            epsilon_retrieval=0.05,
        )
        fake_outputs = {
            "summary_path": REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity" / "classification_summary.json",
            "markdown_path": REPO_ROOT / "benchmarks" / "reports" / "pr_sensitivity" / "classification_summary.md",
        }

        with patch.object(run_experiments_module, "parse_args", return_value=fake_args), patch.object(
            run_experiments_module,
            "explore_pr_sensitivity",
            return_value=fake_outputs,
        ) as explore_mock, patch.object(
            run_experiments_module,
            "load_profile",
            return_value=SimpleNamespace(diagnostic_modes=SimpleNamespace(pr_ephemeral=True)),
        ), patch("builtins.print"):
            run_experiments_module.main()

        self.assertTrue(explore_mock.call_args.kwargs["include_pr_ephemeral"])

    def test_exploration_harness_writes_machine_readable_outputs(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(
                repo_root,
                scenario_ids=(
                    "sc_0_interrupt_compress_continue",
                    "sc_06_plan_reset",
                    "sc_7_stateless_direct_transform",
                ),
            )

            outputs = explore_pr_sensitivity(
                repo_root=repo_root,
                output_dir=repo_root / "benchmarks" / "reports" / "pr_sensitivity",
                scenario_regions={
                    "strong_gain": ["sc_0_interrupt_compress_continue"],
                    "neutral": ["sc_7_stateless_direct_transform"],
                    "risk": ["sc_06_plan_reset"],
                },
                max_runs=4,
                output_provider=_manual_output_provider,
            )

            summary = outputs["summary"]
            self.assertEqual(summary["backend"], "gemini")
            self.assertEqual(summary["diagnostic_modes"], {"pr_ephemeral": False})
            self.assertTrue(outputs["summary_path"].exists())
            self.assertTrue(outputs["markdown_path"].exists())
            self.assertEqual(len(summary["scenario_summaries"]), 3)

            by_id = {
                item["scenario_id"]: item
                for item in summary["scenario_summaries"]
            }

            neutral_summary = by_id["sc_7_stateless_direct_transform"]
            self.assertEqual(neutral_summary["observed_classification"], "neutral")

            gain_summary = by_id["sc_0_interrupt_compress_continue"]
            self.assertEqual(gain_summary["observed_classification"], "strong_gain")
            self.assertTrue(gain_summary["plateau_reached"])

            risk_summary = by_id["sc_06_plan_reset"]
            self.assertEqual(risk_summary["observed_classification"], "risk")
            self.assertTrue(risk_summary["degradation_detected"])

            neutral_trajectory = _load_json(
                repo_root
                / "benchmarks"
                / "reports"
                / "pr_sensitivity"
                / "sc_7_stateless_direct_transform.trajectory.json"
            )
            self.assertEqual(
                neutral_trajectory["reference_runs"]["baseline"]["context"],
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
            self.assertIsNone(neutral_trajectory["reference_runs"]["pr_ephemeral"])
            self.assertTrue(
                all(run["artifact_count_total"] == 0 for run in neutral_trajectory["pr_light_brain_runs"])
            )
            self.assertTrue(
                all(run["context_size"] == 0 for run in neutral_trajectory["pr_light_brain_runs"])
            )
            self.assertIn("snapshot_series", neutral_trajectory)
            self.assertIn("plateau_interpretation", neutral_trajectory)
            self.assertIn("harm_interpretation", neutral_trajectory)
            self.assertIn("final_snapshot_delta_summary", neutral_trajectory)
            self.assertTrue(
                all(Path(run["snapshot_root"]).is_dir() for run in neutral_trajectory["pr_light_brain_runs"])
            )
            self.assertTrue(
                all(
                    run["snapshot_state_summary"]["artifact_count_total"] == 0
                    for run in neutral_trajectory["pr_light_brain_runs"]
                )
            )
            self.assertIsNone(
                neutral_trajectory["pr_light_brain_runs"][0]["snapshot_comparison_to_previous"]
            )
            if len(neutral_trajectory["pr_light_brain_runs"]) > 1:
                second_neutral_run = neutral_trajectory["pr_light_brain_runs"][1]
                self.assertEqual(
                    second_neutral_run["snapshot_comparison_to_previous"]["artifact_count_total"]["delta"],
                    0,
                )
                self.assertEqual(
                    second_neutral_run["snapshot_comparison_to_previous"]["artifact_ids"]["added"],
                    [],
                )
                self.assertEqual(
                    second_neutral_run["snapshot_comparison_to_previous"]["artifact_ids"]["removed"],
                    [],
                )
            neutral_scores = [run["score"] for run in neutral_trajectory["pr_light_brain_runs"]]
            self.assertTrue(all(abs(score - neutral_scores[0]) <= 0.05 for score in neutral_scores))

            gain_trajectory = _load_json(
                repo_root
                / "benchmarks"
                / "reports"
                / "pr_sensitivity"
                / "sc_0_interrupt_compress_continue.trajectory.json"
            )
            first_gain_run = gain_trajectory["pr_light_brain_runs"][0]
            later_gain_run = gain_trajectory["pr_light_brain_runs"][1]
            self.assertEqual(first_gain_run["artifact_count_total"], 1)
            self.assertEqual(
                first_gain_run["snapshot_state_summary"]["artifact_count_total"],
                1,
            )
            self.assertTrue(Path(first_gain_run["snapshot_root"]).is_dir())
            self.assertIsNone(first_gain_run["snapshot_comparison_to_previous"])
            self.assertEqual(later_gain_run["working_context"]["decisions"], ["decision_use_cache"])
            self.assertTrue(Path(later_gain_run["snapshot_root"]).is_dir())
            self.assertIsNotNone(later_gain_run["snapshot_comparison_to_previous"])
            self.assertEqual(
                later_gain_run["snapshot_comparison_to_previous"]["artifact_count_total"]["delta"],
                0,
            )
            self.assertEqual(
                later_gain_run["snapshot_comparison_to_previous"]["working_context_diff"]["decisions_added"],
                [],
            )
            self.assertGreater(later_gain_run["score"], first_gain_run["score"])
            self.assertIn("plateau_interpretation", gain_trajectory)
            self.assertIn("harm_interpretation", gain_trajectory)
            self.assertIn("final_snapshot_delta_summary", gain_trajectory)
            self.assertIn("1", gain_trajectory["snapshot_series"])

            risk_trajectory = _load_json(
                repo_root
                / "benchmarks"
                / "reports"
                / "pr_sensitivity"
                / "sc_06_plan_reset.trajectory.json"
            )
            self.assertIn("plateau_interpretation", risk_trajectory)
            self.assertIn("harm_interpretation", risk_trajectory)
            self.assertIn("final_snapshot_delta_summary", risk_trajectory)
            self.assertIn(
                "snapshot_delta_indicates_state_growth",
                risk_trajectory["harm_interpretation"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_exploration_harness_includes_pr_ephemeral_only_when_enabled(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(
                repo_root,
                scenario_ids=("sc_0_interrupt_compress_continue",),
            )

            outputs = explore_pr_sensitivity(
                repo_root=repo_root,
                output_dir=repo_root / "benchmarks" / "reports" / "pr_sensitivity",
                scenario_regions={
                    "strong_gain": ["sc_0_interrupt_compress_continue"],
                },
                include_pr_ephemeral=True,
                max_runs=2,
                output_provider=_manual_output_provider,
            )

            self.assertEqual(outputs["summary"]["diagnostic_modes"], {"pr_ephemeral": True})
            trajectory = _load_json(
                outputs["output_dir"] / "sc_0_interrupt_compress_continue.trajectory.json"
            )
            self.assertIsNotNone(trajectory["reference_runs"]["pr_ephemeral"])
            self.assertEqual(
                trajectory["reference_runs"]["pr_ephemeral"]["context"]["decisions"],
                [],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_killer_scenario_isolated_validation_shows_stress_signal(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(
                repo_root,
                scenario_ids=("sc_99_killer_all_scenarios",),
            )

            outputs = explore_pr_sensitivity(
                repo_root=repo_root,
                output_dir=repo_root / "benchmarks" / "reports" / "pr_sensitivity",
                scenario_regions={
                    "stress": ["sc_99_killer_all_scenarios"],
                },
                max_runs=5,
                plateau_window=2,
                harm_window=1,
                output_provider=_manual_output_provider,
            )

            summary = outputs["summary"]
            self.assertEqual(len(summary["scenario_summaries"]), 1)
            self.assertEqual(
                summary["scenario_regions"]["stress"],
                ["sc_99_killer_all_scenarios"],
            )
            trajectory = _load_json(
                repo_root
                / "benchmarks"
                / "reports"
                / "pr_sensitivity"
                / "sc_99_killer_all_scenarios.trajectory.json"
            )

            self.assertEqual(trajectory["scenario_id"], "sc_99_killer_all_scenarios")
            self.assertTrue(trajectory["stress_case"])
            self.assertEqual(trajectory["scenario_role"], "integration_stress")
            self.assertIn("plateau_interpretation", trajectory)
            self.assertIn("harm_interpretation", trajectory)
            self.assertIn("final_snapshot_delta_summary", trajectory)
            self.assertIn("snapshot_series", trajectory)

            summary_item = summary["scenario_summaries"][0]
            self.assertTrue(summary_item["stress_case"])
            self.assertEqual(summary_item["scenario_role"], "integration_stress")

            self.assertIsNone(trajectory["reference_runs"]["pr_ephemeral"])

            pr_light_brain_runs = trajectory["pr_light_brain_runs"]
            self.assertGreaterEqual(len(pr_light_brain_runs), 2)

            first_run = pr_light_brain_runs[0]
            second_run = pr_light_brain_runs[1]

            self.assertTrue(Path(first_run["snapshot_root"]).is_dir())
            self.assertTrue(Path(second_run["snapshot_root"]).is_dir())
            self.assertEqual(first_run["artifact_count_total"], 1)
            self.assertEqual(second_run["artifact_count_total"], 2)
            self.assertEqual(
                second_run["snapshot_comparison_to_previous"]["artifact_count_total"]["delta"],
                1,
            )
            self.assertTrue(
                second_run["snapshot_comparison_to_previous"]["artifact_ids"]["added"]
            )
            self.assertTrue(
                second_run["snapshot_comparison_to_previous"]["working_context_diff"]["decisions_added"]
            )

            persistent_carryover = any(
                bool(run["working_context"]["decisions"]) for run in pr_light_brain_runs[1:]
            )
            score_advantage = any(
                run["pr_ephemeral_score"] is None
                or float(run["score"]) > float(run["pr_ephemeral_score"])
                for run in pr_light_brain_runs
            )
            self.assertTrue(score_advantage or persistent_carryover)

            self.assertTrue(
                any(
                    run["artifact_count_total"] > 1
                    or (
                        run["snapshot_comparison_to_previous"] is not None
                        and run["snapshot_comparison_to_previous"]["artifact_count_total"]["delta"] > 0
                    )
                    for run in pr_light_brain_runs
                )
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_detect_plateau_on_synthetic_trajectory(self) -> None:
        runs = [
            {
                "score_delta": 0.02,
                "retrieval_delta": 0.01,
                "non_persisted_suggestion_count": 1,
                "persisted_artifact_delta": 0,
            },
            {
                "score_delta": 0.01,
                "retrieval_delta": 0.0,
                "non_persisted_suggestion_count": 0,
                "persisted_artifact_delta": 0,
            },
        ]
        self.assertTrue(
            detect_plateau(
                runs,
                plateau_window=2,
                epsilon_score=0.05,
                epsilon_retrieval=0.05,
            )
        )

    def test_detect_harm_on_synthetic_trajectory(self) -> None:
        runs = [
            {
                "score_delta": -0.1,
                "retrieval_delta": 0.0,
                "context_growth_per_run": 1,
                "non_persisted_suggestion_count": 0,
            }
        ]
        self.assertTrue(detect_harm(runs, harm_window=1))

    def test_token_metrics_are_exposed_without_affecting_pr_logic(self) -> None:
        repo_root = _test_repo_root()
        try:
            _build_minimal_benchmark_repo(
                repo_root,
                scenario_ids=("sc_0_interrupt_compress_continue",),
            )
            output_dir = repo_root / "benchmarks" / "reports" / "pr_sensitivity"

            baseline_outputs = explore_pr_sensitivity(
                repo_root=repo_root,
                output_dir=output_dir / "baseline",
                scenario_regions={"strong_gain": ["sc_0_interrupt_compress_continue"]},
                max_runs=4,
                output_provider=_manual_output_provider,
            )
            baseline_trajectory = _load_json(
                baseline_outputs["output_dir"] / "sc_0_interrupt_compress_continue.trajectory.json"
            )

            original_run_scenario = explore_module.gemini_adapter.run_scenario

            pr_light_brain_call_count = 0

            def run_scenario_with_tokens(scenario_id: str, **kwargs: object) -> dict[str, object]:
                nonlocal pr_light_brain_call_count
                result = original_run_scenario(scenario_id, **kwargs)
                mode = kwargs["mode"]
                if mode == BASELINE:
                    token_usage = {"prompt_tokens": 90, "output_tokens": 20, "total_tokens": 110}
                elif mode == PR_EPHEMERAL:
                    token_usage = {"prompt_tokens": 95, "output_tokens": 25, "total_tokens": 120}
                else:
                    pr_light_brain_call_count += 1
                    run_index = pr_light_brain_call_count
                    token_usage = {
                        "prompt_tokens": 100 + run_index,
                        "output_tokens": 30 + run_index,
                        "total_tokens": 130 + (run_index * 2),
                    }
                result["token_usage"] = token_usage
                return result

            with patch.object(
                explore_module.gemini_adapter,
                "run_scenario",
                side_effect=run_scenario_with_tokens,
            ):
                token_outputs = explore_pr_sensitivity(
                    repo_root=repo_root,
                    output_dir=output_dir / "with_tokens",
                    scenario_regions={"strong_gain": ["sc_0_interrupt_compress_continue"]},
                    max_runs=4,
                    output_provider=_manual_output_provider,
                )

            token_trajectory = _load_json(
                token_outputs["output_dir"] / "sc_0_interrupt_compress_continue.trajectory.json"
            )

            self.assertEqual(
                token_trajectory["reference_runs"]["baseline"]["total_tokens"],
                110,
            )
            self.assertEqual(
                token_trajectory["reference_runs"]["pr_ephemeral"],
                None,
            )
            self.assertTrue(
                all(run["prompt_tokens"] is not None for run in token_trajectory["pr_light_brain_runs"])
            )
            self.assertTrue(
                all(run["output_tokens"] is not None for run in token_trajectory["pr_light_brain_runs"])
            )
            self.assertTrue(
                all(run["total_tokens"] is not None for run in token_trajectory["pr_light_brain_runs"])
            )

            cumulative_total_tokens = sum(
                int(run["total_tokens"]) for run in token_trajectory["pr_light_brain_runs"]
            )
            self.assertEqual(
                token_trajectory["cumulative_total_tokens"],
                cumulative_total_tokens,
            )

            if token_trajectory["plateau_reached"]:
                runs_to_plateau = int(token_trajectory["runs_to_plateau"])
                expected_tokens_to_plateau = sum(
                    int(run["total_tokens"])
                    for run in token_trajectory["pr_light_brain_runs"][:runs_to_plateau]
                )
                self.assertEqual(
                    token_trajectory["tokens_to_plateau"],
                    expected_tokens_to_plateau,
                )

            best_score = max(float(run["score"]) for run in token_trajectory["pr_light_brain_runs"])
            initial_score = float(token_trajectory["pr_light_brain_runs"][0]["score"])
            self.assertEqual(
                token_trajectory["score_gain_per_token"],
                round((best_score - initial_score) / cumulative_total_tokens, 6),
            )

            self.assertEqual(
                token_trajectory["plateau_reached"],
                baseline_trajectory["plateau_reached"],
            )
            self.assertEqual(
                token_trajectory["degradation_detected"],
                baseline_trajectory["degradation_detected"],
            )
            self.assertEqual(
                token_trajectory["observed_classification"],
                baseline_trajectory["observed_classification"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)


def _manual_output_provider(scenario_id: str, mode: str, run_index: int) -> str:
    decision_output = (
        "Final Answer:\nUse the cached parse result.\n\n"
        "Artifact Suggestion:\n"
        '{"id":"decision_use_cache","type":"decision","summary":"use cached parse result"}'
    )
    killer_decision_anchor = (
        "Final Answer:\nResume from the compact anchor.\n\n"
        "Artifact Suggestion:\n"
        '{"id":"decision_resume_anchor","type":"decision","summary":"preserve resumable design anchor"}'
    )
    killer_decision_reset = (
        "Final Answer:\nRebuild for offline-first peer sync.\n\n"
        "Artifact Suggestion:\n"
        '{"id":"decision_peer_sync_reset","type":"decision","summary":"reset to offline-first peer sync architecture"}'
    )
    none_output = "Final Answer:\nAcknowledged.\n\nArtifact Suggestion:\nNONE"

    if scenario_id == "sc_7_stateless_direct_transform":
        return none_output

    if scenario_id == "sc_0_interrupt_compress_continue":
        if mode in (PR_EPHEMERAL, PR_LIGHT_BRAIN) and run_index == 1:
            return decision_output
        return none_output

    if scenario_id == "sc_06_plan_reset":
        if mode == BASELINE:
            return none_output
        if mode == PR_EPHEMERAL:
            return decision_output
        if mode == PR_LIGHT_BRAIN:
            return decision_output

    if scenario_id == "sc_99_killer_all_scenarios":
        if mode == BASELINE:
            return none_output
        if mode == PR_EPHEMERAL:
            return killer_decision_anchor if run_index == 1 else none_output
        if mode == PR_LIGHT_BRAIN:
            if run_index == 1:
                return killer_decision_anchor
            if run_index == 2:
                return killer_decision_reset
            return none_output

    return none_output


def _build_minimal_benchmark_repo(repo_root: Path, *, scenario_ids: tuple[str, ...]) -> None:
    repo_root.mkdir(parents=True, exist_ok=False)
    _copy_scenarios(repo_root, scenario_ids)
    _copy_canonical_empty_template(repo_root)
    _initialize_runtime_and_seeded_brains(repo_root)


def _copy_scenarios(repo_root: Path, scenario_ids: tuple[str, ...]) -> None:
    source_root = REPO_ROOT / "benchmarks" / "scenarios"
    target_root = repo_root / "benchmarks" / "scenarios"
    target_root.mkdir(parents=True, exist_ok=True)

    for scenario_id in scenario_ids:
        shutil.copy2(source_root / f"{scenario_id}.json", target_root / f"{scenario_id}.json")
        shutil.copy2(source_root / f"{scenario_id}.md", target_root / f"{scenario_id}.md")


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


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _test_repo_root() -> Path:
    temp_root = Path(__file__).resolve().parent / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root / f"repo_{uuid4().hex}"


if __name__ == "__main__":
    unittest.main()
