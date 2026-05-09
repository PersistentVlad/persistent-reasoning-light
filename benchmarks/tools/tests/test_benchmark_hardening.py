# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import copy
import importlib
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
from benchmark_adapters.common import benchmark_prompt_utils
from benchmark_adapters.common.benchmark_paths import (
    CANONICAL_RESULT_ARTIFACT_SUFFIXES,
    BenchmarkPaths,
    EVENTS_JSONL_SUFFIX,
    RESULT_JSON_SUFFIX,
    TRACE_LOG_SUFFIX,
    resolve_repo_root,
    result_events_path,
    result_json_path,
    result_log_path,
    scenario_metadata_path,
)
from benchmark_adapters.common.event_log_utils import BenchmarkEventLogger, read_events
from benchmark_adapters.common.scenario_utils import (
    build_resolved_execution_artifact_payload,
    build_sectioned_reference_composition_validation_result,
    list_available_scenarios,
    load_benchmark_scenario,
    load_scenario_config_with_metadata,
    resolve_sectioned_reference_scenario,
    validate_scenario_metadata,
    validate_sectioned_reference_composition,
)
from benchmark_adapters.gemini import adapter as gemini_adapter_module
from benchmark_adapters.openai_codex import adapter as openai_codex_adapter_module
from benchmark_adapters.common.result_utils import (
    REQUIRED_NUMERIC_RESULT_METRIC_NAMES,
    load_result_json,
    save_result_json,
)
from benchmark_execution import gemini_executor as gemini_executor_module
from benchmark_adapters.openai_codex.adapter import (
    get_benchmark_agent_metadata,
    resolve_openai_model,
    run_scenario,
)
from google.genai import errors as gemini_errors
from benchmarks.tools.compare_results import build_comparison, validate_comparison_schema
from benchmarks.tools.compute_metrics_from_events import (
    compute_result_from_events,
    derive_result_artifact,
)
from benchmarks.tools.generate_summary_report import (
    build_run_comparison_summary,
    build_run_summary_report,
    build_summary_report,
)
from benchmarks.tools.generate_artifact_generation_calibration_report import (
    build_artifact_generation_calibration,
    render_artifact_generation_calibration_report,
    write_artifact_generation_calibration_report,
)
from benchmarks.tools.generate_quickchart_radar_svg import (
    load_radar_definition,
    validate_radar_definition,
)
from benchmarks.tools.normalize_metrics import validate_metric_definition_coverage
from benchmarks.tools.preflight_check import (
    COMMON_REQUIRED_IMPORTS,
    REQUIRED_RADAR_CONFIG_FILES,
)
from benchmarks import run_benchmarks as run_benchmarks_module
from benchmarks.tools.reset_runtime_brain_and_temp_results import (
    clean_temporary_benchmark_results,
    prepare_clean_benchmark_runtime,
)
from benchmarks.tools.post_run_artifact_harvest import (
    HARVEST_REPORT_FILENAME,
    build_post_run_artifact_harvest_report,
    run_post_run_artifact_harvest,
)
from benchmarks.tools.generate_retention_layer import (
    RETENTION_LAYER_SUFFIX,
    RETENTION_SUMMARY_SUFFIX,
    build_sectioned_composite_retention_layer,
    build_structural_retention_layer,
    generate_retention_artifacts_for_run,
    generate_retention_artifacts_for_scenario,
    resolve_scenario_interpretation_contract,
)


SCENARIO_ID = "sc_0_interrupt_compress_continue"
STRUCTURAL_RETENTION_SCENARIO_ID = "sc_8_structural_retention"
CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID = "sc_01_structural_retention"
MATH_STATE_LOSS_SCENARIO_ID = "sc_03_math_state_loss"
ADAPTER_NAME = "openai_codex"
CANONICAL_DIAGNOSTIC_SCENARIO_SUBSET = (
    "sc_00_stateless_direct_transform",
    CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
    "sc_02_n_back_anomaly_trap",
    "sc_03_math_state_loss",
    "sc_04_chain_collapse",
    "sc_05_digit_span_n_back_hybrid",
    "sc_06_plan_reset",
    "sc_07_trail_making",
    "sc_08_move_clock_hands",
)
EXPECTED_PROFILE_SCENARIO_SUBSETS = {
    "gemini_flash_lite_latest": (
        "sc_00_stateless_direct_transform",
        "sc_11_temporal_rule_propagation",
        "sc_09_zero_crossing_event_trap",
        "sc_08_move_clock_hands",
    ),
    "gemini_flash_latest": CANONICAL_DIAGNOSTIC_SCENARIO_SUBSET,
    "gemini_gemma_3_27b": CANONICAL_DIAGNOSTIC_SCENARIO_SUBSET,
}
TRAJECTORY_READY_SCENARIO_IDS = ("sc_01_structural_retention",)
ACTIVE_SCENARIO_INTERPRETATION_EXPECTATIONS = {
    "sc_00_stateless_direct_transform": {
        "interpretation_variant": "none",
        "layer_support": {
            "retention": "unsupported",
            "correctness": "unsupported",
            "ghost": "unsupported",
        },
    },
    CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID: {
        "interpretation_variant": "structural_retention_with_ghost",
        "layer_support": {
            "retention": "enabled",
            "correctness": "deferred",
            "ghost": "enabled",
        },
    },
    "sc_02_n_back_anomaly_trap": {
        "interpretation_variant": "sequence_retention_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "unsupported",
            "ghost": "deferred",
        },
    },
    "sc_03_math_state_loss": {
        "interpretation_variant": "math_retention_with_correctness",
        "layer_support": {
            "retention": "enabled",
            "correctness": "enabled",
            "ghost": "unsupported",
        },
    },
    "sc_04_chain_collapse": {
        "interpretation_variant": "structural_retention_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "unsupported",
            "ghost": "deferred",
        },
    },
    "sc_05_digit_span_n_back_hybrid": {
        "interpretation_variant": "sequence_retention_with_correctness_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "deferred",
            "ghost": "deferred",
        },
    },
    "sc_06_plan_reset": {
        "interpretation_variant": "structural_retention_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "unsupported",
            "ghost": "deferred",
        },
    },
    "sc_07_trail_making": {
        "interpretation_variant": "ordered_trail_retention_with_correctness_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "deferred",
            "ghost": "deferred",
        },
    },
    "sc_08_move_clock_hands": {
        "interpretation_variant": "structural_retention_with_correctness_deferred",
        "layer_support": {
            "retention": "deferred",
            "correctness": "deferred",
            "ghost": "deferred",
        },
    },
}
SC9_COMPOSITION_SOURCE_SCENARIO_IDS = (
    CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
    "sc_03_math_state_loss",
    "sc_02_n_back_anomaly_trap",
    "sc_07_trail_making",
    "sc_08_move_clock_hands",
)
STRUCTURAL_CANONICAL_UNITS = (
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
    "D1", "D2", "D3", "D4", "D5", "D6",
    "C1", "C2", "C3", "C4",
)
MATH_STATE_LOSS_CANONICAL_SLOTS = (
    "PRODUCT_1",
    "PRODUCT_2",
    "COMBINED_SUM",
    "AFTER_SUBTRACTION",
    "AFTER_DIVISION",
    "AFTER_ADDITION",
    "AFTER_MULTIPLICATION",
    "AFTER_REDUCTION",
    "FINAL_NUMERATOR",
    "FINAL_RESULT",
)


class BenchmarkHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paths = BenchmarkPaths(repo_root=REPO_ROOT)

    def _load_scenario_config(self, scenario_id: str) -> dict[str, object]:
        _, _, merged = load_scenario_config_with_metadata(self.paths, scenario_id)
        return merged

    def _load_scenario_metadata(self, scenario_id: str) -> dict[str, object]:
        return json.loads(
            (
                REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.metadata.json"
            ).read_text(encoding="utf-8")
        )

    def _build_profile_lifecycle_repo(self, repo_root: Path) -> None:
        empty_context = {
            "active_task": None,
            "constraints": [],
            "decisions": [],
            "open_issues": [],
        }
        (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
        for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
            (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

        empty_root = repo_root / "reasoning_brain_storage" / "templates" / "empty"
        runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
        seeded_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "seeded"

        for brain_root in (empty_root, runtime_root, seeded_root):
            _create_minimal_brain_root(brain_root, empty_context)

    def _load_existing_results(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        baseline_result = load_result_json(
            result_json_path(self.paths, BASELINE, SCENARIO_ID)
        )
        pr_ephemeral_result = load_result_json(
            result_json_path(self.paths, PR_EPHEMERAL, SCENARIO_ID)
        )
        pr_light_brain_result = load_result_json(
            result_json_path(self.paths, PR_LIGHT_BRAIN, SCENARIO_ID)
        )
        return baseline_result, pr_ephemeral_result, pr_light_brain_result

    def test_all_repo_scenarios_load_with_explicit_execution_contract_fields(self) -> None:
        required_contract_fields = (
            "supports_retention",
            "supports_correctness",
            "supports_ghost",
            "supports_temporal_ghost",
            "return_to_origin",
            "scenario_mode",
            "trajectory_readiness",
        )
        ready_scenario_ids: list[str] = []
        for scenario_id in list_available_scenarios(self.paths):
            scenario = load_benchmark_scenario(self.paths, scenario_id)
            config = scenario.config
            for field_name in required_contract_fields:
                self.assertIn(field_name, config, f"{scenario_id} missing {field_name}")
            self.assertIn(config["scenario_mode"], {"standard", "sectioned", "showcase"})
            self.assertIsInstance(config["supports_retention"], bool)
            self.assertIsInstance(config["supports_correctness"], bool)
            self.assertIsInstance(config["supports_ghost"], bool)
            self.assertIsInstance(config["supports_temporal_ghost"], bool)
            self.assertIsInstance(config["return_to_origin"], bool)
            self.assertIn(
                config["trajectory_readiness"],
                {"ready", "deferred", "unsupported"},
            )
            if config["trajectory_readiness"] == "ready":
                ready_scenario_ids.append(scenario_id)
        self.assertEqual(tuple(sorted(ready_scenario_ids)), TRAJECTORY_READY_SCENARIO_IDS)

    def test_all_repo_scenarios_have_companion_metadata_schema(self) -> None:
        for scenario_id in list_available_scenarios(self.paths):
            with self.subTest(scenario_id=scenario_id):
                metadata_path = scenario_metadata_path(self.paths, scenario_id)
                self.assertTrue(metadata_path.is_file())
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if scenario_id == "sc_99_killer_all_scenarios":
                    self.assertEqual(metadata["contract_version"], "1.6")
                else:
                    self.assertEqual(metadata["contract_version"], "1.4")
                self.assertEqual(metadata["identity"]["scenario_id"], scenario_id)
                expected_migration_fields = {
                    "execution_contract",
                    "interpretation_support",
                    "interpretation_contract",
                    "retention_contract",
                    "ghost_contract",
                    "correctness_contract",
                }
                if scenario_id == "sc_99_killer_all_scenarios":
                    expected_migration_fields.add("section_correctness_contract")
                    expected_migration_fields.add("section_ghost_contract")
                self.assertEqual(
                    set(metadata["migration_lock"].keys()),
                    expected_migration_fields,
                )
                self.assertIn("ghost_contract", metadata)
                self.assertIn("trajectory_contract", metadata)
                self.assertIsNone(metadata["trajectory_contract"])
                self.assertIn("expected_ready", metadata)
                self.assertIn("expected_file", metadata)
                self.assertIsInstance(metadata["expected_ready"], bool)
                if metadata["expected_ready"]:
                    self.assertIsInstance(metadata["expected_file"], str)
                    self.assertTrue(metadata["expected_file"].endswith(".expected.json"))
                else:
                    self.assertIsNone(metadata["expected_file"])
                self.assertEqual(
                    set(metadata["execution_contract"].keys()),
                    {"scenario_mode", "showcase", "status", "return_to_origin"},
                )
                self.assertEqual(
                    set(metadata["interpretation_support"].keys()),
                    {
                        "supports_retention",
                        "supports_correctness",
                        "supports_ghost",
                        "supports_temporal_ghost",
                        "trajectory_readiness",
                    },
                )
                scenario_mode = metadata["execution_contract"]["scenario_mode"]
                supports_ghost = metadata["interpretation_support"]["supports_ghost"]
                if scenario_mode == "sectioned":
                    self.assertIsNone(metadata["ghost_contract"])
                    self.assertFalse(metadata["migration_lock"]["ghost_contract"])
                    if scenario_id == "sc_99_killer_all_scenarios":
                        self.assertTrue(metadata["migration_lock"]["section_correctness_contract"])
                        self.assertTrue(metadata["migration_lock"]["section_ghost_contract"])
                        self.assertEqual(
                            metadata["section_correctness_contracts"][0]["section_id"],
                            "section_2_math_state_loss",
                        )
                        self.assertEqual(
                            metadata["section_ghost_contracts"][0]["section_id"],
                            "section_1_structural_retention",
                        )
                elif supports_ghost:
                    self.assertIsInstance(metadata["ghost_contract"], dict)
                    self.assertTrue(metadata["migration_lock"]["ghost_contract"])
                else:
                    self.assertIsNone(metadata["ghost_contract"])
                    self.assertTrue(metadata["migration_lock"]["ghost_contract"])
                self.assertTrue(
                    {
                        "interpretation_variant",
                        "layer_support",
                    }.issubset(set(metadata["interpretation_contract"].keys()))
                )
                self.assertEqual(
                    set(metadata["interpretation_contract"]["layer_support"].keys()),
                    {"retention", "correctness", "ghost"},
                )
                if scenario_id == "sc_99_killer_all_scenarios":
                    self.assertIsInstance(
                        metadata["interpretation_contract"].get("sections"),
                        list,
                    )
                    self.assertEqual(
                        len(metadata["interpretation_contract"]["sections"]),
                        5,
                    )
                self.assertIn("retention_contract", metadata)
                if metadata["interpretation_support"]["supports_retention"]:
                    self.assertIsInstance(metadata["retention_contract"], dict)
                    self.assertTrue(
                        {
                            "retention_type",
                            "checkpoints",
                            "final_sections",
                            "required_exact_section_headings",
                        }.issubset(set(metadata["retention_contract"].keys()))
                    )
                    checkpoint_ids = [
                        checkpoint["checkpoint_id"]
                        for checkpoint in metadata["retention_contract"]["checkpoints"]
                    ]
                    self.assertEqual(len(checkpoint_ids), len(set(checkpoint_ids)))
                    for checkpoint_id in checkpoint_ids:
                        self.assertTrue(
                            checkpoint_id.startswith("checkpoint_"),
                            f"{scenario_id} has unnormalized checkpoint_id {checkpoint_id}",
                        )
                else:
                    self.assertIsNone(metadata["retention_contract"])
                self.assertIn("correctness_contract", metadata)

    def test_trajectory_contract_disabled_forms_load_cleanly(self) -> None:
        repo_root = _workspace_temp_dir("trajectory_contract_disabled_forms")
        try:
            _build_structural_retention_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            metadata_path = scenario_metadata_path(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIsNone(metadata["trajectory_contract"])

            metadata["trajectory_contract"] = {"enabled": False}
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)

            self.assertNotIn("trajectory_contract", loaded.config)
            self.assertEqual(loaded.config["trajectory_readiness"], "ready")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_malformed_enabled_trajectory_contract_fails_metadata_validation(self) -> None:
        metadata = self._load_scenario_metadata(CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
        metadata["trajectory_contract"] = {
            "enabled": True,
            "mode": "checkpoint_expected_values",
            "checkpoint_expected_values": [
                {
                    "checkpoint_id": "checkpoint_00_initial",
                    "expected_slot_values": {
                        "FIELD_NAME": 42,
                    },
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "values must be strings"):
            validate_scenario_metadata(metadata, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)

    def test_valid_enabled_trajectory_contract_is_schema_only(self) -> None:
        repo_root = _workspace_temp_dir("trajectory_contract_valid_schema_only")
        try:
            _build_structural_retention_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            metadata_path = scenario_metadata_path(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["trajectory_contract"] = {
                "enabled": True,
                "mode": "checkpoint_expected_values",
                "checkpoint_expected_values": [
                    {
                        "checkpoint_id": "checkpoint_00_initial",
                        "expected_slot_values": {
                            "FIELD_NAME": "value",
                        },
                    }
                ],
            }
            validate_scenario_metadata(metadata, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)

            self.assertNotIn("trajectory_contract", loaded.config)
            self.assertEqual(loaded.config["trajectory_readiness"], "ready")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_loader_fails_on_scenario_metadata_identity_mismatch(self) -> None:
        repo_root = _workspace_temp_dir("scenario_metadata_identity_mismatch")
        try:
            _build_structural_retention_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            metadata_path = scenario_metadata_path(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["identity"]["scenario_id"] = "sc_wrong_identity"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "scenario_id mismatch"):
                load_benchmark_scenario(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_task_scenario_jsons_do_not_keep_migrated_interpretation_contract_fields(self) -> None:
        for scenario_id in list_available_scenarios(self.paths):
            with self.subTest(scenario_id=scenario_id):
                scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
                self.assertNotIn("interpretation_spec", scenario)
                composition_spec = scenario.get("composition_spec")
                if isinstance(composition_spec, dict):
                    for section in composition_spec.get("sections", []):
                        self.assertNotIn("interpretation_variant", section)
                        self.assertNotIn("layer_support", section)
                        self.assertNotIn("reason", section)
                retention_spec = scenario.get("retention_spec")
                if isinstance(retention_spec, dict):
                    for section in retention_spec.get("sections", []):
                        self.assertNotIn("interpretation_variant", section)
                        self.assertNotIn("layer_support", section)
                        self.assertNotIn("reason", section)

    def test_task_scenario_jsons_do_not_keep_migrated_retention_contract_fields(self) -> None:
        for scenario_id in list_available_scenarios(self.paths):
            with self.subTest(scenario_id=scenario_id):
                scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
                retention_spec = scenario.get("retention_spec")
                if not isinstance(retention_spec, dict):
                    continue
                for field_name in (
                    "retention_type",
                    "unit_groups",
                    "checkpoints",
                    "final_sections",
                    "required_exact_section_headings",
                ):
                    self.assertNotIn(field_name, retention_spec)
                for section in retention_spec.get("sections", []):
                    self.assertNotIn("retention_type", section)
                    self.assertNotIn("unit_groups", section)

    def test_task_scenario_jsons_do_not_keep_migrated_top_level_correctness_contract_fields(self) -> None:
        for scenario_id in list_available_scenarios(self.paths):
            with self.subTest(scenario_id=scenario_id):
                scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                metadata_path = scenario_metadata_path(self.paths, scenario_id)
                scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                retention_spec = scenario.get("retention_spec")
                if not isinstance(retention_spec, dict):
                    continue
                if (
                    metadata["execution_contract"]["scenario_mode"] == "standard"
                    and isinstance(metadata.get("correctness_contract"), dict)
                ):
                    self.assertNotIn("correctness_spec", retention_spec)

    def test_task_scenario_jsons_do_not_keep_migrated_top_level_ghost_contract_fields(self) -> None:
        for scenario_id in list_available_scenarios(self.paths):
            with self.subTest(scenario_id=scenario_id):
                scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                metadata_path = scenario_metadata_path(self.paths, scenario_id)
                scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                retention_spec = scenario.get("retention_spec")
                if not isinstance(retention_spec, dict):
                    continue
                if (
                    metadata["execution_contract"]["scenario_mode"] == "standard"
                    and metadata["migration_lock"]["ghost_contract"]
                    and metadata["interpretation_support"]["supports_ghost"]
                ):
                    self.assertNotIn("ghost_spec", retention_spec)

    def test_loader_uses_metadata_as_authoritative_source_for_migrated_fields(self) -> None:
        repo_root = _workspace_temp_dir("scenario_metadata_authoritative")
        try:
            _build_structural_retention_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_path = repo_root / "benchmarks" / "scenarios" / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.json"
            metadata_path = scenario_metadata_path(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)

            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            scenario["scenario_mode"] = "showcase"
            scenario["supports_retention"] = False
            scenario["return_to_origin"] = True
            scenario["trajectory_readiness"] = "unsupported"
            scenario["interpretation_spec"] = {
                "interpretation_variant": "none",
                "layer_support": {
                    "retention": "unsupported",
                    "correctness": "unsupported",
                    "ghost": "unsupported",
                },
            }
            scenario["retention_spec"]["retention_type"] = "structural_retention_deferred"
            scenario["retention_spec"]["checkpoints"] = []
            scenario["retention_spec"]["final_sections"] = {
                "retained": "WRONG RETAINED",
                "lost": "WRONG LOST",
            }
            scenario["retention_spec"]["required_exact_section_headings"] = ["WRONG"]
            scenario["retention_spec"]["ghost_spec"] = {
                "token_pattern": "WRONG",
                "valid_transformations": {"WRONG": ["WRONG"]},
            }
            scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["execution_contract"]["scenario_mode"] = "standard"
            metadata["execution_contract"]["showcase"] = False
            metadata["execution_contract"]["return_to_origin"] = False
            metadata["interpretation_support"]["supports_retention"] = True
            metadata["interpretation_support"]["trajectory_readiness"] = "ready"
            metadata["interpretation_contract"]["interpretation_variant"] = (
                "structural_retention_with_ghost"
            )
            metadata["interpretation_contract"]["layer_support"] = {
                "retention": "enabled",
                "correctness": "deferred",
                "ghost": "enabled",
            }
            metadata["retention_contract"]["retention_type"] = "structural_retention"
            metadata["retention_contract"]["checkpoints"] = [
                {
                    "checkpoint_id": "checkpoint_00_initial",
                    "checkpoint_label": "Initial",
                    "section_heading": "CHECKPOINT 0 - INITIAL",
                }
            ]
            metadata["retention_contract"]["final_sections"] = {
                "retained": "FINAL RETAINED UNITS",
                "lost": "FINAL LOST UNITS",
            }
            metadata["retention_contract"]["required_exact_section_headings"] = [
                "CHECKPOINT 0 - INITIAL",
                "FINAL RETAINED UNITS",
                "FINAL LOST UNITS",
            ]
            metadata["ghost_contract"] = {
                "token_pattern": "[A-Z][0-9]+",
                "valid_transformations": {},
            }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
            self.assertEqual(loaded.config["scenario_mode"], "standard")
            self.assertFalse(loaded.config["showcase"])
            self.assertFalse(loaded.config["return_to_origin"])
            self.assertTrue(loaded.config["supports_retention"])
            self.assertEqual(loaded.config["trajectory_readiness"], "ready")
            self.assertEqual(
                loaded.config["interpretation_spec"]["interpretation_variant"],
                "structural_retention_with_ghost",
            )
            self.assertEqual(
                loaded.config["interpretation_spec"]["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "deferred",
                    "ghost": "enabled",
                },
            )
            self.assertEqual(
                loaded.config["retention_spec"]["retention_type"],
                "structural_retention",
            )
            self.assertEqual(
                loaded.config["retention_spec"]["final_sections"],
                {
                    "retained": "FINAL RETAINED UNITS",
                    "lost": "FINAL LOST UNITS",
                },
            )
            self.assertEqual(
                loaded.config["retention_spec"]["required_exact_section_headings"],
                [
                    "CHECKPOINT 0 - INITIAL",
                    "FINAL RETAINED UNITS",
                    "FINAL LOST UNITS",
                ],
            )
            self.assertEqual(
                loaded.config["retention_spec"]["ghost_spec"],
                {
                    "token_pattern": "[A-Z][0-9]+",
                    "valid_transformations": {},
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_loader_uses_metadata_as_authoritative_source_for_top_level_correctness_contract(self) -> None:
        repo_root = _workspace_temp_dir("scenario_correctness_metadata_authoritative")
        try:
            _build_math_state_loss_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_id = MATH_STATE_LOSS_SCENARIO_ID
            scenario_path = repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.json"
            metadata_path = scenario_metadata_path(paths, scenario_id)

            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            scenario["retention_spec"]["correctness_spec"] = {
                "slot_section_heading": "WRONG",
                "value_match_policy": "exact_string",
                "expected_slot_values": {"FINAL_RESULT": "WRONG"},
            }
            scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["correctness_contract"] = {
                "slot_section_heading": "CHECKPOINT 20 - FINAL STATE",
                "value_match_policy": "exact_string",
                "expected_slot_values": {
                    "PRODUCT_1": "1081",
                    "PRODUCT_2": "1102",
                    "COMBINED_SUM": "2183",
                    "AFTER_SUBTRACTION": "1818",
                    "AFTER_DIVISION": "606",
                    "AFTER_ADDITION": "657",
                    "AFTER_MULTIPLICATION": "1314",
                    "AFTER_REDUCTION": "438",
                    "FINAL_NUMERATOR": "437",
                    "FINAL_RESULT": "437/7",
                },
            }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, scenario_id)
            self.assertEqual(
                loaded.config["correctness_spec"],
                metadata["correctness_contract"],
            )
            self.assertEqual(
                loaded.config["retention_spec"]["correctness_spec"],
                metadata["correctness_contract"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_expected_ready_false_preserves_metadata_correctness_values(self) -> None:
        metadata = self._load_scenario_metadata(MATH_STATE_LOSS_SCENARIO_ID)
        loaded = load_benchmark_scenario(self.paths, MATH_STATE_LOSS_SCENARIO_ID)

        self.assertFalse(metadata["expected_ready"])
        self.assertIsNone(metadata["expected_file"])
        self.assertEqual(loaded.config["correctness_spec"], metadata["correctness_contract"])
        self.assertNotIn("expected", loaded.config)

    def test_expected_ready_true_loads_expected_file_and_resolves_expected_ref(self) -> None:
        metadata = self._load_scenario_metadata("sc_08_move_clock_hands")
        loaded = load_benchmark_scenario(self.paths, "sc_08_move_clock_hands")
        expected_path = REPO_ROOT / "benchmarks" / "scenarios" / metadata["expected_file"]
        expected_payload = json.loads(expected_path.read_text(encoding="utf-8"))

        self.assertTrue(metadata["expected_ready"])
        self.assertEqual(metadata["expected_file"], "sc_08_move_clock_hands.expected.json")
        self.assertEqual(
            metadata["correctness_contract"]["expected_ref"],
            "final.expected_slot_values",
        )
        self.assertNotIn("expected_slot_values", metadata["correctness_contract"])
        self.assertEqual(loaded.config["expected"], expected_payload)
        self.assertEqual(
            loaded.config["correctness_spec"]["expected_slot_values"],
            expected_payload["final"]["expected_slot_values"],
        )
        self.assertEqual(
            loaded.config["retention_spec"]["correctness_spec"],
            loaded.config["correctness_spec"],
        )

    def test_expected_ready_missing_expected_file_hard_fails(self) -> None:
        repo_root = _workspace_temp_dir("expected_missing_file")
        try:
            _copy_repo_scenario_bundle(repo_root, "sc_08_move_clock_hands")
            paths = BenchmarkPaths(repo_root=repo_root)
            expected_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / "sc_08_move_clock_hands.expected.json"
            )
            expected_path.unlink()

            with self.assertRaises(FileNotFoundError):
                load_benchmark_scenario(paths, "sc_08_move_clock_hands")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_expected_file_scenario_id_mismatch_fails(self) -> None:
        repo_root = _workspace_temp_dir("expected_id_mismatch")
        try:
            _copy_repo_scenario_bundle(repo_root, "sc_08_move_clock_hands")
            paths = BenchmarkPaths(repo_root=repo_root)
            expected_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / "sc_08_move_clock_hands.expected.json"
            )
            payload = json.loads(expected_path.read_text(encoding="utf-8"))
            payload["scenario_id"] = "sc_wrong"
            expected_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "scenario_id mismatch"):
                load_benchmark_scenario(paths, "sc_08_move_clock_hands")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_expected_file_checkpoint_id_mismatch_fails(self) -> None:
        repo_root = _workspace_temp_dir("expected_checkpoint_mismatch")
        try:
            _copy_repo_scenario_bundle(repo_root, "sc_08_move_clock_hands")
            paths = BenchmarkPaths(repo_root=repo_root)
            expected_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / "sc_08_move_clock_hands.expected.json"
            )
            payload = json.loads(expected_path.read_text(encoding="utf-8"))
            payload["checkpoints"] = [
                {
                    "checkpoint_id": "checkpoint_missing",
                    "expected_state": {"TIME": "12:00"},
                }
            ]
            expected_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not match retention checkpoints"):
                load_benchmark_scenario(paths, "sc_08_move_clock_hands")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_expected_json_is_sole_source_for_migrated_scenario_values(self) -> None:
        metadata = self._load_scenario_metadata("sc_08_move_clock_hands")
        expected_path = REPO_ROOT / "benchmarks" / "scenarios" / metadata["expected_file"]
        expected_payload = json.loads(expected_path.read_text(encoding="utf-8"))

        self.assertNotIn("expected_slot_values", metadata["correctness_contract"])
        self.assertIn("expected_ref", metadata["correctness_contract"])
        self.assertEqual(
            expected_payload["final"]["expected_slot_values"],
            {
                "TIME": "12:00",
                "HOUR_HAND": "12",
                "MINUTE_HAND": "00",
                "MINUTES_TO_POS_A": "0",
            },
        )

    def test_required_imports_resolve(self) -> None:
        required_imports = (
            "benchmark_adapters.openai_codex.adapter",
            "reasoning_adapters.codex.adapter",
            *COMMON_REQUIRED_IMPORTS,
        )
        for module_name in required_imports:
            with self.subTest(module_name=module_name):
                importlib.import_module(module_name)

    def test_resolve_repo_root_uses_current_package_layout(self) -> None:
        resolved = resolve_repo_root(REPO_ROOT / "benchmarks")
        self.assertEqual(resolved, REPO_ROOT)

    def test_artifact_suffix_contract_is_canonical(self) -> None:
        self.assertEqual(
            set(CANONICAL_RESULT_ARTIFACT_SUFFIXES),
            {TRACE_LOG_SUFFIX, EVENTS_JSONL_SUFFIX, RESULT_JSON_SUFFIX},
        )
        self.assertEqual(
            result_log_path(self.paths, BASELINE, SCENARIO_ID).name,
            f"{SCENARIO_ID}{TRACE_LOG_SUFFIX}",
        )
        self.assertEqual(
            result_events_path(self.paths, PR_EPHEMERAL, SCENARIO_ID).name,
            f"{SCENARIO_ID}{EVENTS_JSONL_SUFFIX}",
        )
        self.assertEqual(
            result_json_path(self.paths, PR_LIGHT_BRAIN, SCENARIO_ID).name,
            f"{SCENARIO_ID}{RESULT_JSON_SUFFIX}",
        )

    def test_benchmark_brain_working_context_shape_is_valid(self) -> None:
        required_keys = {
            "active_task",
            "constraints",
            "decisions",
            "open_issues",
        }
        optional_multi_type_keys = {"tasks", "procedures"}
        for brain_root in (
            self.paths.empty_brain_root,
            self.paths.runtime_brain_root,
            self.paths.seeded_brain_root,
        ):
            with self.subTest(brain_root=brain_root.name):
                working_context_path = brain_root / "views" / "working_context.json"
                self.assertTrue(working_context_path.is_file())
                working_context = json.loads(working_context_path.read_text(encoding="utf-8"))
                self.assertTrue(required_keys.issubset(set(working_context.keys())))
                self.assertTrue(
                    set(working_context.keys()).issubset(
                        required_keys | optional_multi_type_keys
                    )
                )
                self.assertIsNone(working_context["active_task"])
                self.assertIsInstance(working_context["constraints"], list)
                self.assertIsInstance(working_context["decisions"], list)
                self.assertIsInstance(working_context["open_issues"], list)
                if "tasks" in working_context:
                    self.assertIsInstance(working_context["tasks"], list)
                if "procedures" in working_context:
                    self.assertIsInstance(working_context["procedures"], list)
                if brain_root.name in {"empty", "seeded"}:
                    self.assertEqual(working_context["constraints"], [])
                    self.assertEqual(working_context["decisions"], [])
                    self.assertEqual(working_context["open_issues"], [])
                    self.assertEqual(working_context.get("tasks", []), [])
                    self.assertEqual(working_context.get("procedures", []), [])

    def test_comparison_schema_is_valid_for_existing_results(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            compute_result_from_events(
                _build_emission_only_events(PR_EPHEMERAL),
                adapter_name=ADAPTER_NAME,
            ),
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )
        validated = validate_comparison_schema(comparison)
        self.assertEqual(
            set(validated.keys()),
            {"comparison_metadata", "summary_scores", "metrics_comparison"},
        )
        self.assertGreater(len(validated["metrics_comparison"]), 0)

    def test_metric_definition_coverage_matches_required_numeric_metrics(self) -> None:
        validate_metric_definition_coverage(
            list(REQUIRED_NUMERIC_RESULT_METRIC_NAMES)
        )

    def test_radar_config_coverage_validates_for_all_required_radars(self) -> None:
        radar_dir = REPO_ROOT / "benchmarks" / "tools" / "radar_charts"
        for filename in REQUIRED_RADAR_CONFIG_FILES:
            with self.subTest(radar=filename):
                radar_name = filename.removeprefix("radar_").removesuffix(".json")
                radar_definition = load_radar_definition(radar_name, radar_charts_dir=radar_dir)
                validated = validate_radar_definition(radar_definition)
                self.assertEqual(validated["radar_name"], radar_name)

    def test_result_derivation_is_reproducible(self) -> None:
        events = _build_baseline_events()

        first = compute_result_from_events(events, adapter_name=ADAPTER_NAME)
        second = compute_result_from_events(events, adapter_name=ADAPTER_NAME)

        self.assertEqual(first, second)

    def test_result_derivation_splits_emission_and_persistence_signals(self) -> None:
        emission_only = compute_result_from_events(
            _build_emission_only_events(PR_EPHEMERAL),
            adapter_name=ADAPTER_NAME,
        )
        reuse_focused = compute_result_from_events(
            _build_reuse_focused_events(PR_LIGHT_BRAIN),
            adapter_name=ADAPTER_NAME,
        )

        self.assertEqual(
            emission_only["persistence_integrity"]["artifact_suggested_count"],
            1,
        )
        self.assertEqual(
            emission_only["persistence_integrity"]["controlled_mutations_ratio"],
            1.0,
        )
        self.assertEqual(
            emission_only["knowledge_persistence"]["context_utilization_rate"],
            0.0,
        )
        self.assertEqual(
            emission_only["knowledge_persistence"]["reuse_rate"],
            0.0,
        )
        self.assertEqual(
            emission_only["retrieval_metrics"]["retrieval_precision"],
            0.0,
        )

        self.assertEqual(
            reuse_focused["persistence_integrity"]["artifact_suggested_count"],
            0,
        )
        self.assertEqual(
            reuse_focused["persistence_integrity"]["controlled_mutations_ratio"],
            0.0,
        )
        self.assertEqual(
            reuse_focused["knowledge_persistence"]["context_utilization_rate"],
            1.0,
        )
        self.assertEqual(
            reuse_focused["knowledge_persistence"]["reuse_rate"],
            1.0,
        )
        self.assertEqual(
            reuse_focused["retrieval_metrics"]["retrieval_precision"],
            1.0,
        )

    def test_comparison_summary_prioritizes_persistence_over_emission(self) -> None:
        baseline_result = compute_result_from_events(
            _build_baseline_events(),
            adapter_name=ADAPTER_NAME,
        )
        pr_ephemeral_result = compute_result_from_events(
            _build_emission_only_events(PR_EPHEMERAL),
            adapter_name=ADAPTER_NAME,
        )
        pr_light_brain_result = compute_result_from_events(
            _build_reuse_focused_events(PR_LIGHT_BRAIN),
            adapter_name=ADAPTER_NAME,
        )

        comparison = build_comparison(
            baseline_result,
            pr_ephemeral_result,
            pr_light_brain_result,
            adapter_name=ADAPTER_NAME,
        )
        summary_scores = comparison["summary_scores"]

        self.assertGreater(
            summary_scores["pr_ephemeral_pr_stability_score"],
            summary_scores["baseline_pr_stability_score"],
        )
        self.assertGreater(
            summary_scores["pr_light_brain_pr_stability_score"],
            summary_scores["pr_ephemeral_pr_stability_score"],
        )

    def test_summary_report_surfaces_persistence_metrics(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            compute_result_from_events(
                _build_emission_only_events(PR_EPHEMERAL),
                adapter_name=ADAPTER_NAME,
            ),
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )

        report = build_summary_report(comparison, chart_paths=[])

        self.assertIn("### retrieval_precision", report)
        self.assertIn("### context_utilization_rate", report)
        self.assertIn("### reuse_rate", report)

    def test_artifact_generation_calibration_counts_outcomes_and_rates(self) -> None:
        events = [
            _artifact_calibration_completed_event("valid"),
            _artifact_calibration_completed_event("none"),
            _artifact_calibration_completed_event("missing"),
            _artifact_calibration_completed_event("malformed"),
        ]

        calibration = build_artifact_generation_calibration(events)
        generation = calibration["artifact_generation"]

        self.assertEqual(calibration["total_tasks"], 4)
        self.assertEqual(generation["valid_artifact_count"], 1)
        self.assertEqual(generation["none_count"], 1)
        self.assertEqual(generation["missing_count"], 1)
        self.assertEqual(generation["malformed_count"], 1)
        self.assertEqual(generation["artifact_rate"], 0.25)
        self.assertEqual(generation["none_rate"], 0.25)
        self.assertEqual(generation["malformed_rate"], 0.25)

    def test_artifact_generation_calibration_computes_filter_alignment_and_reasons(self) -> None:
        events = [
            _artifact_calibration_completed_event(
                "valid",
                filter_payload=_artifact_filter_payload("accepted", reasons=[]),
            ),
            _artifact_calibration_completed_event(
                "valid",
                filter_payload=_artifact_filter_payload(
                    "rejected",
                    reasons=["artifact looks like an intermediate reasoning trace"],
                ),
            ),
            _artifact_calibration_completed_event(
                "valid",
                filter_payload=_artifact_filter_payload(
                    "rejected",
                    reasons=["artifact content needs clarification"],
                ),
            ),
        ]

        calibration = build_artifact_generation_calibration(events)
        filter_alignment = calibration["filter_alignment"]

        self.assertEqual(filter_alignment["evaluated_count"], 3)
        self.assertEqual(filter_alignment["accepted_count"], 1)
        self.assertEqual(filter_alignment["rejected_count"], 2)
        self.assertAlmostEqual(filter_alignment["filter_acceptance_rate"], 1 / 3)
        self.assertAlmostEqual(filter_alignment["generator_precision"], 1 / 3)
        self.assertEqual(
            filter_alignment["rejection_reason_distribution"],
            {
                "artifact looks like an intermediate reasoning trace": 1,
                "artifact content needs clarification": 1,
            },
        )

    def test_artifact_generation_calibration_handles_missing_shadow_and_filter_telemetry(self) -> None:
        events = [_artifact_calibration_completed_event("valid")]

        calibration = build_artifact_generation_calibration(events)
        shadow = calibration["shadow_generation"]
        filter_alignment = calibration["filter_alignment"]
        report = render_artifact_generation_calibration_report(calibration)

        self.assertEqual(shadow["shadow_total_count"], 0)
        self.assertEqual(shadow["shadow_artifact_rate"], 0.0)
        self.assertEqual(shadow["shadow_none_rate"], 0.0)
        self.assertEqual(filter_alignment["evaluated_count"], 0)
        self.assertEqual(filter_alignment["filter_acceptance_rate"], 0.0)
        self.assertIn("## Shadow Generation", report)
        self.assertIn("## Hard-Gate Readiness", report)

    def test_artifact_generation_calibration_report_writes_markdown_without_result_artifacts(self) -> None:
        repo_root = _workspace_temp_dir("artifact_calibration_report")
        try:
            event_path = repo_root / "benchmarks" / "results" / BASELINE / (
                f"{SCENARIO_ID}{EVENTS_JSONL_SUFFIX}"
            )
            logger = BenchmarkEventLogger(
                event_log_path=event_path,
                scenario_id=SCENARIO_ID,
                mode=BASELINE,
                auto_reset=True,
                allow_overwrite=True,
            )
            logger.log_task_started()
            logger.log_task_completed(
                {
                    "success": True,
                    "execution_source": "manual_override",
                    "artifact_generation": _artifact_generation_payload("none"),
                }
            )
            output_path = repo_root / "benchmarks" / "reports" / (
                "artifact_generation_calibration.md"
            )

            written = write_artifact_generation_calibration_report(
                [event_path],
                output_path=output_path,
                overwrite=True,
            )

            self.assertEqual(written, output_path)
            report = output_path.read_text(encoding="utf-8")
            self.assertIn("# Artifact Generation Calibration Report", report)
            self.assertIn("- none_count: 1", report)
            self.assertFalse(
                (
                    repo_root
                    / "benchmarks"
                    / "results"
                    / BASELINE
                    / f"{SCENARIO_ID}{RESULT_JSON_SUFFIX}"
                ).exists()
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_comparison_fails_loudly_when_metric_definition_is_missing(self) -> None:
        baseline_result = compute_result_from_events(
            _build_baseline_events(),
            adapter_name=ADAPTER_NAME,
        )
        pr_ephemeral_result = compute_result_from_events(
            _build_emission_only_events(PR_EPHEMERAL),
            adapter_name=ADAPTER_NAME,
        )
        pr_light_brain_result = compute_result_from_events(
            _build_reuse_focused_events(PR_LIGHT_BRAIN),
            adapter_name=ADAPTER_NAME,
        )
        mutated_results = []
        for result in (baseline_result, pr_ephemeral_result, pr_light_brain_result):
            mutated = copy.deepcopy(result)
            mutated["reasoning_stability"]["novel_phase8_metric"] = 1.0
            mutated_results.append(mutated)

        with self.assertRaisesRegex(ValueError, "missing definitions"):
            build_comparison(*mutated_results)

    def test_radar_definition_fails_loudly_when_metric_is_unknown(self) -> None:
        radar_definition = {
            "radar_name": "phase8_probe",
            "metrics": ["novel_phase8_metric"],
        }
        with self.assertRaisesRegex(ValueError, "missing definitions"):
            validate_radar_definition(radar_definition)

    def test_save_result_requires_explicit_overwrite(self) -> None:
        result = compute_result_from_events(
            _build_baseline_events(),
            adapter_name=ADAPTER_NAME,
        )

        tmpdir = _workspace_temp_dir("save_result")
        try:
            output_path = tmpdir / "probe.result.json"
            save_result_json(output_path, result, overwrite=False)

            with self.assertRaises(FileExistsError):
                save_result_json(output_path, result, overwrite=False)

            save_result_json(output_path, result, overwrite=True)
            self.assertTrue(output_path.is_file())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_event_logger_auto_reset_requires_explicit_overwrite(self) -> None:
        tmpdir = _workspace_temp_dir("event_logger")
        try:
            log_path = tmpdir / "probe.events.jsonl"
            log_path.write_text("existing\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                BenchmarkEventLogger(
                    event_log_path=log_path,
                    scenario_id=SCENARIO_ID,
                    mode=BASELINE,
                    auto_reset=True,
                    allow_overwrite=False,
                )

            logger = BenchmarkEventLogger(
                event_log_path=log_path,
                scenario_id=SCENARIO_ID,
                mode=BASELINE,
                auto_reset=True,
                allow_overwrite=True,
            )
            logger.log_task_started()
            events = read_events(log_path)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "task_started")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_prepare_clean_benchmark_runtime_resets_runtime_brain_and_cleans_results(self) -> None:
        repo_root = REPO_ROOT / "benchmarks" / "tools" / "tests" / "_tmp_prepare_runtime_repo"
        if repo_root.exists():
            shutil.rmtree(repo_root)

        try:
            repo_root.mkdir(parents=True)
            empty_context = {
                "active_task": None,
                "constraints": [],
                "decisions": [],
                "open_issues": [],
            }

            (repo_root / "benchmarks" / "scenarios").mkdir(parents=True)
            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True)

            empty_root = repo_root / "reasoning_brain_storage" / "templates" / "empty"
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            seeded_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "seeded"

            for brain_root in (empty_root, runtime_root, seeded_root):
                _create_minimal_brain_root(brain_root, empty_context)

            (empty_root / "marker.txt").write_text(
                "empty-brain-marker\n",
                encoding="utf-8",
            )
            (runtime_root / "stale.txt").write_text(
                "stale-runtime-state\n",
                encoding="utf-8",
            )

            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                for suffix in (TRACE_LOG_SUFFIX, EVENTS_JSONL_SUFFIX, RESULT_JSON_SUFFIX):
                    artifact_path = repo_root / "benchmarks" / "results" / mode / f"{SCENARIO_ID}{suffix}"
                    artifact_path.write_text("temporary\n", encoding="utf-8")

            prepare_clean_benchmark_runtime(repo_root)

            self.assertTrue(
                (runtime_root / "marker.txt").is_file()
            )
            self.assertFalse(
                (runtime_root / "stale.txt").exists()
            )

            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                mode_dir = repo_root / "benchmarks" / "results" / mode
                self.assertTrue(mode_dir.is_dir())
                self.assertEqual(list(mode_dir.iterdir()), [])
        finally:
            if repo_root.exists():
                shutil.rmtree(repo_root)

    def test_agent_metadata_uses_same_model_resolver_as_execution(self) -> None:
        with patch.dict("os.environ", {"OPENAI_MODEL": "gpt-test-benchmark"}, clear=False):
            metadata = get_benchmark_agent_metadata(adapter_name=ADAPTER_NAME)
            self.assertEqual(metadata["agent_model"], resolve_openai_model())

        self.assertEqual(metadata["adapter"], ADAPTER_NAME)
        self.assertEqual(metadata["agent_model"], "gpt-test-benchmark")
        self.assertTrue(metadata["full_agent_name"])

    def test_profile_defaults_brain_lifecycle_when_fields_are_absent(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_default")
        try:
            profile_path = temp_profiles_dir / "minimal.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "minimal",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                profile = run_benchmarks_module.load_profile("minimal")

            self.assertEqual(profile.brain_mode, "accumulative")
            self.assertFalse(profile.diagnostic_modes.pr_ephemeral)
            self.assertFalse(profile.diagnostic_modes.post_run_artifact_harvest)
            self.assertEqual(profile.brain_in.type, "empty")
            self.assertIsNone(profile.brain_in.ref)
            self.assertEqual(profile.brain_out.mode, "continue")
            self.assertIsNone(profile.brain_out.ref)
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_resolve_execution_modes_excludes_pr_ephemeral_by_default(self) -> None:
        self.assertEqual(
            run_benchmarks_module.resolve_execution_modes(),
            (BASELINE, PR_LIGHT_BRAIN),
        )

    def test_resolve_execution_modes_includes_pr_ephemeral_when_enabled(self) -> None:
        profile = run_benchmarks_module._default_benchmark_profile()._replace(
            diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=True),
        )
        self.assertEqual(
            run_benchmarks_module.resolve_execution_modes(profile),
            (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN),
        )

    def test_resolve_ordinary_scenario_layers_appends_mandatory_stress_case(self) -> None:
        profile = run_benchmarks_module.BenchmarkProfile(
            diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
            brain_mode="accumulative",
            brain_in=run_benchmarks_module.BrainInPolicy(type="empty", ref=None),
            brain_out=run_benchmarks_module.BrainOutPolicy(mode="continue", ref=None),
            name="test",
            backend="gemini",
            model="gemini-flash-lite-latest",
            scenario_subset=(
                "sc_00_stateless_direct_transform",
                CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
            ),
            showcase=run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
            mode_to_key_mapping="strict",
            timeout_seconds=20,
            inter_scenario_delay_seconds=1,
            on_429_first="wait_30s_retry_once",
            on_429_second="stop_run",
            purpose="test",
        )

        plan = run_benchmarks_module.resolve_ordinary_scenario_layers(profile)

        self.assertEqual(
            plan.diagnostic_scenario_ids,
            ("sc_00_stateless_direct_transform", CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID),
        )
        self.assertEqual(
            plan.stress_scenario_ids,
            (run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,),
        )
        self.assertEqual(
            plan.all_scenario_ids,
            (
                "sc_00_stateless_direct_transform",
                CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
            ),
        )

    def test_write_scenario_layer_manifest_marks_diagnostic_vs_stress(self) -> None:
        repo_root = _workspace_temp_dir("scenario_layer_manifest")
        try:
            manifest_path = run_benchmarks_module.write_scenario_layer_manifest(
                repo_root,
                run_id="test_run",
                diagnostic_scenario_ids=(
                    "sc_00_stateless_direct_transform",
                    CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                ),
                stress_scenario_ids=(run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,),
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["diagnostic_scenario_ids"],
                ["sc_00_stateless_direct_transform", CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID],
            )
            self.assertEqual(
                manifest["stress_scenario_ids"],
                [run_benchmarks_module.KILLER_STRESS_SCENARIO_ID],
            )
            self.assertEqual(
                manifest["scenarios"][-1],
                {
                    "execution_order": 3,
                    "scenario_id": run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
                    "scenario_role": "integration_stress",
                    "stress_case": True,
                },
            )
            self.assertEqual(
                manifest["scenarios"][0]["scenario_role"],
                "diagnostic",
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_repo_profiles_use_canonical_diagnostic_subset(self) -> None:
        profile_names = (
            "gemini_flash_lite_latest",
            "gemini_flash_latest",
            "gemini_gemma_3_27b",
        )

        for profile_name in profile_names:
            with self.subTest(profile=profile_name):
                profile = run_benchmarks_module.load_profile(profile_name)
                self.assertEqual(
                    profile.scenario_subset,
                    EXPECTED_PROFILE_SCENARIO_SUBSETS[profile_name],
                )
                self.assertEqual(profile.showcase, run_benchmarks_module.KILLER_STRESS_SCENARIO_ID)
                self.assertNotIn("sc_99_killer_all_scenarios", profile.scenario_subset)
                self.assertNotIn("sc_0_interrupt_compress_continue", profile.scenario_subset)
                self.assertNotIn("sc_1_context_drift", profile.scenario_subset)
                self.assertNotIn("sc_2_context_compression", profile.scenario_subset)
                self.assertNotIn("sc_5_math_reasoning", profile.scenario_subset)
                self.assertNotIn("sc_7_stateless_direct_transform", profile.scenario_subset)
                self.assertNotIn("sc_8_structural_retention", profile.scenario_subset)
                self.assertFalse(profile.diagnostic_modes.pr_ephemeral)

    def test_repo_profile_files_declare_valid_artifact_and_context_runtime_knobs(self) -> None:
        required_runtime_knobs = (
            "working_context_format",
            "artifact_generator_mode",
            "artifact_filter_mode",
        )

        profile_paths = sorted(run_benchmarks_module.PROFILES_DIR.glob("*.json"))
        self.assertGreater(len(profile_paths), 0)

        for profile_path in profile_paths:
            with self.subTest(profile=profile_path.name):
                raw_profile = json.loads(profile_path.read_text(encoding="utf-8"))
                for field_name in required_runtime_knobs:
                    self.assertIn(field_name, raw_profile)

                self.assertIn(
                    raw_profile["working_context_format"],
                    run_benchmarks_module.SUPPORTED_WORKING_CONTEXT_FORMATS,
                )
                self.assertIn(
                    raw_profile["artifact_generator_mode"],
                    run_benchmarks_module.SUPPORTED_ARTIFACT_GENERATOR_MODES,
                )
                self.assertIn(
                    raw_profile["artifact_filter_mode"],
                    run_benchmarks_module.SUPPORTED_ARTIFACT_FILTER_MODES,
                )

                profile = run_benchmarks_module.load_profile(profile_path.stem)
                self.assertEqual(
                    profile.working_context_format,
                    raw_profile["working_context_format"],
                )
                self.assertEqual(
                    profile.artifact_generator_mode,
                    raw_profile["artifact_generator_mode"],
                )
                self.assertEqual(
                    profile.artifact_filter_mode,
                    raw_profile["artifact_filter_mode"],
                )

    def test_repo_profiles_append_sc9_once_via_runner_scenario_plan(self) -> None:
        profile_names = (
            "gemini_flash_lite_latest",
            "gemini_flash_latest",
            "gemini_gemma_3_27b",
        )

        for profile_name in profile_names:
            with self.subTest(profile=profile_name):
                profile = run_benchmarks_module.load_profile(profile_name)
                plan = run_benchmarks_module.resolve_ordinary_scenario_layers(profile)

                self.assertEqual(
                    plan.diagnostic_scenario_ids,
                    EXPECTED_PROFILE_SCENARIO_SUBSETS[profile_name],
                )
                self.assertEqual(
                    plan.stress_scenario_ids,
                    (run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,),
                )
                self.assertEqual(
                    plan.all_scenario_ids.count(run_benchmarks_module.KILLER_STRESS_SCENARIO_ID),
                    1,
                )
                self.assertEqual(
                    plan.all_scenario_ids[-1],
                    run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
                )

    def test_new_repo_profiles_load_successfully(self) -> None:
        flash_profile = run_benchmarks_module.load_profile("gemini_flash_latest")
        gemma_profile = run_benchmarks_module.load_profile("gemini_gemma_3_27b")

        self.assertEqual(flash_profile.backend, "gemini")
        self.assertEqual(flash_profile.model, "gemini-flash-latest")
        self.assertEqual(
            flash_profile.showcase,
            run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
        )
        self.assertFalse(flash_profile.diagnostic_modes.pr_ephemeral)
        self.assertEqual(gemma_profile.backend, "gemini")
        self.assertEqual(gemma_profile.model, "gemma-3-27b-it")
        self.assertEqual(
            gemma_profile.showcase,
            run_benchmarks_module.KILLER_STRESS_SCENARIO_ID,
        )
        self.assertFalse(gemma_profile.diagnostic_modes.pr_ephemeral)

    def test_active_canonical_scenario_files_exist_and_match_file_identity(self) -> None:
        for scenario_id in CANONICAL_DIAGNOSTIC_SCENARIO_SUBSET:
            with self.subTest(scenario_id=scenario_id):
                json_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                metadata_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.metadata.json"
                md_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.md"
                self.assertTrue(json_path.is_file())
                self.assertTrue(metadata_path.is_file())
                self.assertTrue(md_path.is_file())

                scenario = json.loads(json_path.read_text(encoding="utf-8"))
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.assertEqual(scenario["scenario_id"], scenario_id)
                self.assertEqual(metadata["identity"]["scenario_id"], scenario_id)
                self.assertIsInstance(scenario["scenario_name"], str)
                self.assertTrue(scenario["scenario_name"].strip())
                self.assertIsInstance(scenario["scenario_type"], str)
                self.assertTrue(scenario["scenario_type"].strip())

    def test_active_canonical_scenario_metadata_is_structurally_coherent(self) -> None:
        for scenario_id in CANONICAL_DIAGNOSTIC_SCENARIO_SUBSET:
            with self.subTest(scenario_id=scenario_id):
                json_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.json"
                metadata_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.metadata.json"
                md_path = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}.md"
                scenario = json.loads(json_path.read_text(encoding="utf-8"))
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                markdown = md_path.read_text(encoding="utf-8")
                loaded = load_benchmark_scenario(self.paths, scenario_id)

                self.assertNotIn("interpretation_spec", scenario)
                interpretation_contract = metadata.get("interpretation_contract")
                self.assertIsInstance(interpretation_contract, dict)
                interpretation_spec = loaded.config.get("interpretation_spec")
                self.assertIsInstance(interpretation_spec, dict)
                if scenario_id == CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID:
                    self.assertEqual(
                        metadata["interpretation_support"]["trajectory_readiness"],
                        "ready",
                    )
                else:
                    self.assertNotEqual(
                        metadata["interpretation_support"]["trajectory_readiness"],
                        "ready",
                    )
                self.assertEqual(
                    loaded.config["trajectory_readiness"],
                    metadata["interpretation_support"]["trajectory_readiness"],
                )
                self.assertEqual(
                    interpretation_contract["interpretation_variant"],
                    ACTIVE_SCENARIO_INTERPRETATION_EXPECTATIONS[scenario_id]["interpretation_variant"],
                )
                self.assertEqual(
                    interpretation_contract["layer_support"],
                    ACTIVE_SCENARIO_INTERPRETATION_EXPECTATIONS[scenario_id]["layer_support"],
                )
                self.assertEqual(
                    interpretation_spec["interpretation_variant"],
                    interpretation_contract["interpretation_variant"],
                )
                self.assertEqual(
                    interpretation_spec["layer_support"],
                    interpretation_contract["layer_support"],
                )
                self.assertIn("## Interpretation readiness", markdown)

                retention_contract = metadata.get("retention_contract")
                retention_spec = loaded.config.get("retention_spec")
                retention_support = interpretation_spec["layer_support"]["retention"]
                if retention_support == "unsupported":
                    self.assertIsNone(retention_contract)
                    self.assertIsNone(retention_spec)
                    continue

                self.assertIsInstance(retention_contract, dict)
                self.assertIsInstance(retention_spec, dict)
                self.assertTrue(retention_contract["retention_type"])
                self.assertEqual(
                    retention_spec["retention_type"],
                    retention_contract["retention_type"],
                )
                self.assertIsInstance(retention_contract.get("checkpoints"), list)
                self.assertGreater(len(retention_contract["checkpoints"]), 0)
                self.assertEqual(
                    retention_spec["checkpoints"],
                    retention_contract["checkpoints"],
                )
                self.assertIsInstance(
                    retention_contract.get("required_exact_section_headings"),
                    list,
                )
                self.assertGreater(len(retention_contract["required_exact_section_headings"]), 0)
                self.assertEqual(
                    retention_spec["required_exact_section_headings"],
                    retention_contract["required_exact_section_headings"],
                )
                self.assertIsInstance(retention_contract.get("final_sections"), dict)
                self.assertTrue(retention_contract["final_sections"]["retained"])
                self.assertTrue(retention_contract["final_sections"]["lost"])
                self.assertEqual(
                    retention_spec["final_sections"],
                    retention_contract["final_sections"],
                )
                if "unit_groups" in retention_contract:
                    self.assertEqual(
                        retention_spec.get("unit_groups"),
                        retention_contract["unit_groups"],
                    )

                if retention_support == "enabled":
                    self.assertFalse(retention_spec["retention_type"].endswith("_deferred"))
                else:
                    self.assertTrue(retention_spec["retention_type"].endswith("_deferred"))

                correctness_support = interpretation_spec["layer_support"]["correctness"]
                if correctness_support == "unsupported":
                    self.assertIsNone(retention_spec.get("correctness_spec"))
                elif correctness_support == "enabled":
                    self.assertIsInstance(retention_spec.get("correctness_spec"), dict)

                correctness_contract = metadata.get("correctness_contract")
                if metadata["execution_contract"]["scenario_mode"] == "sectioned":
                    self.assertIsNone(correctness_contract)
                elif isinstance(correctness_contract, dict):
                    expected_correctness_contract = correctness_contract
                    if metadata.get("expected_ready"):
                        expected_payload = json.loads(
                            (
                                REPO_ROOT
                                / "benchmarks"
                                / "scenarios"
                                / metadata["expected_file"]
                            ).read_text(encoding="utf-8")
                        )
                        expected_correctness_contract = {
                            "slot_section_heading": correctness_contract[
                                "slot_section_heading"
                            ],
                            "value_match_policy": correctness_contract[
                                "value_match_policy"
                            ],
                            "expected_slot_values": expected_payload["final"][
                                "expected_slot_values"
                            ],
                        }
                    self.assertEqual(
                        loaded.config.get("correctness_spec"),
                        expected_correctness_contract,
                    )
                    self.assertEqual(
                        retention_spec.get("correctness_spec"),
                        expected_correctness_contract,
                    )

                ghost_support = interpretation_spec["layer_support"]["ghost"]
                if ghost_support == "unsupported":
                    self.assertIsNone(retention_spec.get("ghost_spec"))
                else:
                    self.assertIsInstance(retention_spec.get("ghost_spec"), dict)

    def test_sc9_top_level_ghost_contract_remains_deferred_in_metadata(self) -> None:
        scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / "sc_99_killer_all_scenarios.json"
        metadata_path = scenario_metadata_path(self.paths, "sc_99_killer_all_scenarios")
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        loaded = load_benchmark_scenario(self.paths, "sc_99_killer_all_scenarios")

        self.assertIsNone(metadata["ghost_contract"])
        self.assertFalse(metadata["migration_lock"]["ghost_contract"])
        self.assertIsInstance(scenario["retention_spec"].get("ghost_spec"), dict)
        self.assertEqual(
            loaded.config["retention_spec"].get("ghost_spec"),
            scenario["retention_spec"]["ghost_spec"],
        )

    def test_sc9_task_json_does_not_keep_migrated_section_correctness_truth(self) -> None:
        scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / "sc_99_killer_all_scenarios.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        section_2 = next(
            section
            for section in scenario["retention_spec"]["sections"]
            if section["section_id"] == "section_2_math_state_loss"
        )
        self.assertNotIn("correctness_spec", section_2)

    def test_sc9_task_json_does_not_keep_migrated_section_ghost_truth(self) -> None:
        scenario_path = REPO_ROOT / "benchmarks" / "scenarios" / "sc_99_killer_all_scenarios.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        section_1 = next(
            section
            for section in scenario["retention_spec"]["sections"]
            if section["section_id"] == "section_1_structural_retention"
        )
        self.assertNotIn("ghost_spec", section_1)

    def test_sc9_loader_uses_metadata_as_authoritative_source_for_section_correctness_contracts(
        self,
    ) -> None:
        repo_root = _workspace_temp_dir("sc9_section_correctness_metadata_authoritative")
        try:
            _build_sc9_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_path = repo_root / "benchmarks" / "scenarios" / "sc_99_killer_all_scenarios.json"
            metadata_path = scenario_metadata_path(paths, "sc_99_killer_all_scenarios")

            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            section_2 = next(
                section
                for section in scenario["retention_spec"]["sections"]
                if section["section_id"] == "section_2_math_state_loss"
            )
            section_2["correctness_spec"] = {
                "slot_section_heading": "WRONG SECTION",
                "value_match_policy": "wrong",
                "expected_slot_values": {"WRONG": "WRONG"},
            }
            scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["section_correctness_contracts"][0]["correctness_contract"] = {
                "slot_section_heading": "SECTION 2 - MATH STATE LOSS",
                "value_match_policy": "exact_string",
                "expected_slot_values": {
                    "PRODUCT_1": "1081",
                    "PRODUCT_2": "1102",
                    "COMBINED_SUM": "2183",
                    "AFTER_SUBTRACTION": "1818",
                    "AFTER_DIVISION": "606",
                    "AFTER_ADDITION": "657",
                    "AFTER_MULTIPLICATION": "1314",
                    "AFTER_REDUCTION": "438",
                    "FINAL_NUMERATOR": "437",
                    "FINAL_RESULT": "437/7",
                },
            }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
            loaded_section_2 = next(
                section
                for section in loaded.config["retention_spec"]["sections"]
                if section["section_id"] == "section_2_math_state_loss"
            )
            self.assertEqual(
                loaded_section_2["correctness_spec"],
                metadata["section_correctness_contracts"][0]["correctness_contract"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_loader_fails_on_section_correctness_metadata_section_id_mismatch(self) -> None:
        repo_root = _workspace_temp_dir("sc9_section_correctness_section_id_mismatch")
        try:
            _build_sc9_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            metadata_path = scenario_metadata_path(paths, "sc_99_killer_all_scenarios")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["section_correctness_contracts"][0]["section_id"] = "section_missing"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "section correctness metadata|unknown section ids",
            ):
                load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_loader_uses_metadata_as_authoritative_source_for_section_ghost_contracts(
        self,
    ) -> None:
        repo_root = _workspace_temp_dir("sc9_section_ghost_metadata_authoritative")
        try:
            _build_sc9_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_path = repo_root / "benchmarks" / "scenarios" / "sc_99_killer_all_scenarios.json"
            metadata_path = scenario_metadata_path(paths, "sc_99_killer_all_scenarios")

            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            section_1 = next(
                section
                for section in scenario["retention_spec"]["sections"]
                if section["section_id"] == "section_1_structural_retention"
            )
            section_1["ghost_spec"] = {
                "token_pattern": "WRONG",
                "valid_transformations": {"WRONG": ["WRONG"]},
            }
            scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["section_ghost_contracts"][0]["ghost_contract"] = {
                "token_pattern": "[A-Z][0-9]+",
                "valid_transformations": {},
            }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            loaded = load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
            loaded_section_1 = next(
                section
                for section in loaded.config["retention_spec"]["sections"]
                if section["section_id"] == "section_1_structural_retention"
            )
            self.assertEqual(
                loaded_section_1["ghost_spec"],
                metadata["section_ghost_contracts"][0]["ghost_contract"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_loader_fails_on_section_ghost_metadata_section_id_mismatch(self) -> None:
        repo_root = _workspace_temp_dir("sc9_section_ghost_section_id_mismatch")
        try:
            _build_sc9_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            metadata_path = scenario_metadata_path(paths, "sc_99_killer_all_scenarios")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["section_ghost_contracts"][0]["section_id"] = "section_missing"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "section ghost metadata|unknown section ids",
            ):
                load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_interpretation_dispatch_uses_metadata_for_unknown_structural_clone(self) -> None:
        repo_root = _workspace_temp_dir("metadata_driven_structural_clone")
        try:
            (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
            (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
            (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)
            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

            custom_scenario_id = "sc_custom_structural_clone"
            source_json = json.loads(
                (
                    REPO_ROOT
                    / "benchmarks"
                    / "scenarios"
                    / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.json"
                ).read_text(encoding="utf-8")
            )
            source_json["scenario_id"] = custom_scenario_id
            source_metadata = json.loads(
                (
                    REPO_ROOT
                    / "benchmarks"
                    / "scenarios"
                    / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.metadata.json"
                ).read_text(encoding="utf-8")
            )
            source_metadata["identity"]["scenario_id"] = custom_scenario_id
            source_md = (
                REPO_ROOT
                / "benchmarks"
                / "scenarios"
                / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.md"
            ).read_text(encoding="utf-8")

            (repo_root / "benchmarks" / "scenarios" / f"{custom_scenario_id}.json").write_text(
                json.dumps(source_json, indent=2) + "\n",
                encoding="utf-8",
            )
            (repo_root / "benchmarks" / "scenarios" / f"{custom_scenario_id}.metadata.json").write_text(
                json.dumps(source_metadata, indent=2) + "\n",
                encoding="utf-8",
            )
            (repo_root / "benchmarks" / "scenarios" / f"{custom_scenario_id}.md").write_text(
                source_md,
                encoding="utf-8",
            )

            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=custom_scenario_id,
                agent_output=(
                    "CHECKPOINT 0 - INITIAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 5 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 10 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 15 - REVERSE\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 20 - FINAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "FINAL RETAINED UNITS\n"
                    "F1, F2, F3, F4, F5, F6, F7, F8, F9, D1, D2, D3, D4, D5, D6, C1, C2, C3, C4\n\n"
                    "FINAL LOST UNITS\n"
                    "F10"
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=custom_scenario_id,
                agent_output=(
                    "CHECKPOINT 0 - INITIAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 5 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 10 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 15 - REVERSE\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 20 - FINAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "FINAL RETAINED UNITS\n"
                    "F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, D1, D2, D3, D4, D5, D6, C1, C2, C3, C4\n\n"
                    "FINAL LOST UNITS\n"
                    "NONE"
                ),
            )

            retention_layer_path, _ = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=custom_scenario_id,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )

            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            self.assertEqual(
                retention_layer["interpretation_metadata"],
                {
                    "scenario_id": custom_scenario_id,
                    "scenario_type": "structural_retention",
                    "interpretation_variant": "structural_retention_with_ghost",
                },
            )
            self.assertEqual(
                retention_layer["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "deferred",
                    "ghost": "enabled",
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_deferred_interpretation_scenario_does_not_generate_artifacts(self) -> None:
        repo_root = _workspace_temp_dir("deferred_interpretation_skip")
        try:
            (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
            (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
            (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)
            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

            scenario_id = "sc_02_n_back_anomaly_trap"
            _copy_repo_scenario_bundle(repo_root, scenario_id)

            generated = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=scenario_id,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            self.assertIsNone(generated)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_resolve_interpretation_contract_uses_metadata_and_loads_sc9_composite_contract(self) -> None:
        structural_contract = resolve_scenario_interpretation_contract(
            scenario_id="sc_custom_structural_clone",
            scenario_type="structural_retention",
            scenario_config={
                "interpretation_spec": {
                    "interpretation_variant": "structural_retention_with_ghost",
                    "layer_support": {
                        "retention": "enabled",
                        "correctness": "deferred",
                        "ghost": "enabled",
                    },
                    "reason": "metadata-driven clone",
                }
            },
        )
        self.assertEqual(
            structural_contract,
            {
                "interpretation_variant": "structural_retention_with_ghost",
                "layer_support": {
                    "retention": "enabled",
                    "correctness": "deferred",
                    "ghost": "enabled",
                },
                "reason": "metadata-driven clone",
            },
        )

        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        sc9_contract = resolve_scenario_interpretation_contract(
            scenario_id="sc_99_killer_all_scenarios",
            scenario_type=sc9_config["scenario_type"],
            scenario_config=sc9_config,
        )
        self.assertEqual(
            sc9_contract,
            {
                "interpretation_variant": "sectioned_composite_interpretation",
                "layer_support": {
                    "retention": "enabled",
                    "correctness": "enabled",
                    "ghost": "enabled",
                },
                "reason": "composite stress scenario with independent section evaluation; sections 1-2 are interpreted now and sections 3-5 remain deferred",
            },
        )

    def test_sc9_composition_schema_is_explicit_and_valid(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")

        self.assertEqual(sc9_config["scenario_mode"], "sectioned")
        self.assertTrue(sc9_config["showcase"])
        composition_spec = sc9_config.get("composition_spec")
        self.assertIsInstance(composition_spec, dict)
        self.assertEqual(composition_spec["composition_type"], "sectioned_by_reference")
        self.assertEqual(composition_spec["resolution_policy"], "explicit_sections_only")
        self.assertEqual(
            composition_spec["namespace_format"],
            "{section_id}__{source_step_id}",
        )

        sections = composition_spec.get("sections")
        self.assertIsInstance(sections, list)
        self.assertEqual(len(sections), 5)
        for section in sections:
            with self.subTest(section_id=section["section_id"]):
                self.assertIsInstance(section["include_steps"], list)
                self.assertGreater(len(section["include_steps"]), 0)
                self.assertIsInstance(section["return_to_origin"], bool)
                self.assertEqual(
                    set(section["contract_imports"].keys()),
                    {
                        "retention_type",
                        "unit_groups",
                        "checkpoints",
                        "final_sections",
                        "required_exact_section_headings",
                        "ghost_spec",
                        "correctness_spec",
                    },
                )

        validation = validate_sectioned_reference_composition(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=sc9_config,
            strict=True,
        )
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["errors"], [])
        self.assertEqual(len(validation["sections"]), 5)

    def test_sc9_composition_validation_requires_explicit_include_steps(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][2]["include_steps"] = []

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(any("include_steps" in error for error in validation["errors"]))

    def test_sc9_composition_validation_requires_explicit_return_to_origin(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        del mutated["composition_spec"]["sections"][0]["return_to_origin"]

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("return_to_origin" in error for error in validation["errors"])
        )
        with self.assertRaisesRegex(ValueError, "return_to_origin"):
            validate_sectioned_reference_composition(
                self.paths,
                scenario_id="sc_99_killer_all_scenarios",
                config=mutated,
                strict=True,
            )

    def test_sc9_composition_validation_fails_on_missing_source_scenario(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][0]["source_scenario_id"] = "sc_missing_source"

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("sc_missing_source" in error for error in validation["errors"])
        )

    def test_sc9_composition_validation_fails_on_missing_step_id(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][1]["include_steps"].append("step_missing")

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(any("step_missing" in error for error in validation["errors"]))

    def test_sc9_composition_validation_fails_on_duplicate_section_ids(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][1]["section_id"] = (
            mutated["composition_spec"]["sections"][0]["section_id"]
        )

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(any("duplicate section_id" in error for error in validation["errors"]))

    def test_sc9_composition_validation_fails_on_invalid_max_percent_total(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][4]["max_percent"] = 10.0

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(any("must equal exactly 100" in error for error in validation["errors"]))

    def test_sc9_composition_validation_fails_on_invalid_contract_imports(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        del mutated["composition_spec"]["sections"][0]["contract_imports"]["ghost_spec"]

        validation = build_sectioned_reference_composition_validation_result(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=mutated,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(any("contract_imports" in error for error in validation["errors"]))

    def test_sc9_validated_composition_resolves_to_explicit_scenario(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")

        resolution = resolve_sectioned_reference_scenario(
            self.paths,
            scenario_id="sc_99_killer_all_scenarios",
            config=sc9_config,
            strict=True,
        )

        self.assertTrue(resolution["valid"])
        resolved_config = resolution["resolved_config"]
        self.assertEqual(resolved_config["scenario_id"], "sc_99_killer_all_scenarios")
        self.assertEqual(resolved_config["resolved_from"], "sc_99_killer_all_scenarios")
        self.assertEqual(
            resolved_config["composition_spec"]["resolution_policy"],
            "explicit_sections_only",
        )
        self.assertEqual(len(resolved_config["resolved_sections"]), 5)
        self.assertEqual(len(resolved_config["retention_spec"]["resolved_sections"]), 5)

        resolved_steps = resolved_config["steps"]
        expected_step_count = sum(
            len(section["include_steps"])
            for section in sc9_config["composition_spec"]["sections"]
        )
        self.assertEqual(len(resolved_steps), expected_step_count)
        self.assertEqual(len(resolved_config["execution_flow"]), expected_step_count)
        self.assertEqual(
            resolved_steps[0]["step_id"],
            "section_1_structural_retention__step_00_initial_and_rules",
        )
        self.assertEqual(
            resolved_steps[0]["resolved_step_id"],
            "section_1_structural_retention__step_00_initial_and_rules",
        )
        self.assertEqual(
            resolved_steps[0]["source_step_id"],
            "step_00_initial_and_rules",
        )
        self.assertEqual(
            resolved_steps[0]["source_scenario_id"],
            "sc_01_structural_retention",
        )
        self.assertEqual(
            resolved_steps[-1]["step_id"],
            "section_5_move_clock_hands__step_99_final_report",
        )

        section_2 = next(
            section
            for section in resolved_config["resolved_sections"]
            if section["section_id"] == "section_2_math_state_loss"
        )
        self.assertEqual(section_2["return_to_origin"], True)
        self.assertIn("correctness_spec", section_2["resolved_contract"])
        self.assertNotIn("ghost_spec", section_2["resolved_contract"])
        self.assertEqual(
            [step["source_step_id"] for step in section_2["resolved_steps"][:3]],
            ["step_00_initial_and_rules", "step_01_action", "step_02_action"],
        )
        for section in resolved_config["resolved_sections"]:
            source_config = self._load_scenario_config(section["source_scenario_id"])
            source_step_ids = {
                step["step_id"]
                for step in source_config["steps"]
            }
            missing_step_ids = [
                step_id
                for step_id in section["include_steps"]
                if step_id not in source_step_ids
            ]
            self.assertEqual(missing_step_ids, [])

    def test_sc9_invalid_composition_does_not_resolve(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        mutated = copy.deepcopy(sc9_config)
        mutated["composition_spec"]["sections"][0]["include_steps"].append("step_missing")

        with self.assertRaisesRegex(ValueError, "step_missing"):
            resolve_sectioned_reference_scenario(
                self.paths,
                scenario_id="sc_99_killer_all_scenarios",
                config=mutated,
                strict=True,
            )

    def test_ordinary_scenario_without_steps_fails_authoring_validation(self) -> None:
        repo_root = _workspace_temp_dir("ordinary_without_steps")
        try:
            _build_structural_retention_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.json"
            )
            scenario_payload = json.loads(scenario_path.read_text(encoding="utf-8"))
            del scenario_payload["steps"]
            scenario_path.write_text(
                json.dumps(scenario_payload, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "steps"):
                load_benchmark_scenario(paths, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_composition_without_raw_steps_loads_and_resolves(self) -> None:
        sc9_config = self._load_scenario_config("sc_99_killer_all_scenarios")
        self.assertNotIn("steps", sc9_config)

        scenario = load_benchmark_scenario(self.paths, "sc_99_killer_all_scenarios")

        self.assertEqual(scenario.config["resolved_from"], "sc_99_killer_all_scenarios")
        self.assertEqual(len(scenario.config["steps"]), 90)
        self.assertEqual(
            scenario.config["steps"][0]["step_id"],
            "section_1_structural_retention__step_00_initial_and_rules",
        )

    def test_sc9_composition_rejects_raw_top_level_steps(self) -> None:
        repo_root = _workspace_temp_dir("sc9_raw_steps_rejected")
        try:
            _build_sc9_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / "sc_99_killer_all_scenarios.json"
            )
            scenario_payload = json.loads(scenario_path.read_text(encoding="utf-8"))
            scenario_payload["steps"] = [
                {
                    "step_id": "legacy_raw_step",
                    "instruction": "This raw step must never be used as fallback.",
                }
            ]
            scenario_path.write_text(
                json.dumps(scenario_payload, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "must not define top-level steps"):
                load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_execution_load_path_uses_resolved_explicit_steps(self) -> None:
        scenario = gemini_adapter_module.load_scenario(
            self.paths,
            "sc_99_killer_all_scenarios",
        )
        self.assertEqual(scenario.scenario_id, "sc_99_killer_all_scenarios")
        self.assertEqual(scenario.config["resolved_from"], "sc_99_killer_all_scenarios")
        self.assertEqual(
            scenario.config["steps"][0]["step_id"],
            "section_1_structural_retention__step_00_initial_and_rules",
        )
        self.assertEqual(
            scenario.config["steps"][0]["source_scenario_id"],
            "sc_01_structural_retention",
        )
        self.assertEqual(
            scenario.config["steps"][-1]["step_id"],
            "section_5_move_clock_hands__step_99_final_report",
        )

    def test_ordinary_scenario_execution_load_path_remains_unchanged(self) -> None:
        scenario = load_benchmark_scenario(
            self.paths,
            CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
        )
        self.assertNotIn("resolved_from", scenario.config)
        self.assertEqual(
            scenario.config["steps"][0]["step_id"],
            "step_00_initial_and_rules",
        )
        self.assertNotIn("source_scenario_id", scenario.config["steps"][0])

    def test_runner_writes_sc9_resolved_execution_artifact(self) -> None:
        repo_root = _workspace_temp_dir("sc9_resolved_artifact")
        try:
            _build_sc9_repo(repo_root)
            artifact_paths = run_benchmarks_module.write_resolved_execution_artifacts(
                repo_root,
                run_id="test_run",
                scenario_ids=("sc_99_killer_all_scenarios",),
            )
            self.assertEqual(len(artifact_paths), 1)
            artifact_path = artifact_paths[0]
            self.assertEqual(artifact_path.name, "sc_99_resolved.json")
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["scenario_id"], "sc_99_killer_all_scenarios")
            self.assertEqual(payload["resolved_from"], "sc_99_killer_all_scenarios")
            self.assertEqual(len(payload["resolved_sections"]), 5)
            self.assertEqual(len(payload["retention_spec"]["resolved_sections"]), 5)
            self.assertEqual(
                payload["steps"][0]["resolved_step_id"],
                "section_1_structural_retention__step_00_initial_and_rules",
            )
            self.assertEqual(
                payload["execution_flow"][0],
                "section_1_structural_retention__step_00_initial_and_rules",
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_interpretation_uses_resolved_structure_without_source_requery(self) -> None:
        repo_root = _workspace_temp_dir("sc9_resolved_interpretation_only")
        try:
            _build_sc9_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id="sc_99_killer_all_scenarios",
                agent_output=_sc9_agent_output(
                    structural_units=(
                        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
                        "D1", "D2", "D3", "D4", "D5", "D6",
                        "C1", "C2", "C3", "C4", "X1",
                    ),
                    math_slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 62.42857142857143",
                    ),
                    retained_sections=("section_2_math_state_loss",),
                    lost_sections=(
                        "section_1_structural_retention",
                        "section_3_n_back_anomaly_trap",
                        "section_4_trail_making",
                        "section_5_move_clock_hands",
                    ),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id="sc_99_killer_all_scenarios",
                agent_output=_sc9_agent_output(
                    structural_units=(
                        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
                        "D1", "D2", "D3", "D4", "D5", "D6",
                        "C1", "C2", "C3", "C4",
                    ),
                    math_slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 437/7",
                    ),
                    retained_sections=(
                        "section_1_structural_retention",
                        "section_2_math_state_loss",
                    ),
                    lost_sections=(
                        "section_3_n_back_anomaly_trap",
                        "section_4_trail_making",
                        "section_5_move_clock_hands",
                    ),
                ),
            )

            paths = BenchmarkPaths(repo_root=repo_root)
            scenario = load_benchmark_scenario(paths, "sc_99_killer_all_scenarios")
            interpretation_contract = resolve_scenario_interpretation_contract(
                scenario_id="sc_99_killer_all_scenarios",
                scenario_type=scenario.config["scenario_type"],
                scenario_config=scenario.config,
            )

            for scenario_id in SC9_COMPOSITION_SOURCE_SCENARIO_IDS:
                for suffix in (".json", ".md"):
                    (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}{suffix}").unlink()

            mutated_retention_spec = copy.deepcopy(scenario.config["retention_spec"])
            del mutated_retention_spec["sections"]

            retention_layer = build_sectioned_composite_retention_layer(
                paths=paths,
                scenario_id="sc_99_killer_all_scenarios",
                scenario_type=scenario.config["scenario_type"],
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                retention_spec=mutated_retention_spec,
                interpretation_contract=interpretation_contract,
            )

            sections = {section["section_id"]: section for section in retention_layer["sections"]}
            self.assertEqual(
                sections["section_1_structural_retention"]["source_scenario_id"],
                "sc_01_structural_retention",
            )
            self.assertEqual(
                sections["section_2_math_state_loss"]["include_steps"][:2],
                ["step_00_initial_and_rules", "step_01_action"],
            )
            self.assertIsNone(sections["section_3_n_back_anomaly_trap"]["section_result"])
            top_final = retention_layer["final_summary"]
            self.assertEqual(top_final[BASELINE]["total_retained_percent"], 39.0)
            self.assertEqual(top_final[BASELINE]["total_correctness_percent"], 18.0)
            self.assertEqual(top_final[BASELINE]["total_ghost_percent"], 1.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_retained_percent"], 40.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_correctness_percent"], 20.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_ghost_percent"], 0.0)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_scenario_interpretation_support_manifest_marks_supported_deferred_and_unsupported_layers(self) -> None:
        repo_root = _workspace_temp_dir("interpretation_support_manifest")
        try:
            (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
            for scenario_id in (
                "sc_00_stateless_direct_transform",
                CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                "sc_03_math_state_loss",
                "sc_05_digit_span_n_back_hybrid",
                "sc_99_killer_all_scenarios",
                *SC9_COMPOSITION_SOURCE_SCENARIO_IDS,
            ):
                _copy_repo_scenario_bundle(repo_root, scenario_id)

            manifest_path = run_benchmarks_module.write_scenario_interpretation_support_manifest(
                repo_root,
                run_id="test_run",
                diagnostic_scenario_ids=(
                    "sc_00_stateless_direct_transform",
                    CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                    "sc_03_math_state_loss",
                    "sc_05_digit_span_n_back_hybrid",
                ),
                stress_scenario_ids=("sc_99_killer_all_scenarios",),
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_id"], "test_run")
            scenario_map = {
                entry["scenario_id"]: entry
                for entry in manifest["scenarios"]
            }

            self.assertEqual(
                scenario_map["sc_03_math_state_loss"]["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "enabled",
                    "ghost": "unsupported",
                },
            )
            self.assertEqual(
                scenario_map["sc_05_digit_span_n_back_hybrid"]["interpretation_variant"],
                "sequence_retention_with_correctness_deferred",
            )
            self.assertEqual(
                scenario_map["sc_05_digit_span_n_back_hybrid"]["layer_support"],
                {
                    "retention": "deferred",
                    "correctness": "deferred",
                    "ghost": "deferred",
                },
            )
            self.assertEqual(
                scenario_map[CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID]["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "deferred",
                    "ghost": "enabled",
                },
            )
            self.assertEqual(
                scenario_map["sc_00_stateless_direct_transform"],
                {
                    "scenario_id": "sc_00_stateless_direct_transform",
                    "scenario_role": "diagnostic",
                    "scenario_type": "stateless_direct_transformation",
                    "interpretation_variant": "none",
                    "layer_support": {
                        "retention": "unsupported",
                        "correctness": "unsupported",
                        "ghost": "unsupported",
                    },
                    "reason": "control scenario with no retention, correctness, or ghost interpretation contract",
                },
            )
            self.assertEqual(
                scenario_map["sc_99_killer_all_scenarios"]["scenario_role"],
                "integration_stress",
            )
            self.assertEqual(
                scenario_map["sc_99_killer_all_scenarios"]["interpretation_variant"],
                "sectioned_composite_interpretation",
            )
            self.assertEqual(
                scenario_map["sc_99_killer_all_scenarios"]["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "enabled",
                    "ghost": "enabled",
                },
            )
            self.assertEqual(
                scenario_map["sc_99_killer_all_scenarios"]["reason"],
                "composite stress scenario with independent section evaluation; sections 1-2 are interpreted now and sections 3-5 remain deferred",
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_sc9_composite_interpretation_generates_sectioned_artifacts(self) -> None:
        repo_root = _workspace_temp_dir("sc9_composite_interpretation")
        try:
            _build_sc9_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id="sc_99_killer_all_scenarios",
                agent_output=_sc9_agent_output(
                    structural_units=(
                        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
                        "D1", "D2", "D3", "D4", "D5", "D6",
                        "C1", "C2", "C3", "C4", "X1",
                    ),
                    math_slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 437",
                    ),
                    retained_sections=("section_2_math_state_loss",),
                    lost_sections=(
                        "section_1_structural_retention",
                        "section_3_n_back_anomaly_trap",
                        "section_4_trail_making",
                        "section_5_move_clock_hands",
                    ),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id="sc_99_killer_all_scenarios",
                agent_output=_sc9_agent_output(
                    structural_units=(
                        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
                        "D1", "D2", "D3", "D4", "D5", "D6",
                        "C1", "C2", "C3", "C4",
                    ),
                    math_slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 437/7",
                    ),
                    retained_sections=(
                        "section_1_structural_retention",
                        "section_2_math_state_loss",
                    ),
                    lost_sections=(
                        "section_3_n_back_anomaly_trap",
                        "section_4_trail_making",
                        "section_5_move_clock_hands",
                    ),
                ),
            )

            retention_layer_path, retention_summary_path = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id="sc_99_killer_all_scenarios",
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )

            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            self.assertEqual(
                retention_layer["interpretation_metadata"],
                {
                    "scenario_id": "sc_99_killer_all_scenarios",
                    "scenario_type": "sectioned_composite_retention",
                    "interpretation_variant": "sectioned_composite_interpretation",
                    "composite": True,
                },
            )
            self.assertEqual(
                retention_layer["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "enabled",
                    "ghost": "enabled",
                },
            )
            self.assertNotIn("unit_groups", retention_layer)
            self.assertEqual(retention_layer["retention_metadata"]["aggregation_policy"], "section_level_only")

            sections = {
                section["section_id"]: section
                for section in retention_layer["sections"]
            }
            self.assertIsInstance(sections["section_1_structural_retention"]["section_result"], dict)
            self.assertIsInstance(sections["section_2_math_state_loss"]["section_result"], dict)
            self.assertIsNone(sections["section_3_n_back_anomaly_trap"]["section_result"])
            self.assertIsNone(sections["section_4_trail_making"]["section_result"])
            self.assertIsNone(sections["section_5_move_clock_hands"]["section_result"])
            self.assertEqual(
                sections["section_1_structural_retention"]["source_scenario_id"],
                "sc_01_structural_retention",
            )
            self.assertEqual(
                sections["section_1_structural_retention"]["include_steps"][0],
                "step_00_initial_and_rules",
            )
            self.assertEqual(
                sections["section_2_math_state_loss"]["source_scenario_id"],
                "sc_03_math_state_loss",
            )

            structural_final = sections["section_1_structural_retention"]["section_result"]["final_summary"]
            math_final = sections["section_2_math_state_loss"]["section_result"]["final_summary"]
            self.assertEqual(structural_final[BASELINE]["retained_count"], 19)
            self.assertEqual(structural_final[BASELINE]["ghost_units"], 1)
            self.assertEqual(
                structural_final[BASELINE]["temporal_diagnostics"],
                {
                    "temporal_ghost_detected": True,
                    "temporal_ghost_count": 1,
                },
            )
            self.assertEqual(math_final[BASELINE]["correct_units"], 9)
            self.assertEqual(math_final[BASELINE]["correctness_percent"], 0.9)
            self.assertEqual(math_final[PR_LIGHT_BRAIN]["correct_units"], 10)
            self.assertNotIn("return_to_origin", math_final[BASELINE])

            top_final = retention_layer["final_summary"]
            self.assertEqual(top_final[BASELINE]["retained_section_ids"], ["section_2_math_state_loss"])
            self.assertEqual(
                top_final[BASELINE]["lost_section_ids"],
                [
                    "section_1_structural_retention",
                    "section_3_n_back_anomaly_trap",
                    "section_4_trail_making",
                    "section_5_move_clock_hands",
                ],
            )
            self.assertEqual(top_final[BASELINE]["total_retained_percent"], 39.0)
            self.assertEqual(top_final[BASELINE]["total_correctness_percent"], 18.0)
            self.assertEqual(top_final[BASELINE]["total_ghost_percent"], 1.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_retained_percent"], 40.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_correctness_percent"], 20.0)
            self.assertEqual(top_final[PR_LIGHT_BRAIN]["total_ghost_percent"], 0.0)
            self.assertEqual(top_final["delta_vs_baseline"]["total_retained_percent_delta"], 1.0)
            self.assertEqual(top_final["delta_vs_baseline"]["total_correctness_percent_delta"], 2.0)
            self.assertEqual(top_final["delta_vs_baseline"]["total_ghost_percent_delta"], -1.0)

            summary_text = retention_summary_path.read_text(encoding="utf-8")
            self.assertIn("## Section Support", summary_text)
            self.assertIn("## Structural Retention", summary_text)
            self.assertIn("## Math State Loss", summary_text)
            self.assertNotIn("## N-Back Anomaly Trap", summary_text)
            self.assertIn("## Composite Final Summary", summary_text)
            self.assertIn("- totals are sums of section contributions only", summary_text)
            self.assertIn("- no raw-unit merging across sections is used", summary_text)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_active_gemini_flash_lite_profile_timeout_matches_current_profile(self) -> None:
        profile = run_benchmarks_module.load_profile("gemini_flash_lite_latest")
        self.assertEqual(profile.timeout_seconds, 299)

    def test_two_mode_comparison_and_summary_report_remain_valid_without_pr_ephemeral(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            None,
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )

        validated = validate_comparison_schema(comparison)
        self.assertIsNone(validated["comparison_metadata"]["pr_ephemeral_mode"])
        self.assertIsNone(validated["summary_scores"]["pr_ephemeral_pr_stability_score"])

        report = build_summary_report(validated, chart_paths=[])
        self.assertNotIn("pr_ephemeral |", report)
        self.assertIn("| baseline |", report)
        self.assertIn("| pr_light_brain |", report)

    def test_run_comparison_summary_includes_effect_summary_from_raw_metrics(self) -> None:
        comparison_summary = build_run_comparison_summary(
            {
                "sc_alpha": build_comparison(
                    compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
                    None,
                    compute_result_from_events(
                        _build_reuse_focused_events(PR_LIGHT_BRAIN),
                        adapter_name=ADAPTER_NAME,
                    ),
                    adapter_name=ADAPTER_NAME,
                ),
                "sc_beta": build_comparison(
                    compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
                    None,
                    compute_result_from_events(
                        _build_reuse_focused_events(PR_LIGHT_BRAIN),
                        adapter_name=ADAPTER_NAME,
                    ),
                    adapter_name=ADAPTER_NAME,
                ),
            },
            run_id="test_run",
            agent_metadata={
                "adapter": ADAPTER_NAME,
                "full_agent_name": "OpenAI Codex",
                "agent_model": "codex-test",
            },
            showcase_scenario_id="sc_alpha",
        )

        effect_summary = comparison_summary["effect_summary"]
        self.assertEqual(
            effect_summary["reuse_improvement"]["source_metric"],
            "reuse_rate",
        )
        self.assertEqual(
            effect_summary["rediscovery_reduction"]["source_metric"],
            "rediscovery_rate",
        )
        self.assertEqual(effect_summary["reuse_improvement"]["baseline"], 0.0)
        self.assertEqual(effect_summary["reuse_improvement"]["pr_light_brain"], 1.0)
        self.assertIsNone(effect_summary["reuse_improvement"]["delta_percent"])
        self.assertEqual(effect_summary["rediscovery_reduction"]["baseline"], 0.0)
        self.assertEqual(effect_summary["rediscovery_reduction"]["pr_light_brain"], 0.0)
        self.assertIsNone(effect_summary["rediscovery_reduction"]["delta_percent"])
        self.assertEqual(
            comparison_summary["stability_scores"]["baseline_average_pr_stability_score"],
            0.12,
        )

    def test_effect_summary_delta_uses_raw_metrics_not_stability_score(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            None,
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )
        mutated = copy.deepcopy(comparison)
        for entry in mutated["metrics_comparison"]:
            if entry["metric_name"] == "reuse_rate":
                entry["values"]["baseline"] = 0.20
                entry["values"]["pr_light_brain"] = 0.50
            if entry["metric_name"] == "rediscovery_rate":
                entry["values"]["baseline"] = 0.40
                entry["values"]["pr_light_brain"] = 0.10
        mutated["summary_scores"]["baseline_pr_stability_score"] = 999.0
        mutated["summary_scores"]["pr_light_brain_pr_stability_score"] = -999.0

        comparison_summary = build_run_comparison_summary(
            {"sc_alpha": mutated},
            run_id="test_run",
            agent_metadata={
                "adapter": ADAPTER_NAME,
                "full_agent_name": "OpenAI Codex",
                "agent_model": "codex-test",
            },
            showcase_scenario_id="sc_alpha",
        )

        effect_summary = comparison_summary["effect_summary"]
        self.assertEqual(effect_summary["reuse_improvement"]["baseline"], 0.20)
        self.assertEqual(effect_summary["reuse_improvement"]["pr_light_brain"], 0.50)
        self.assertEqual(effect_summary["reuse_improvement"]["delta_percent"], 150.0)
        self.assertEqual(effect_summary["rediscovery_reduction"]["baseline"], 0.40)
        self.assertEqual(effect_summary["rediscovery_reduction"]["pr_light_brain"], 0.10)
        self.assertEqual(effect_summary["rediscovery_reduction"]["delta_percent"], 75.0)

    def test_effect_summary_handles_missing_metrics_safely(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            None,
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )
        mutated = copy.deepcopy(comparison)
        mutated["metrics_comparison"] = [
            entry
            for entry in mutated["metrics_comparison"]
            if entry["metric_name"] != "reuse_rate"
        ]

        comparison_summary = build_run_comparison_summary(
            {"sc_alpha": mutated},
            run_id="test_run",
            agent_metadata={
                "adapter": ADAPTER_NAME,
                "full_agent_name": "OpenAI Codex",
                "agent_model": "codex-test",
            },
            showcase_scenario_id="sc_alpha",
        )

        effect_summary = comparison_summary["effect_summary"]
        self.assertEqual(
            effect_summary["reuse_improvement"],
            {
                "source_metric": "reuse_rate",
                "baseline": None,
                "pr_light_brain": None,
                "delta_percent": None,
            },
        )

    def test_run_summary_report_includes_human_facing_effects_without_pr_ephemeral_dependency(self) -> None:
        comparison = build_comparison(
            compute_result_from_events(_build_baseline_events(), adapter_name=ADAPTER_NAME),
            None,
            compute_result_from_events(
                _build_reuse_focused_events(PR_LIGHT_BRAIN),
                adapter_name=ADAPTER_NAME,
            ),
            adapter_name=ADAPTER_NAME,
        )
        mutated = copy.deepcopy(comparison)
        for entry in mutated["metrics_comparison"]:
            if entry["metric_name"] == "reuse_rate":
                entry["values"]["baseline"] = 0.20
                entry["values"]["pr_light_brain"] = 0.50
            if entry["metric_name"] == "rediscovery_rate":
                entry["values"]["baseline"] = 0.40
                entry["values"]["pr_light_brain"] = 0.10

        comparison_summary = build_run_comparison_summary(
            {"sc_alpha": mutated},
            run_id="test_run",
            agent_metadata={
                "adapter": ADAPTER_NAME,
                "full_agent_name": "OpenAI Codex",
                "agent_model": "codex-test",
            },
            showcase_scenario_id="sc_alpha",
        )

        report = build_run_summary_report(
            comparison_summary,
            chart_paths=[],
            warnings=[],
        )

        self.assertIn("## Human-Facing Effects", report)
        self.assertIn("reuse improvement: baseline=0.20, pr_light_brain=0.50, delta=+150.0%", report)
        self.assertIn("rediscovery reduction: baseline=0.40, pr_light_brain=0.10, delta=75.0% lower", report)
        self.assertNotIn("pr_ephemeral", report.split("## Human-Facing Effects", 1)[1].split("## Stability Scores", 1)[0])

    def test_retention_generator_ignores_non_structural_scenarios(self) -> None:
        repo_root = _workspace_temp_dir("retention_ignore")
        try:
            _build_minimal_adapter_repo(repo_root, scenario_id=SCENARIO_ID)
            generated = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=SCENARIO_ID,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            self.assertIsNone(generated)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_generator_creates_strict_two_mode_outputs(self) -> None:
        repo_root = _workspace_temp_dir("retention_outputs")
        try:
            _build_structural_retention_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS[:-2],
                    forward_10=STRUCTURAL_CANONICAL_UNITS[:-2],
                    reverse_5=STRUCTURAL_CANONICAL_UNITS[:-2],
                    final_retained=STRUCTURAL_CANONICAL_UNITS[:-2],
                    final_lost=STRUCTURAL_CANONICAL_UNITS[-2:],
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=tuple(reversed(STRUCTURAL_CANONICAL_UNITS)),
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            retention_layer_path, retention_summary_path = (
                generate_retention_artifacts_for_scenario(
                    repo_root=repo_root,
                    run_id="test_run",
                    scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                    source_modes=(BASELINE, PR_LIGHT_BRAIN),
                    overwrite=True,
                )
            )

            self.assertTrue(retention_layer_path.is_file())
            self.assertTrue(retention_summary_path.is_file())

            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            self.assertEqual(
                retention_layer["interpretation_metadata"],
                {
                    "scenario_id": CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                    "scenario_type": "structural_retention",
                    "interpretation_variant": "structural_retention_with_ghost",
                },
            )
            self.assertEqual(
                retention_layer["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "deferred",
                    "ghost": "enabled",
                },
            )
            self.assertNotIn("effect_summary", retention_layer)
            self.assertEqual(
                retention_layer["retention_metadata"]["retention_type"],
                "structural_retention",
            )
            self.assertEqual(
                retention_layer["retention_metadata"]["counting_policy"],
                "presence_absence_only",
            )
            self.assertIsNone(retention_layer["final_summary"][PR_EPHEMERAL])
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["retained_count"],
                18,
            )
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["lost_count"],
                2,
            )
            self.assertEqual(
                retention_layer["final_summary"][PR_LIGHT_BRAIN]["retained_count"],
                20,
            )
            self.assertEqual(
                retention_layer["final_summary"]["delta_vs_baseline"]["retained_count_delta"],
                2,
            )
            for checkpoint in retention_layer["step_trajectory"]:
                self.assertIsNone(checkpoint[PR_EPHEMERAL])

            self.assertNotIn("correctness_percent", retention_layer["final_summary"])
            self.assertNotIn("retention_correctness_gap", retention_layer["final_summary"])
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["ghost_units"],
                0,
            )
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["ghost_percent"],
                0.0,
            )
            self.assertEqual(
                retention_layer["final_summary"][PR_LIGHT_BRAIN]["ghost_units"],
                0,
            )
            self.assertEqual(
                retention_layer["final_summary"]["delta_vs_baseline"]["ghost_units_delta"],
                0,
            )
            self.assertNotIn("ghost_units", retention_layer["step_trajectory"][0][BASELINE])
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["temporal_diagnostics"],
                {
                    "temporal_ghost_detected": False,
                    "temporal_ghost_count": 0,
                },
            )
            self.assertEqual(
                retention_layer["final_summary"][BASELINE]["trajectory_diagnostics"],
                {
                    "enabled": True,
                    "trajectory_score": 80.0,
                    "checkpoint_count": 5,
                    "checkpoint_weight": 20.0,
                    "deviation_segments": 1,
                    "first_deviation_step": 1,
                    "recovery_signal": {
                        "recovered_after_deviation": False,
                        "deviation_start_step": 1,
                        "recovery_step": None,
                        "recovery_distance": None,
                    },
                    "erosion_curve": [
                        {
                            "step_index": 0,
                            "checkpoint_id": "checkpoint_00_initial",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                        {
                            "step_index": 1,
                            "checkpoint_id": "checkpoint_01",
                            "deviation_triggered": True,
                            "deviation_active": True,
                            "cumulative_penalty": 20.0,
                            "trajectory_score": 80.0,
                        },
                        {
                            "step_index": 2,
                            "checkpoint_id": "checkpoint_02",
                            "deviation_triggered": False,
                            "deviation_active": True,
                            "cumulative_penalty": 20.0,
                            "trajectory_score": 80.0,
                        },
                        {
                            "step_index": 3,
                            "checkpoint_id": "checkpoint_03",
                            "deviation_triggered": False,
                            "deviation_active": True,
                            "cumulative_penalty": 20.0,
                            "trajectory_score": 80.0,
                        },
                        {
                            "step_index": 4,
                            "checkpoint_id": "checkpoint_99_final",
                            "deviation_triggered": False,
                            "deviation_active": True,
                            "cumulative_penalty": 20.0,
                            "trajectory_score": 80.0,
                        },
                    ],
                },
            )
            self.assertEqual(
                retention_layer["final_summary"][PR_LIGHT_BRAIN]["trajectory_diagnostics"],
                {
                    "enabled": True,
                    "trajectory_score": 100.0,
                    "checkpoint_count": 5,
                    "checkpoint_weight": 20.0,
                    "deviation_segments": 0,
                    "first_deviation_step": None,
                    "recovery_signal": {
                        "recovered_after_deviation": False,
                        "deviation_start_step": None,
                        "recovery_step": None,
                        "recovery_distance": None,
                    },
                    "erosion_curve": [
                        {
                            "step_index": 0,
                            "checkpoint_id": "checkpoint_00_initial",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                        {
                            "step_index": 1,
                            "checkpoint_id": "checkpoint_01",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                        {
                            "step_index": 2,
                            "checkpoint_id": "checkpoint_02",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                        {
                            "step_index": 3,
                            "checkpoint_id": "checkpoint_03",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                        {
                            "step_index": 4,
                            "checkpoint_id": "checkpoint_99_final",
                            "deviation_triggered": False,
                            "deviation_active": False,
                            "cumulative_penalty": 0.0,
                            "trajectory_score": 100.0,
                        },
                    ],
                },
            )
            self.assertNotIn(
                "trajectory_diagnostics",
                retention_layer["final_summary"]["delta_vs_baseline"],
            )
            self.assertNotIn(
                "return_to_origin",
                retention_layer["final_summary"][BASELINE],
            )

            summary_text = retention_summary_path.read_text(encoding="utf-8")
            self.assertIn("## Layer Support", summary_text)
            self.assertIn("- retention: enabled", summary_text)
            self.assertIn("- correctness: deferred", summary_text)
            self.assertIn("- ghost: enabled", summary_text)
            self.assertIn("counting_policy: presence/absence only", summary_text)
            self.assertIn("## Ghost Artifacts", summary_text)
            self.assertIn("- structural ghost is final-state only", summary_text)
            self.assertIn("## Temporal Diagnostics", summary_text)
            self.assertIn("## Trajectory Diagnostics", summary_text)
            self.assertIn("- trajectory diagnostics are diagnostic only", summary_text)
            self.assertIn("- baseline: score=80.00 checkpoint_count=5 deviation_segments=1 first_deviation_step=1 recovered=False recovery_step=None recovery_distance=None", summary_text)
            self.assertNotIn("## Optional Correctness Layer", summary_text)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_trajectory_penalizes_discrete_segments_and_resets_after_recovery(self) -> None:
        repo_root = _workspace_temp_dir("retention_trajectory_segments")
        try:
            _build_structural_retention_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS[:-1],
                    forward_10=STRUCTURAL_CANONICAL_UNITS[:-1],
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=STRUCTURAL_CANONICAL_UNITS,
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            retention_layer_path, _ = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            diagnostics = retention_layer["final_summary"][BASELINE]["trajectory_diagnostics"]

            self.assertEqual(diagnostics["trajectory_score"], 80.0)
            self.assertEqual(diagnostics["deviation_segments"], 1)
            self.assertEqual(diagnostics["first_deviation_step"], 1)
            self.assertEqual(
                diagnostics["recovery_signal"],
                {
                    "recovered_after_deviation": True,
                    "deviation_start_step": 1,
                    "recovery_step": 3,
                    "recovery_distance": 2,
                },
            )
            self.assertEqual(
                diagnostics["erosion_curve"][1:4],
                [
                    {
                        "step_index": 1,
                        "checkpoint_id": "checkpoint_01",
                        "deviation_triggered": True,
                        "deviation_active": True,
                        "cumulative_penalty": 20.0,
                        "trajectory_score": 80.0,
                    },
                    {
                        "step_index": 2,
                        "checkpoint_id": "checkpoint_02",
                        "deviation_triggered": False,
                        "deviation_active": True,
                        "cumulative_penalty": 20.0,
                        "trajectory_score": 80.0,
                    },
                    {
                        "step_index": 3,
                        "checkpoint_id": "checkpoint_03",
                        "deviation_triggered": False,
                        "deviation_active": False,
                        "cumulative_penalty": 20.0,
                        "trajectory_score": 80.0,
                    },
                ],
            )
            self.assertEqual(retention_layer["final_summary"][BASELINE]["retained_count"], 20)
            self.assertEqual(retention_layer["final_summary"][BASELINE]["retention_percent"], 1.0)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_trajectory_requires_explicit_ready_metadata(self) -> None:
        repo_root = _workspace_temp_dir("retention_trajectory_readiness_gate")
        try:
            _build_structural_retention_repo(repo_root)
            metadata_path = (
                repo_root
                / "benchmarks"
                / "scenarios"
                / f"{CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID}.metadata.json"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["interpretation_support"]["trajectory_readiness"] = "deferred"
            metadata["trajectory_contract"] = {
                "enabled": True,
                "mode": "checkpoint_expected_values",
                "checkpoint_expected_values": [
                    {
                        "checkpoint_id": "checkpoint_00_initial",
                        "expected_slot_values": {
                            "FIELD_NAME": "value",
                        },
                    }
                ],
            }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS[:-1],
                    forward_10=STRUCTURAL_CANONICAL_UNITS[:-1],
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=STRUCTURAL_CANONICAL_UNITS,
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            retention_layer_path, retention_summary_path = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))

            self.assertNotIn("trajectory_diagnostics", retention_layer["final_summary"][BASELINE])
            self.assertNotIn("trajectory_diagnostics", retention_layer["final_summary"][PR_LIGHT_BRAIN])
            self.assertNotIn(
                "## Trajectory Diagnostics",
                retention_summary_path.read_text(encoding="utf-8"),
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_generator_requires_exact_headings(self) -> None:
        repo_root = _workspace_temp_dir("retention_strict")
        try:
            _build_structural_retention_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=(
                    "CHECKPOINT ONE - INVENTORY\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 5 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 10 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 15 - REVERSE\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 20 - FINAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "FINAL RETAINED UNITS\n"
                    + ", ".join(STRUCTURAL_CANONICAL_UNITS) + "\n\n"
                    "FINAL LOST UNITS\n"
                    "NONE"
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=STRUCTURAL_CANONICAL_UNITS,
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            with self.assertRaisesRegex(ValueError, "required exact section heading missing"):
                generate_retention_artifacts_for_scenario(
                    repo_root=repo_root,
                    run_id="test_run",
                    scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                    source_modes=(BASELINE, PR_LIGHT_BRAIN),
                    overwrite=True,
                )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_ghost_units_are_counted_separately_and_deduplicated(self) -> None:
        repo_root = _workspace_temp_dir("retention_ghosts")
        try:
            _build_structural_retention_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=(
                    "CHECKPOINT 0 - INITIAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, X1, X1\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 5 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, X2\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 10 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, X3, X3\n\n"
                    "CHECKPOINT 15 - REVERSE\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3\n\n"
                    "CHECKPOINT 20 - FINAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, X4\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3\n\n"
                    "FINAL RETAINED UNITS\n"
                    "F1, F2, F3, F4, F5, F6, F7, F8, F9, D1, D2, D3, D4, D5, D6, C1, C2, C3, X4\n\n"
                    "FINAL LOST UNITS\n"
                    "F10, C4, X4, X5, X5"
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=STRUCTURAL_CANONICAL_UNITS,
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            retention_layer_path, retention_summary_path = (
                generate_retention_artifacts_for_scenario(
                    repo_root=repo_root,
                    run_id="test_run",
                    scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                    source_modes=(BASELINE, PR_LIGHT_BRAIN),
                    overwrite=True,
                )
            )

            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            baseline_final = retention_layer["final_summary"][BASELINE]
            delta = retention_layer["final_summary"]["delta_vs_baseline"]

            self.assertNotIn("ghost_unit_ids", retention_layer["step_trajectory"][0][BASELINE])
            self.assertEqual(
                baseline_final["temporal_diagnostics"],
                {
                    "temporal_ghost_detected": True,
                    "temporal_ghost_count": 2,
                },
            )
            self.assertEqual(baseline_final["retained_count"], 18)
            self.assertEqual(baseline_final["lost_count"], 2)
            self.assertEqual(baseline_final["ghost_unit_ids"], ["X4", "X5"])
            self.assertEqual(baseline_final["ghost_units"], 2)
            self.assertEqual(baseline_final["ghost_percent"], 2 / 20)
            self.assertEqual(delta["ghost_units_delta"], -2)
            self.assertEqual(delta["ghost_percent_delta"], -(2 / 20))

            summary_text = retention_summary_path.read_text(encoding="utf-8")
            self.assertIn("- ghost is separate from retained/lost accounting", summary_text)
            self.assertIn("- baseline: ghost_units=2 ghost_percent=0.10", summary_text)
            self.assertIn("## Temporal Diagnostics", summary_text)
            self.assertIn("- baseline: detected=True count=2", summary_text)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_structural_retention_ghost_extraction_uses_only_validated_sections(self) -> None:
        repo_root = _workspace_temp_dir("retention_ghost_sections")
        try:
            _build_structural_retention_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=(
                    "PREAMBLE X9 SHOULD NOT COUNT\n\n"
                    "CHECKPOINT 0 - INITIAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 5 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 10 - FORWARD\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 15 - REVERSE\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "CHECKPOINT 20 - FINAL\n"
                    "FACTS: F1, F2, F3, F4, F5, F6, F7, F8, F9, F10\n"
                    "DEPENDENCIES: D1, D2, D3, D4, D5, D6\n"
                    "CONSTRAINTS: C1, C2, C3, C4\n\n"
                    "FINAL RETAINED UNITS\n"
                    + ", ".join(STRUCTURAL_CANONICAL_UNITS) + "\n\n"
                    "FINAL LOST UNITS\n"
                    "NONE"
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                agent_output=_retention_agent_output(
                    initial=STRUCTURAL_CANONICAL_UNITS,
                    forward_5=STRUCTURAL_CANONICAL_UNITS,
                    forward_10=STRUCTURAL_CANONICAL_UNITS,
                    reverse_5=STRUCTURAL_CANONICAL_UNITS,
                    final_retained=STRUCTURAL_CANONICAL_UNITS,
                    final_lost=(),
                ),
            )

            retention_layer_path, _ = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            baseline_final = retention_layer["final_summary"][BASELINE]

            self.assertEqual(baseline_final["ghost_units"], 0)
            self.assertEqual(baseline_final["ghost_unit_ids"], [])
            self.assertEqual(
                baseline_final["temporal_diagnostics"],
                {
                    "temporal_ghost_detected": False,
                    "temporal_ghost_count": 0,
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_math_state_loss_correctness_layer_remains_independent_from_retention(self) -> None:
        repo_root = _workspace_temp_dir("math_correctness")
        try:
            _build_math_state_loss_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                agent_output=_math_state_loss_agent_output(
                    slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 62.42857142857143",
                    ),
                    retained_slots=MATH_STATE_LOSS_CANONICAL_SLOTS,
                    lost_slots=(),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                agent_output=_math_state_loss_agent_output(
                    slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 437/7",
                    ),
                    retained_slots=MATH_STATE_LOSS_CANONICAL_SLOTS,
                    lost_slots=(),
                ),
            )

            retention_layer_path, retention_summary_path = (
                generate_retention_artifacts_for_scenario(
                    repo_root=repo_root,
                    run_id="test_run",
                    scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                    source_modes=(BASELINE, PR_LIGHT_BRAIN),
                    overwrite=True,
                )
            )

            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            baseline_final = retention_layer["final_summary"][BASELINE]
            brain_final = retention_layer["final_summary"][PR_LIGHT_BRAIN]
            delta = retention_layer["final_summary"]["delta_vs_baseline"]

            self.assertEqual(
                retention_layer["interpretation_metadata"],
                {
                    "scenario_id": MATH_STATE_LOSS_SCENARIO_ID,
                    "scenario_type": "state_loss_recovery",
                    "interpretation_variant": "math_retention_with_correctness",
                },
            )
            self.assertEqual(
                retention_layer["layer_support"],
                {
                    "retention": "enabled",
                    "correctness": "enabled",
                    "ghost": "unsupported",
                },
            )
            self.assertEqual(
                retention_layer["retention_metadata"]["retention_type"],
                "math_retention_with_correctness",
            )
            self.assertEqual(
                baseline_final["retention_percent"],
                1.0,
            )
            self.assertEqual(
                baseline_final["correctness_percent"],
                0.9,
            )
            self.assertEqual(
                baseline_final["retention_correctness_gap"],
                0.1,
            )
            self.assertEqual(brain_final["retention_percent"], 1.0)
            self.assertEqual(brain_final["correctness_percent"], 1.0)
            self.assertEqual(brain_final["retention_correctness_gap"], 0.0)
            self.assertEqual(delta["retention_percent_delta"], 0.0)
            self.assertEqual(delta["correctness_percent_delta"], 0.1)
            self.assertEqual(delta["retention_correctness_gap_delta"], -0.1)
            self.assertNotIn("ghost_units", json.dumps(retention_layer, sort_keys=True))
            self.assertNotIn("ghost_percent", json.dumps(retention_layer, sort_keys=True))
            self.assertEqual(
                baseline_final["return_to_origin"],
                {
                    "enabled": True,
                    "matches": True,
                },
            )
            self.assertEqual(
                brain_final["return_to_origin"],
                {
                    "enabled": True,
                    "matches": True,
                },
            )
            self.assertEqual(
                baseline_final["temporal_diagnostics"],
                {
                    "temporal_ghost_detected": False,
                    "temporal_ghost_count": 0,
                },
            )
            self.assertNotIn("trajectory_diagnostics", baseline_final)

            summary_text = retention_summary_path.read_text(encoding="utf-8")
            self.assertIn("## Layer Support", summary_text)
            self.assertIn("- retention: enabled", summary_text)
            self.assertIn("- correctness: enabled", summary_text)
            self.assertIn("- ghost: unsupported", summary_text)
            self.assertIn("## Optional Correctness Layer", summary_text)
            self.assertNotIn("## Ghost Artifacts", summary_text)
            self.assertIn("## Return To Origin", summary_text)
            self.assertIn("## Temporal Diagnostics", summary_text)
            self.assertNotIn("## Trajectory Diagnostics", summary_text)
            self.assertIn(
                "- baseline: retention_percent=1.00 correctness_percent=0.90 gap=0.10",
                summary_text,
            )
            self.assertIn(
                "- pr_light_brain: retention_percent=1.00 correctness_percent=1.00 gap=0.00",
                summary_text,
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_math_state_loss_correctness_uses_exact_fraction_truth(self) -> None:
        repo_root = _workspace_temp_dir("math_exact_truth")
        try:
            _build_math_state_loss_repo(repo_root)
            _write_retention_trace_log(
                repo_root,
                mode=BASELINE,
                scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                agent_output=_math_state_loss_agent_output(
                    slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 437/7",
                    ),
                    retained_slots=MATH_STATE_LOSS_CANONICAL_SLOTS,
                    lost_slots=(),
                ),
            )
            _write_retention_trace_log(
                repo_root,
                mode=PR_LIGHT_BRAIN,
                scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                agent_output=_math_state_loss_agent_output(
                    slot_lines=(
                        "PRODUCT_1: 1081",
                        "PRODUCT_2: 1102",
                        "COMBINED_SUM: 2183",
                        "AFTER_SUBTRACTION: 1818",
                        "AFTER_DIVISION: 606",
                        "AFTER_ADDITION: 657",
                        "AFTER_MULTIPLICATION: 1314",
                        "AFTER_REDUCTION: 438",
                        "FINAL_NUMERATOR: 437",
                        "FINAL_RESULT: 62.42857142857143",
                    ),
                    retained_slots=MATH_STATE_LOSS_CANONICAL_SLOTS,
                    lost_slots=(),
                ),
            )

            retention_layer_path, _ = generate_retention_artifacts_for_scenario(
                repo_root=repo_root,
                run_id="test_run",
                scenario_id=MATH_STATE_LOSS_SCENARIO_ID,
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                overwrite=True,
            )
            retention_layer = json.loads(retention_layer_path.read_text(encoding="utf-8"))
            baseline_final = retention_layer["final_summary"][BASELINE]
            brain_final = retention_layer["final_summary"][PR_LIGHT_BRAIN]

            self.assertEqual(baseline_final["correct_units"], 10)
            self.assertEqual(baseline_final["incorrect_units"], 0)
            self.assertEqual(brain_final["correct_units"], 9)
            self.assertEqual(brain_final["incorrect_units"], 1)
            self.assertEqual(brain_final["correctness_percent"], 0.9)
            self.assertTrue(baseline_final["return_to_origin"]["matches"])
            self.assertTrue(brain_final["return_to_origin"]["matches"])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_runner_invokes_retention_generation_after_post_processing(self) -> None:
        sequence: list[str] = []
        fake_profile = SimpleNamespace(
            name="test_profile",
            backend="gemini",
            model="gemini-flash-lite-latest",
            scenario_subset=(STRUCTURAL_RETENTION_SCENARIO_ID,),
            diagnostic_modes=SimpleNamespace(
                pr_ephemeral=False,
                post_run_artifact_harvest=False,
            ),
            brain_mode="accumulative",
            brain_in=SimpleNamespace(type="runtime"),
            brain_out=SimpleNamespace(mode="snapshot"),
            inter_scenario_delay_seconds=1,
            showcase=STRUCTURAL_RETENTION_SCENARIO_ID,
            mode_to_key_mapping="strict",
        )
        fake_backend = SimpleNamespace(
            backend="gemini",
            adapter_name="gemini",
            get_benchmark_agent_metadata=lambda **_: {
                "adapter": "gemini",
                "full_agent_name": "Gemini",
                "agent_model": "gemini-flash-lite-latest",
            },
        )

        with patch.object(
            run_benchmarks_module,
            "parse_args",
            return_value=SimpleNamespace(
                profile="test_profile",
                backend=None,
                artifact_generator_mode=None,
                artifact_filter_mode=None,
                working_context_format=None,
            ),
        ), patch.object(
            run_benchmarks_module,
            "load_profile",
            return_value=fake_profile,
        ), patch.object(
            run_benchmarks_module,
            "resolve_backend",
            return_value=fake_backend,
        ), patch.object(
            run_benchmarks_module,
            "run_preflight",
            side_effect=lambda *args, **kwargs: sequence.append("preflight"),
        ), patch.object(
            run_benchmarks_module,
            "apply_pre_run_brain_lifecycle",
            side_effect=lambda *args, **kwargs: sequence.append("pre_run_lifecycle"),
        ), patch.object(
            run_benchmarks_module,
            "clean_temporary_benchmark_results",
            side_effect=lambda *args, **kwargs: sequence.append("clean_results"),
        ), patch.object(
            run_benchmarks_module,
            "run_all",
            side_effect=lambda *args, **kwargs: sequence.append("run_all")
            or run_benchmarks_module.RunExecutionState(quota_stop_reason=None, total_429_count=0),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_layer_manifest",
            side_effect=lambda *args, **kwargs: Path("scenario_layers.json"),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_interpretation_support_manifest",
            side_effect=lambda *args, **kwargs: Path("scenario_interpretation_support.json"),
        ), patch.object(
            run_benchmarks_module,
            "run_post_processing",
            side_effect=lambda *args, **kwargs: sequence.append("post_processing"),
        ), patch.object(
            run_benchmarks_module,
            "generate_retention_artifacts_for_run",
            side_effect=lambda *args, **kwargs: sequence.append("retention_generation") or [],
        ), patch.object(
            run_benchmarks_module,
            "apply_post_run_brain_lifecycle",
            side_effect=lambda *args, **kwargs: sequence.append("post_run_lifecycle"),
        ), patch.object(
            run_benchmarks_module,
            "run_post_run_artifact_harvest",
            side_effect=lambda *args, **kwargs: sequence.append("post_run_harvest")
            or Path(HARVEST_REPORT_FILENAME),
        ), patch.object(
            run_benchmarks_module,
            "build_run_id",
            return_value="test_run",
        ), patch("builtins.print"):
            run_benchmarks_module.main()

        self.assertLess(sequence.index("run_all"), sequence.index("post_processing"))
        self.assertLess(sequence.index("post_processing"), sequence.index("retention_generation"))
        self.assertLess(sequence.index("retention_generation"), sequence.index("post_run_lifecycle"))

    def test_benchmark_prompt_instructions_require_contract_artifact_types(self) -> None:
        contract_text = (
            Path("reasoning_brain_storage") / "artifact_extraction_contract.md"
        ).read_text(encoding="utf-8")
        instructions = benchmark_prompt_utils.build_benchmark_instructions(mode=PR_LIGHT_BRAIN)
        joined = "\n".join(instructions)

        for artifact_type in ("TaskCard", "DecisionCard", "ConstraintCard", "ProcedureCard"):
            self.assertIn(f"### {artifact_type}", contract_text)
            self.assertIn(artifact_type, joined)
        self.assertIn("TaskCard, DecisionCard, ConstraintCard, ProcedureCard", joined)
        self.assertIn('For each type, output exactly one value: "NONE" or {"id":"...", "summary":"..."}.', joined)
        self.assertIn("Default for every artifact type is NONE.", joined)
        self.assertIn("At most one artifact per type is allowed.", joined)
        self.assertIn("Do not use aliases such as artifact_id or lower-case card names.", joined)
        self.assertIn("Do not output reasoning traces", joined)

    def test_benchmark_prompt_default_artifact_generator_mode_is_legacy(self) -> None:
        default_instructions = benchmark_prompt_utils.build_benchmark_instructions(
            mode=PR_LIGHT_BRAIN
        )
        explicit_legacy_instructions = benchmark_prompt_utils.build_benchmark_instructions(
            mode=PR_LIGHT_BRAIN,
            artifact_generator_mode=benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_LEGACY,
        )

        self.assertEqual(default_instructions, explicit_legacy_instructions)
        self.assertNotIn(
            "Default Artifact Suggestion output is NONE.",
            "\n".join(default_instructions),
        )

    def test_shadow_artifact_generator_mode_uses_legacy_active_prompt(self) -> None:
        legacy_instructions = benchmark_prompt_utils.build_benchmark_instructions(
            mode=PR_LIGHT_BRAIN,
            artifact_generator_mode=benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_LEGACY,
        )
        shadow_instructions = benchmark_prompt_utils.build_benchmark_instructions(
            mode=PR_LIGHT_BRAIN,
            artifact_generator_mode=benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_SHADOW,
        )

        self.assertEqual(shadow_instructions, legacy_instructions)

    def test_constrained_artifact_generator_prompt_uses_current_benchmark_schema(self) -> None:
        instructions = benchmark_prompt_utils.build_benchmark_instructions(
            mode=PR_LIGHT_BRAIN,
            artifact_generator_mode=benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_CONSTRAINED,
        )
        joined = "\n".join(instructions)

        self.assertIn("Default Artifact Suggestion output for every artifact type is NONE.", joined)
        self.assertIn("TaskCard", joined)
        self.assertIn("DecisionCard", joined)
        self.assertIn("ConstraintCard", joined)
        self.assertIn("ProcedureCard", joined)
        self.assertIn("durable approach decision", joined)
        self.assertIn("explicit checkable rule", joined)
        self.assertIn("reusable deterministic workflow", joined)
        self.assertIn("durable, structural, non-temporary, non-redundant, independent", joined)
        self.assertIn("temporary calculations", joined)
        self.assertIn("intermediate states", joined)
        self.assertIn("step-local notes", joined)
        self.assertIn("restatements of the current answer", joined)
        self.assertIn("duplicate provided context", joined)
        self.assertIn("Do not output reasoning traces", joined)
        self.assertIn('"TaskCard":"NONE"', joined)
        self.assertIn('"DecisionCard":{"id":"...","summary":"..."}', joined)
        self.assertIn("If confidence is not high for a type, output NONE for that type.", joined)

    def test_artifact_generator_mode_rejects_unknown_values(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_prompt_utils.build_benchmark_instructions(
                mode=PR_LIGHT_BRAIN,
                artifact_generator_mode="experimental",
            )

    def test_adapter_prompt_can_opt_into_constrained_artifact_generator_mode(self) -> None:
        repo_root = _workspace_temp_dir("constrained_prompt_adapter")
        try:
            scenario_id = "sc_constrained_prompt_adapter"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario = gemini_adapter_module.load_scenario(paths, scenario_id)

            prompt = gemini_adapter_module.build_prompt(
                paths,
                scenario,
                mode=PR_EPHEMERAL,
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                task_text="Exercise constrained artifact prompt mode.",
                artifact_generator_mode=(
                    benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_CONSTRAINED
                ),
            )

            self.assertIn(
                "Default Artifact Suggestion output for every artifact type is NONE.",
                prompt,
            )
            self.assertIn("durable, structural, non-temporary, non-redundant", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_working_context_format_defaults_to_reference_only(self) -> None:
        repo_root = _workspace_temp_dir("wc_default")
        try:
            scenario_id = "sc_08_reference_default"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)
            paths = BenchmarkPaths(repo_root=repo_root)
            scenario = gemini_adapter_module.load_scenario(paths, scenario_id)
            context = {
                "active_task": None,
                "constraints": ["sc_08_con_time_mod_720"],
                "decisions": ["sc_08_cyclic_state_handling_rule"],
                "open_issues": [],
            }

            prompt = benchmark_prompt_utils.build_benchmark_prompt(
                scenario,
                context,
                mode=PR_LIGHT_BRAIN,
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                task_text="Exercise default context format.",
            )

            self.assertIn("Decisions:\n- sc_08_cyclic_state_handling_rule", prompt)
            self.assertIn("Constraints:\n- sc_08_con_time_mod_720", prompt)
            self.assertNotIn("Relevant Decisions:", prompt)
            self.assertNotIn("Relevant Constraints:", prompt)
            self.assertNotIn("Established protocol for cyclic clock state updates", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_relevant_summaries_selects_scenario_and_global_decisions(self) -> None:
        repo_root = _workspace_temp_dir("wc_relevant")
        try:
            brain_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            context = {
                "active_task": None,
                "constraints": [],
                "decisions": [
                    "benchmark_benchmark_rule",
                    "common_shared_rule",
                    "global_all_scenarios_rule",
                    "sc_04_chain_collapse_final",
                    "sc_08_cyclic_state_handling_rule",
                    "sc_08_move_clock_hands_completion",
                    "sc_10_hanoi_like_final",
                    "temporal_rule_propagation_logic_v1",
                ],
                "open_issues": [],
            }
            _create_minimal_brain_root(brain_root, context)
            _write_decision_artifact(
                brain_root,
                "benchmark_benchmark_rule",
                "Benchmark-wide rule summary.",
                body="FULL BENCHMARK BODY MUST NOT APPEAR",
            )
            _write_decision_artifact(
                brain_root,
                "common_shared_rule",
                "Common shared rule summary.",
            )
            _write_decision_artifact(
                brain_root,
                "global_all_scenarios_rule",
                "Global rule summary.",
            )
            _write_decision_artifact(
                brain_root,
                "sc_08_cyclic_state_handling_rule",
                "Established protocol for cyclic clock state updates.",
                body="FULL CLOCK BODY MUST NOT APPEAR",
            )
            _write_decision_artifact(
                brain_root,
                "sc_08_move_clock_hands_completion",
                "Finalized cyclic spatial state tracking.",
            )

            enriched = benchmark_prompt_utils.build_relevant_summary_context(
                context,
                brain_root=brain_root,
                scenario_id="sc_08_move_clock_hands",
            )
            selected_ids = [
                decision["id"]
                for decision in enriched["relevant_decisions"]
            ]

            self.assertEqual(
                selected_ids,
                [
                    "benchmark_benchmark_rule",
                    "common_shared_rule",
                    "global_all_scenarios_rule",
                    "sc_08_cyclic_state_handling_rule",
                    "sc_08_move_clock_hands_completion",
                ],
            )

            prompt = benchmark_prompt_utils.build_runtime_prompt_block(
                enriched,
                task_text="Use relevant summaries.",
                mode=PR_LIGHT_BRAIN,
                scenario_id="sc_08_move_clock_hands",
                working_context_format=(
                    benchmark_prompt_utils.WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES
                ),
            )

            self.assertIn("Relevant Decisions:", prompt)
            self.assertIn(
                "- sc_08_cyclic_state_handling_rule: Established protocol for cyclic clock state updates.",
                prompt,
            )
            self.assertIn("- global_all_scenarios_rule: Global rule summary.", prompt)
            self.assertNotIn("sc_04_chain_collapse_final", prompt)
            self.assertNotIn("sc_10_hanoi_like_final", prompt)
            self.assertNotIn("temporal_rule_propagation_logic_v1", prompt)
            self.assertNotIn("FULL CLOCK BODY MUST NOT APPEAR", prompt)
            self.assertNotIn("FULL BENCHMARK BODY MUST NOT APPEAR", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_relevant_summaries_renders_all_contract_artifact_groups(self) -> None:
        repo_root = _workspace_temp_dir("wc_all_types")
        try:
            brain_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            context = {
                "active_task": None,
                "tasks": ["sc_08_clarify_goal"],
                "constraints": ["sc_08_never_skip_boundary"],
                "decisions": ["sc_08_cyclic_state_handling_rule"],
                "procedures": ["sc_08_apply_boundary_workflow"],
                "open_issues": [],
            }
            _create_minimal_brain_root(brain_root, context)
            artifacts = (
                ("tasks", "sc_08_clarify_goal", "task", "Clarify goal summary."),
                ("constraints", "sc_08_never_skip_boundary", "constraint", "Never skip boundary summary."),
                ("decisions", "sc_08_cyclic_state_handling_rule", "decision", "Decision summary."),
                ("procedures", "sc_08_apply_boundary_workflow", "procedure", "Procedure summary."),
            )
            for folder, artifact_id, artifact_type, summary in artifacts:
                (brain_root / "brain" / folder / f"{artifact_id}.json").write_text(
                    json.dumps(
                        {
                            "id": artifact_id,
                            "type": artifact_type,
                            "summary": summary,
                            "body": "FULL BODY MUST NOT APPEAR",
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            enriched = benchmark_prompt_utils.build_relevant_summary_context(
                context,
                brain_root=brain_root,
                scenario_id="sc_08_move_clock_hands",
            )
            prompt = benchmark_prompt_utils.build_runtime_prompt_block(
                enriched,
                task_text="Use relevant summaries.",
                mode=PR_LIGHT_BRAIN,
                scenario_id="sc_08_move_clock_hands",
                working_context_format=(
                    benchmark_prompt_utils.WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES
                ),
            )

            self.assertIn("Relevant Task Cards:\n- sc_08_clarify_goal: Clarify goal summary.", prompt)
            self.assertIn("Relevant Decisions:\n- sc_08_cyclic_state_handling_rule: Decision summary.", prompt)
            self.assertIn("Relevant Constraints:\n- sc_08_never_skip_boundary: Never skip boundary summary.", prompt)
            self.assertIn("Relevant Procedures:\n- sc_08_apply_boundary_workflow: Procedure summary.", prompt)
            self.assertNotIn("\nTasks:\n", prompt)
            self.assertNotIn("\nDecisions:\n", prompt)
            self.assertNotIn("\nConstraints:\n", prompt)
            self.assertNotIn("\nProcedures:\n", prompt)
            self.assertEqual(prompt.count("sc_08_never_skip_boundary"), 1)
            self.assertNotIn("FULL BODY MUST NOT APPEAR", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_relevant_summaries_render_none_when_no_relevant_decisions(self) -> None:
        repo_root = _workspace_temp_dir("wc_none")
        try:
            brain_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            context = {
                "active_task": None,
                "constraints": [],
                "decisions": ["sc_04_chain_collapse_final"],
                "open_issues": [],
            }
            _create_minimal_brain_root(brain_root, context)

            enriched = benchmark_prompt_utils.build_relevant_summary_context(
                context,
                brain_root=brain_root,
                scenario_id="sc_08_move_clock_hands",
            )
            prompt = benchmark_prompt_utils.build_runtime_prompt_block(
                enriched,
                task_text="Use relevant summaries.",
                mode=PR_LIGHT_BRAIN,
                scenario_id="sc_08_move_clock_hands",
                working_context_format=(
                    benchmark_prompt_utils.WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES
                ),
            )

            self.assertIn("Relevant Task Cards:\n- none", prompt)
            self.assertIn("Relevant Decisions:\n- none", prompt)
            self.assertIn("Relevant Constraints:\n- none", prompt)
            self.assertIn("Relevant Procedures:\n- none", prompt)
            self.assertNotIn("\nDecisions:\n", prompt)
            self.assertNotIn("\nConstraints:\n", prompt)
            self.assertNotIn("sc_04_chain_collapse_final", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_pr_light_brain_prompt_can_opt_into_relevant_summaries(self) -> None:
        repo_root = _workspace_temp_dir("wc_optin")
        try:
            scenario_id = "sc_08_prompt_probe"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)
            paths = BenchmarkPaths(repo_root=repo_root)
            brain_root = paths.runtime_brain_root
            context = {
                "active_task": None,
                "constraints": [],
                "decisions": [
                    "sc_04_chain_collapse_final",
                    "sc_08_cyclic_state_handling_rule",
                ],
                "open_issues": [],
            }
            (brain_root / "views" / "working_context.json").write_text(
                json.dumps(context, indent=2) + "\n",
                encoding="utf-8",
            )
            _write_decision_artifact(
                brain_root,
                "sc_08_cyclic_state_handling_rule",
                "Established protocol for cyclic clock state updates.",
                body="FULL PROMPT BODY MUST NOT APPEAR",
            )
            scenario = gemini_adapter_module.load_scenario(paths, scenario_id)

            prompt = gemini_adapter_module.build_prompt(
                paths,
                scenario,
                mode=PR_LIGHT_BRAIN,
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                task_text="Exercise relevant summary context mode.",
                working_context_format=(
                    benchmark_prompt_utils.WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES
                ),
            )

            self.assertIn("Relevant Decisions:", prompt)
            self.assertIn(
                "- sc_08_cyclic_state_handling_rule: Established protocol for cyclic clock state updates.",
                prompt,
            )
            self.assertNotIn("\nDecisions:\n", prompt)
            self.assertNotIn("\nConstraints:\n", prompt)
            self.assertNotIn("sc_04_chain_collapse_final", prompt)
            self.assertNotIn("FULL PROMPT BODY MUST NOT APPEAR", prompt)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_artifact_generator_shadow_telemetry_disabled_by_default(self) -> None:
        repo_root = _workspace_temp_dir("shadow_disabled_default")
        try:
            scenario_id = "sc_shadow_disabled_default"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_EPHEMERAL,
                task_text="Exercise default shadow telemetry behavior.",
                agent_output="Final Answer: done\nArtifact Suggestion: NONE",
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            payload = _extract_task_completed_payload(read_events(run_result["event_log_path"]))
            self.assertNotIn("artifact_generation_shadow", payload)
            self.assertNotIn("artifact_filter_shadow", payload)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_openai_filter_shadow_accepts_valid_benchmark_artifact_without_changing_artifact_event(self) -> None:
        repo_root = _workspace_temp_dir("openai_filter_shadow_accept")
        try:
            scenario_id = "sc_openai_filter_shadow_accept"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = run_scenario(
                scenario_id,
                mode=BASELINE,
                task_text="Observe filter shadow verdict.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_filter","type":"decision","summary":"Keep filter shadow as diagnostics only."}'
                ),
                adapter_name=ADAPTER_NAME,
                artifact_filter_shadow_mode=True,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            filter_telemetry = _extract_task_completed_artifact_filter_shadow(events)
            self.assertTrue(filter_telemetry["enabled"])
            self.assertEqual(filter_telemetry["mode"], "shadow")
            self.assertEqual(filter_telemetry["status"], "evaluated")
            self.assertEqual(filter_telemetry["verdict"], "accepted")
            self.assertEqual(filter_telemetry["raw_verdict"], "ACCEPT")
            self.assertTrue(filter_telemetry["structural_valid"])
            self.assertTrue(filter_telemetry["semantic_valid"])

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(artifact_events[0]["payload"]["artifact_id"], "decision_filter")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_filter_shadow_accepts_sc_prefixed_benchmark_artifact_without_changing_event(self) -> None:
        repo_root = _workspace_temp_dir("gemini_filter_shadow_accept")
        try:
            scenario_id = "sc_gemini_filter_shadow_accept"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_EPHEMERAL,
                task_text="Observe normalized filter shadow verdict without schema mutation.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"sc_08_cyclic_state_handling_rule","type":"decision","summary":"Keep benchmark compact artifact schema."}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_filter_shadow_mode=True,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            filter_telemetry = _extract_task_completed_artifact_filter_shadow(events)
            self.assertEqual(filter_telemetry["mode"], "shadow")
            self.assertEqual(filter_telemetry["status"], "evaluated")
            self.assertEqual(filter_telemetry["verdict"], "accepted")
            self.assertEqual(filter_telemetry["raw_verdict"], "ACCEPT")
            self.assertTrue(filter_telemetry["structural_valid"])

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(
                artifact_events[0]["payload"]["artifact_id"],
                "sc_08_cyclic_state_handling_rule",
            )
            self.assertEqual(
                artifact_events[0]["payload"]["artifact_candidate"],
                {
                    "id": "sc_08_cyclic_state_handling_rule",
                    "type": "decision",
                    "summary": "Keep benchmark compact artifact schema.",
                },
            )
            self.assertEqual(
                run_result["artifact_suggestion"],
                {
                    "id": "sc_08_cyclic_state_handling_rule",
                    "type": "decision",
                    "summary": "Keep benchmark compact artifact schema.",
                },
            )
            raw_log = run_result["raw_log_path"].read_text(encoding="utf-8")
            agent_output_section = raw_log.split("Agent Output:", 1)[1]
            self.assertEqual(agent_output_section.count("Artifact Suggestion:"), 1)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_filter_shadow_skips_none_and_malformed_outputs(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
            ),
            ("openai_codex", run_scenario, ADAPTER_NAME, BASELINE),
        )
        output_cases = (
            ("none", "Final Answer: done\nArtifact Suggestion: NONE"),
            ("malformed", "Final Answer: done\nArtifact Suggestion: {not valid json"),
        )

        for adapter_label, runner, adapter_name, mode in adapter_cases:
            for expected_outcome, agent_output in output_cases:
                with self.subTest(adapter=adapter_label, outcome=expected_outcome):
                    repo_root = _workspace_temp_dir(f"{adapter_label}_filter_{expected_outcome}")
                    try:
                        scenario_id = f"sc_{adapter_label}_filter_{expected_outcome}"
                        _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                        run_result = runner(
                            scenario_id,
                            mode=mode,
                            task_text="Observe skipped filter shadow.",
                            agent_output=agent_output,
                            adapter_name=adapter_name,
                            artifact_filter_shadow_mode=True,
                            repo_root=repo_root,
                            overwrite_existing_artifacts=True,
                        )

                        events = read_events(run_result["event_log_path"])
                        filter_telemetry = _extract_task_completed_artifact_filter_shadow(events)
                        self.assertTrue(filter_telemetry["enabled"])
                        self.assertEqual(filter_telemetry["mode"], "shadow")
                        self.assertEqual(filter_telemetry["status"], "skipped")
                        self.assertIsNone(filter_telemetry["verdict"])
                        self.assertEqual(filter_telemetry["parser_outcome"], expected_outcome)
                        self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
                    finally:
                        shutil.rmtree(repo_root, ignore_errors=True)

    def test_openai_filter_soft_mode_accepts_valid_benchmark_artifact_without_changing_artifact_event(self) -> None:
        repo_root = _workspace_temp_dir("openai_filter_soft_accept")
        try:
            scenario_id = "sc_openai_filter_soft_accept"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = run_scenario(
                scenario_id,
                mode=BASELINE,
                task_text="Observe filter soft verdict.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_soft","type":"decision","summary":"Keep soft filter diagnostics only."}'
                ),
                adapter_name=ADAPTER_NAME,
                artifact_filter_mode="soft",
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            payload = _extract_task_completed_payload(events)
            self.assertNotIn("artifact_filter_shadow", payload)

            filter_telemetry = _extract_task_completed_artifact_filter(events)
            self.assertEqual(filter_telemetry["mode"], "soft")
            self.assertEqual(filter_telemetry["status"], "evaluated")
            self.assertEqual(filter_telemetry["verdict"], "accepted")
            self.assertEqual(filter_telemetry["raw_verdict"], "ACCEPT")

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(artifact_events[0]["payload"]["artifact_id"], "decision_soft")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_filter_soft_accepts_normalized_benchmark_artifact_without_changing_event_or_persistence(self) -> None:
        repo_root = _workspace_temp_dir("g_filter_soft")
        try:
            scenario_id = "sc_gemini_filter_soft_accept"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Soft filter normalization must not mutate persistence.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_soft_normalized","type":"decision","summary":"Keep compact benchmark persistence."}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_filter_mode="soft",
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            filter_telemetry = _extract_task_completed_artifact_filter(events)
            self.assertEqual(filter_telemetry["mode"], "soft")
            self.assertEqual(filter_telemetry["status"], "evaluated")
            self.assertEqual(filter_telemetry["verdict"], "accepted")
            self.assertEqual(filter_telemetry["raw_verdict"], "ACCEPT")

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(
                artifact_events[0]["payload"]["artifact_id"],
                "decision_soft_normalized",
            )
            self.assertEqual(
                artifact_events[0]["payload"]["artifact_candidate"],
                {
                    "id": "decision_soft_normalized",
                    "type": "decision",
                    "summary": "Keep compact benchmark persistence.",
                },
            )

            decision_path = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "sc_gemini_decision_soft_normalized.json"
            )
            self.assertTrue(decision_path.is_file())
            persisted = json.loads(decision_path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted,
                {
                    "id": "sc_gemini_decision_soft_normalized",
                    "type": "decision",
                    "summary": "Keep compact benchmark persistence.",
                },
            )
            self.assertFalse((decision_path.parent / "decision_soft_normalized.json").exists())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapter_filter_input_normalization_maps_benchmark_artifacts_to_core_schema_only(self) -> None:
        benchmark_artifact = {
            "id": "decision_normalize",
            "type": "decision",
            "summary": "Keep normalized filter input separate.",
        }

        normalized = gemini_adapter_module._normalize_artifact_for_filter_input(
            benchmark_artifact
        )

        self.assertEqual(
            normalized,
            {
                "id": "decision_normalize",
                "type": "DecisionCard",
                "statement": "Keep normalized filter input separate.",
                "reason": ["Normalized from benchmark artifact for filter evaluation"],
                "status": "proposed",
            },
        )
        self.assertEqual(
            benchmark_artifact,
            {
                "id": "decision_normalize",
                "type": "decision",
                "summary": "Keep normalized filter input separate.",
            },
        )

    def test_adapter_filter_input_normalization_adds_core_prefix_for_sc_artifact_ids(self) -> None:
        benchmark_artifact = {
            "id": "sc_08_cyclic_state_handling_rule",
            "type": "decision",
            "summary": "Keep normalized filter input separate.",
        }

        normalized = gemini_adapter_module._normalize_artifact_for_filter_input(
            benchmark_artifact
        )

        self.assertEqual(normalized["id"], "decision_sc_08_cyclic_state_handling_rule")
        self.assertEqual(normalized["type"], "DecisionCard")
        self.assertEqual(benchmark_artifact["id"], "sc_08_cyclic_state_handling_rule")

    def test_adapter_filter_still_rejects_truly_invalid_artifacts_after_normalization_layer(self) -> None:
        telemetry = gemini_adapter_module._evaluate_artifact_filter(
            suggestion={
                "id": "unknown_invalid",
                "type": "unknown",
                "summary": "This artifact type remains unsupported.",
            },
            parser_outcome="valid",
            mode="soft",
        )

        self.assertEqual(telemetry["status"], "evaluated")
        self.assertEqual(telemetry["verdict"], "rejected")
        self.assertEqual(telemetry["raw_verdict"], "REJECT")
        self.assertIn("invalid artifact type: unknown", telemetry["reasons"])

    def test_adapters_filter_soft_mode_skips_none_missing_and_malformed_outputs(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
            ),
            ("openai_codex", run_scenario, ADAPTER_NAME, BASELINE),
        )
        output_cases = (
            ("missing", "Final Answer: done"),
            ("none", "Final Answer: done\nArtifact Suggestion: NONE"),
            ("malformed", "Final Answer: done\nArtifact Suggestion: {not valid json"),
        )

        for adapter_label, runner, adapter_name, mode in adapter_cases:
            for expected_outcome, agent_output in output_cases:
                with self.subTest(adapter=adapter_label, outcome=expected_outcome):
                    repo_root = _workspace_temp_dir(f"{adapter_label}_soft_{expected_outcome}")
                    try:
                        scenario_id = f"sc_{adapter_label}_soft_{expected_outcome}"
                        _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                        run_result = runner(
                            scenario_id,
                            mode=mode,
                            task_text="Observe skipped soft filter.",
                            agent_output=agent_output,
                            adapter_name=adapter_name,
                            artifact_filter_mode="soft",
                            repo_root=repo_root,
                            overwrite_existing_artifacts=True,
                        )

                        events = read_events(run_result["event_log_path"])
                        filter_telemetry = _extract_task_completed_artifact_filter(events)
                        self.assertEqual(filter_telemetry["mode"], "soft")
                        self.assertEqual(filter_telemetry["status"], "skipped")
                        self.assertIsNone(filter_telemetry["verdict"])
                        self.assertEqual(filter_telemetry["parser_outcome"], expected_outcome)
                        self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
                    finally:
                        shutil.rmtree(repo_root, ignore_errors=True)

    def test_artifact_filter_mode_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            gemini_adapter_module.run_scenario(
                "sc_filter_mode_invalid",
                mode=BASELINE,
                task_text="Invalid filter mode.",
                agent_output="Final Answer: done\nArtifact Suggestion: NONE",
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_filter_mode="hard",
            )

    def test_adapters_shadow_artifact_generation_classifies_outputs_without_artifact_events(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
                {
                    "none": "Final Answer: shadow\nArtifact Suggestion: NONE",
                    "malformed": "Final Answer: shadow\nArtifact Suggestion: {not valid json",
                    "valid": (
                        "Final Answer: shadow\n"
                        'Artifact Suggestion: {"id":"decision_shadow","type":"decision","summary":"Keep the shadow boundary."}'
                    ),
                },
            ),
            (
                "openai_codex",
                run_scenario,
                ADAPTER_NAME,
                BASELINE,
                {
                    "none": "Final Answer: shadow\nArtifact Suggestion: NONE",
                    "malformed": "Final Answer: shadow\nArtifact Suggestion: {not valid json",
                    "valid": (
                        "Final Answer: shadow\n"
                        'Artifact Suggestion: {"id":"decision_shadow","type":"decision","summary":"Keep the shadow boundary."}'
                    ),
                },
            ),
        )

        for adapter_label, runner, adapter_name, mode, shadow_outputs in adapter_cases:
            for expected_outcome, shadow_output in shadow_outputs.items():
                with self.subTest(adapter=adapter_label, shadow_outcome=expected_outcome):
                    repo_root = _workspace_temp_dir(f"{adapter_label}_shadow_{expected_outcome}")
                    try:
                        scenario_id = f"sc_{adapter_label}_shadow_{expected_outcome}"
                        _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                        run_result = runner(
                            scenario_id,
                            mode=mode,
                            task_text="Exercise shadow artifact parser telemetry.",
                            agent_output="Final Answer: active\nArtifact Suggestion: NONE",
                            adapter_name=adapter_name,
                            artifact_generator_mode=(
                                benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_SHADOW
                            ),
                            artifact_generator_shadow_output=shadow_output,
                            repo_root=repo_root,
                            overwrite_existing_artifacts=True,
                        )

                        events = read_events(run_result["event_log_path"])
                        shadow_telemetry = _extract_task_completed_artifact_generation_shadow(events)
                        self.assertTrue(shadow_telemetry["enabled"])
                        self.assertEqual(shadow_telemetry["parser_outcome"], expected_outcome)
                        self.assertEqual(
                            shadow_telemetry["artifact_proposed_count"],
                            1 if expected_outcome == "valid" else 0,
                        )
                        self.assertEqual(
                            shadow_telemetry["none_output_count"],
                            1 if expected_outcome == "none" else 0,
                        )
                        self.assertEqual(
                            shadow_telemetry["malformed_output_count"],
                            1 if expected_outcome == "malformed" else 0,
                        )
                        self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
                    finally:
                        shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_shadow_valid_artifact_does_not_override_active_artifact_or_persist(self) -> None:
        repo_root = _workspace_temp_dir("g_shadow")
        try:
            scenario_id = "sc_gemini_shadow_active_authoritative"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Persist only the active artifact suggestion.",
                agent_output=(
                    "Final Answer: active\n"
                    'Artifact Suggestion: {"id":"decision_active","type":"decision","summary":"Keep the active boundary."}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_generator_mode=(
                    benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_SHADOW
                ),
                artifact_generator_shadow_output=(
                    "Final Answer: shadow\n"
                    'Artifact Suggestion: {"id":"decision_shadow","type":"decision","summary":"Keep the shadow boundary."}'
                ),
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            shadow_telemetry = _extract_task_completed_artifact_generation_shadow(events)
            self.assertEqual(shadow_telemetry["parser_outcome"], "valid")

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(artifact_events[0]["payload"]["artifact_id"], "decision_active")
            self.assertEqual(run_result["artifact_suggestion"]["id"], "decision_active")

            decision_dir = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
            )
            self.assertTrue((decision_dir / "sc_gemini_decision_active.json").is_file())
            self.assertFalse((decision_dir / "decision_active.json").exists())
            self.assertFalse((decision_dir / "decision_shadow.json").exists())
            self.assertFalse((decision_dir / "sc_gemini_decision_shadow.json").exists())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_pr_light_brain_direct_persistence_prefixes_all_supported_artifact_types(self) -> None:
        repo_root = _workspace_temp_dir("g_prefix_all")
        try:
            scenario_id = "sc_00_stateless_direct_transform"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)
            suggestion_payload = {
                "TaskCard": {
                    "id": "task_string_transform_001",
                    "summary": "Keep the current benchmark task scoped to string transformation.",
                },
                "DecisionCard": {
                    "id": "dc_naming_convention_001",
                    "summary": "Use deterministic names for generated benchmark artifacts.",
                },
                "ConstraintCard": {
                    "id": "cc_no_semantic_guessing_001",
                    "summary": "Avoid semantic guessing when persisting benchmark artifacts.",
                },
                "ProcedureCard": {
                    "id": "pc_string_transformation_001",
                    "summary": "Apply the string transformation steps in their declared order.",
                },
            }

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Persist all supported artifact types with scenario scope.",
                agent_output=(
                    "Final Answer: done\n"
                    f"Artifact Suggestion: {json.dumps(suggestion_payload)}"
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(
                [event["payload"]["artifact_id"] for event in artifact_events],
                [
                    "task_string_transform_001",
                    "dc_naming_convention_001",
                    "cc_no_semantic_guessing_001",
                    "pc_string_transformation_001",
                ],
            )

            runtime_root = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
            )
            for folder, artifact_id in (
                ("tasks", "sc_00_task_string_transform_001"),
                ("decisions", "sc_00_dc_naming_convention_001"),
                ("constraints", "sc_00_cc_no_semantic_guessing_001"),
                ("procedures", "sc_00_pc_string_transformation_001"),
            ):
                persisted_path = runtime_root / "brain" / folder / f"{artifact_id}.json"
                self.assertTrue(persisted_path.is_file())
                persisted_payload = json.loads(persisted_path.read_text(encoding="utf-8"))
                self.assertEqual(persisted_payload["id"], artifact_id)

            self.assertFalse(
                (
                    runtime_root
                    / "brain"
                    / "decisions"
                    / "dc_naming_convention_001.json"
                ).exists()
            )
            working_context = json.loads(
                (runtime_root / "views" / "working_context.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(working_context["tasks"], ["sc_00_task_string_transform_001"])
            self.assertEqual(working_context["decisions"], ["sc_00_dc_naming_convention_001"])
            self.assertEqual(working_context["constraints"], ["sc_00_cc_no_semantic_guessing_001"])
            self.assertEqual(working_context["procedures"], ["sc_00_pc_string_transformation_001"])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_pr_light_brain_direct_persistence_keeps_already_prefixed_ids(self) -> None:
        repo_root = _workspace_temp_dir("g_prefixed")
        try:
            scenario_id = "sc_09_zero_crossing_event_trap"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Persist an already scoped artifact suggestion.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"sc_09_dec_zero_crossing_trigger_logic",'
                    '"type":"decision","summary":"Keep zero crossing trigger logic scoped."}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            decision_dir = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
            )
            self.assertTrue(
                (decision_dir / "sc_09_dec_zero_crossing_trigger_logic.json").is_file()
            )
            self.assertFalse(
                (
                    decision_dir
                    / "sc_09_sc_09_dec_zero_crossing_trigger_logic.json"
                ).exists()
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_direct_pr_light_brain_and_post_run_harvest_use_same_normalized_artifact_id(self) -> None:
        repo_root = _workspace_temp_dir("g_harvest_same")
        try:
            scenario_id = SCENARIO_ID
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Persist a directly suggested benchmark artifact.",
                agent_output=(
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_shared_scope",'
                    '"type":"decision","summary":"Share the same scenario-scoped id."}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )
            direct_path = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "sc_0_decision_shared_scope.json"
            )
            self.assertTrue(direct_path.is_file())

            _write_harvest_event_log(
                repo_root,
                scenario_id=scenario_id,
                mode=PR_EPHEMERAL,
                candidate={
                    "id": "decision_shared_scope",
                    "type": "decision",
                    "summary": "Share the same scenario-scoped id.",
                },
            )
            report = build_post_run_artifact_harvest_report(
                repo_root=repo_root,
                scenario_ids=(scenario_id,),
                source_modes=(PR_EPHEMERAL,),
                enabled=True,
                runtime_available=True,
            )

            self.assertEqual(report["items"][0]["artifact_id"], "sc_0_decision_shared_scope")
            self.assertEqual(report["items"][0]["original_artifact_id"], "decision_shared_scope")
            self.assertFalse(
                (
                    repo_root
                    / "reasoning_brain_storage"
                    / "benchmarks"
                    / "runtime"
                    / "brain"
                    / "decisions"
                    / "decision_shared_scope.json"
                ).exists()
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_constrained_active_none_uses_constrained_prompt_and_does_not_persist(self) -> None:
        repo_root = _workspace_temp_dir("gemini_constrained_none")
        try:
            scenario_id = "sc_gemini_constrained_none"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Use constrained active artifact generation.",
                agent_output="Final Answer: done\nArtifact Suggestion: NONE",
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_generator_mode=(
                    benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_CONSTRAINED
                ),
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            self.assertIn(
                "Default Artifact Suggestion output for every artifact type is NONE.",
                run_result["prompt"],
            )
            events = read_events(run_result["event_log_path"])
            telemetry = _extract_task_completed_artifact_generation(events)
            self.assertEqual(telemetry["parser_outcome"], "none")
            self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)

            decision_dir = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
            )
            self.assertEqual(list(decision_dir.glob("*.json")), [])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_constrained_active_valid_artifact_emits_artifact_suggested(self) -> None:
        valid_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
                (
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_constrained","type":"decision","summary":"Keep constrained active output."}'
                ),
                "decision",
            ),
            (
                "openai_codex",
                run_scenario,
                ADAPTER_NAME,
                BASELINE,
                (
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_constrained","type":"decision","summary":"Keep constrained active output."}'
                ),
                "decision",
            ),
        )

        for adapter_label, runner, adapter_name, mode, agent_output, artifact_type in valid_cases:
            with self.subTest(adapter=adapter_label):
                repo_root = _workspace_temp_dir(f"{adapter_label}_constrained_valid")
                try:
                    scenario_id = f"sc_{adapter_label}_constrained_valid"
                    _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                    run_result = runner(
                        scenario_id,
                        mode=mode,
                        task_text="Use constrained active artifact generation.",
                        agent_output=agent_output,
                        adapter_name=adapter_name,
                        artifact_generator_mode=(
                            benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_CONSTRAINED
                        ),
                        repo_root=repo_root,
                        overwrite_existing_artifacts=True,
                    )

                    self.assertIn(
                        "Default Artifact Suggestion output for every artifact type is NONE.",
                        run_result["prompt"],
                    )
                    events = read_events(run_result["event_log_path"])
                    telemetry = _extract_task_completed_artifact_generation(events)
                    self.assertEqual(telemetry["parser_outcome"], "valid")
                    self.assertEqual(telemetry["artifact_proposed_count"], 1)

                    artifact_events = [
                        event for event in events if event["event_type"] == "artifact_suggested"
                    ]
                    self.assertEqual(len(artifact_events), 1)
                    self.assertEqual(
                        artifact_events[0]["payload"]["artifact_id"],
                        "decision_constrained",
                    )
                    self.assertEqual(artifact_events[0]["payload"]["artifact_type"], artifact_type)
                finally:
                    shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_constrained_active_malformed_artifact_is_telemetry_only(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
            ),
            ("openai_codex", run_scenario, ADAPTER_NAME, BASELINE),
        )

        for adapter_label, runner, adapter_name, mode in adapter_cases:
            with self.subTest(adapter=adapter_label):
                repo_root = _workspace_temp_dir(f"{adapter_label}_constrained_bad")
                try:
                    scenario_id = f"sc_{adapter_label}_constrained_bad"
                    _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                    run_result = runner(
                        scenario_id,
                        mode=mode,
                        task_text="Use constrained active artifact generation.",
                        agent_output="Final Answer: done\nArtifact Suggestion: {not valid json",
                        adapter_name=adapter_name,
                        artifact_generator_mode=(
                            benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_CONSTRAINED
                        ),
                        repo_root=repo_root,
                        overwrite_existing_artifacts=True,
                    )

                    self.assertIn(
                        "Default Artifact Suggestion output for every artifact type is NONE.",
                        run_result["prompt"],
                    )
                    events = read_events(run_result["event_log_path"])
                    telemetry = _extract_task_completed_artifact_generation(events)
                    self.assertEqual(telemetry["parser_outcome"], "malformed")
                    self.assertEqual(telemetry["malformed_output_count"], 1)
                    self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
                finally:
                    shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_shadow_mode_keeps_active_none_authoritative(self) -> None:
        repo_root = _workspace_temp_dir("gemini_constrained_shadow")
        try:
            scenario_id = "sc_gemini_constrained_shadow"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Keep active NONE authoritative.",
                agent_output="Final Answer: active\nArtifact Suggestion: NONE",
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                artifact_generator_mode=(
                    benchmark_prompt_utils.ARTIFACT_GENERATOR_MODE_SHADOW
                ),
                artifact_generator_shadow_output=(
                    "Final Answer: shadow\n"
                    'Artifact Suggestion: {"id":"decision_shadow","type":"decision","summary":"Keep the shadow boundary."}'
                ),
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            active_telemetry = _extract_task_completed_artifact_generation(events)
            shadow_telemetry = _extract_task_completed_artifact_generation_shadow(events)
            self.assertEqual(active_telemetry["parser_outcome"], "none")
            self.assertEqual(shadow_telemetry["parser_outcome"], "valid")
            self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
            self.assertIsNone(run_result["artifact_suggestion"])

            decision_dir = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
            )
            self.assertFalse((decision_dir / "decision_shadow.json").exists())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_adapter_artifact_suggested_event_carries_full_candidate_payload(self) -> None:
        repo_root = _workspace_temp_dir("artifact_candidate_event")
        try:
            scenario_id = "sc_phase5_boundary_probe"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_EPHEMERAL,
                task_text="Persist the validated architecture decision.",
                agent_output=(
                    "Final Answer: done\n\n"
                    'Artifact Suggestion: {"id":"decision_boundary","type":"decision","summary":"persist validated boundary decision"}'
                ),
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(len(artifact_events), 1)
            payload = artifact_events[0]["payload"]
            self.assertEqual(payload["artifact_id"], "decision_boundary")
            self.assertEqual(payload["artifact_type"], "decision")
            self.assertEqual(
                payload["artifact_candidate"],
                {
                    "id": "decision_boundary",
                    "type": "decision",
                    "summary": "persist validated boundary decision",
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_classify_missing_none_and_malformed_artifact_suggestions(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
            ),
            ("openai_codex", run_scenario, ADAPTER_NAME, BASELINE),
        )
        output_cases = (
            ("missing", "Final Answer: done"),
            ("none", "Final Answer: done\nArtifact Suggestion: NONE"),
            ("malformed", "Final Answer: done\nArtifact Suggestion: {not valid json"),
        )

        for adapter_label, runner, adapter_name, mode in adapter_cases:
            for expected_outcome, agent_output in output_cases:
                with self.subTest(adapter=adapter_label, outcome=expected_outcome):
                    repo_root = _workspace_temp_dir(f"{adapter_label}_{expected_outcome}")
                    try:
                        scenario_id = f"sc_{adapter_label}_{expected_outcome}"
                        _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                        run_result = runner(
                            scenario_id,
                            mode=mode,
                            task_text="Exercise artifact parser telemetry.",
                            agent_output=agent_output,
                            adapter_name=adapter_name,
                            repo_root=repo_root,
                            overwrite_existing_artifacts=True,
                        )

                        events = read_events(run_result["event_log_path"])
                        telemetry = _extract_task_completed_artifact_generation(events)
                        self.assertEqual(telemetry["parser_outcome"], expected_outcome)
                        self.assertEqual(telemetry["artifact_proposed_count"], 0)
                        self.assertEqual(
                            telemetry["none_output_count"],
                            1 if expected_outcome == "none" else 0,
                        )
                        self.assertEqual(
                            telemetry["malformed_output_count"],
                            1 if expected_outcome == "malformed" else 0,
                        )
                        self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)
                    finally:
                        shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_valid_artifact_suggestion_keeps_artifact_event_and_valid_telemetry(self) -> None:
        valid_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
                (
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_valid","type":"decision","summary":"Keep the durable boundary."}'
                ),
                "decision_valid",
                "decision",
            ),
            (
                "openai_codex",
                run_scenario,
                ADAPTER_NAME,
                BASELINE,
                (
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"decision_valid","type":"decision","summary":"Keep the durable boundary."}'
                ),
                "decision_valid",
                "decision",
            ),
        )

        for adapter_label, runner, adapter_name, mode, agent_output, artifact_id, artifact_type in valid_cases:
            with self.subTest(adapter=adapter_label):
                repo_root = _workspace_temp_dir(f"{adapter_label}_valid")
                try:
                    scenario_id = f"sc_{adapter_label}_valid"
                    _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                    run_result = runner(
                        scenario_id,
                        mode=mode,
                        task_text="Exercise valid artifact parser telemetry.",
                        agent_output=agent_output,
                        adapter_name=adapter_name,
                        repo_root=repo_root,
                        overwrite_existing_artifacts=True,
                    )

                    events = read_events(run_result["event_log_path"])
                    telemetry = _extract_task_completed_artifact_generation(events)
                    self.assertEqual(telemetry["parser_outcome"], "valid")
                    self.assertEqual(telemetry["artifact_proposed_count"], 1)
                    self.assertEqual(telemetry["none_output_count"], 0)
                    self.assertEqual(telemetry["malformed_output_count"], 0)

                    artifact_events = [
                        event for event in events if event["event_type"] == "artifact_suggested"
                    ]
                    self.assertEqual(len(artifact_events), 1)
                    self.assertEqual(artifact_events[0]["payload"]["artifact_id"], artifact_id)
                    self.assertEqual(artifact_events[0]["payload"]["artifact_type"], artifact_type)
                finally:
                    shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_none_artifact_suggestion_does_not_persist_pr_light_brain_artifact(self) -> None:
        repo_root = _workspace_temp_dir("gemini_none_no_persistence")
        try:
            scenario_id = "sc_gemini_none_no_persistence"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

            run_result = gemini_adapter_module.run_scenario(
                scenario_id,
                mode=PR_LIGHT_BRAIN,
                task_text="Do not persist an artifact for NONE.",
                agent_output="Final Answer: done\nArtifact Suggestion: NONE",
                adapter_name=gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            telemetry = _extract_task_completed_artifact_generation(events)
            self.assertEqual(telemetry["parser_outcome"], "none")
            self.assertEqual(_count_event_type(events, "artifact_suggested"), 0)

            decision_dir = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
            )
            self.assertEqual(list(decision_dir.glob("*.json")), [])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_artifact_harvest_uses_event_logs_and_persists_accepted_runtime_artifacts(self) -> None:
        repo_root = _workspace_temp_dir("harvest_accept")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=PR_EPHEMERAL,
                candidate={
                    "id": "decision_harvested",
                    "type": "decision",
                    "summary": "harvest the persisted benchmark candidate",
                },
            )
            trace_log = result_log_path(BenchmarkPaths(repo_root=repo_root), PR_EPHEMERAL, SCENARIO_ID)
            trace_log.write_text("this trace should not be consulted\n", encoding="utf-8")

            report_path = run_post_run_artifact_harvest(
                repo_root=repo_root,
                run_id="harvest_accept",
                scenario_ids=(SCENARIO_ID,),
                source_modes=(PR_EPHEMERAL,),
                enabled=True,
                runtime_available=True,
            )
            self.assertEqual(report_path.name, HARVEST_REPORT_FILENAME)
            report = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(report["accepted"], 1)
            self.assertEqual(report["persisted_count"], 1)
            self.assertTrue(report["runtime_updated"])
            self.assertEqual(report["items"][0]["artifact_id"], "sc_0_decision_harvested")
            self.assertEqual(report["items"][0]["original_artifact_id"], "decision_harvested")
            persisted_path = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "sc_0_decision_harvested.json"
            )
            self.assertTrue(persisted_path.is_file())
            persisted_payload = json.loads(persisted_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_payload["id"], "sc_0_decision_harvested")
            persisted_event = read_events(
                result_events_path(
                    BenchmarkPaths(repo_root=repo_root),
                    PR_EPHEMERAL,
                    SCENARIO_ID,
                )
            )[1]
            self.assertEqual(
                persisted_event["payload"]["artifact_candidate"]["id"],
                "decision_harvested",
            )
            working_context = json.loads(
                (
                    repo_root
                    / "reasoning_brain_storage"
                    / "benchmarks"
                    / "runtime"
                    / "views"
                    / "working_context.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(working_context["decisions"], ["sc_0_decision_harvested"])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_artifact_harvest_persists_accepted_artifacts_by_type(self) -> None:
        repo_root = _workspace_temp_dir("harvest_accept_all_types")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            paths = BenchmarkPaths(repo_root=repo_root)
            event_path = result_events_path(paths, PR_EPHEMERAL, SCENARIO_ID)
            logger = BenchmarkEventLogger(
                event_log_path=event_path,
                scenario_id=SCENARIO_ID,
                mode=PR_EPHEMERAL,
                auto_reset=True,
                allow_overwrite=True,
            )
            logger.log_task_started()
            candidates = (
                {"id": "task_goal", "type": "task", "summary": "clarify durable benchmark goal"},
                {"id": "decision_rule", "type": "decision", "summary": "choose durable benchmark rule"},
                {"id": "constraint_rule", "type": "constraint", "summary": "never violate benchmark rule"},
                {"id": "procedure_flow", "type": "procedure", "summary": "run deterministic benchmark workflow"},
            )
            for candidate in candidates:
                logger.log_artifact_suggested(
                    {
                        "artifact_id": candidate["id"],
                        "artifact_type": candidate["type"],
                        "artifact_candidate": candidate,
                    }
                )
            logger.log_task_completed({"success": True, "execution_source": "manual_override"})

            report = build_post_run_artifact_harvest_report(
                repo_root=repo_root,
                scenario_ids=(SCENARIO_ID,),
                source_modes=(PR_EPHEMERAL,),
                enabled=True,
                runtime_available=True,
            )

            self.assertEqual(report["accepted"], 4)
            self.assertEqual(report["persisted_count"], 4)
            for folder, artifact_id in (
                ("tasks", "sc_0_task_goal"),
                ("decisions", "sc_0_decision_rule"),
                ("constraints", "sc_0_constraint_rule"),
                ("procedures", "sc_0_procedure_flow"),
            ):
                self.assertTrue(
                    (
                        repo_root
                        / "reasoning_brain_storage"
                        / "benchmarks"
                        / "runtime"
                        / "brain"
                        / folder
                        / f"{artifact_id}.json"
                    ).is_file()
                )
            working_context = json.loads(
                (paths.runtime_brain_root / "views" / "working_context.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(working_context["tasks"], ["sc_0_task_goal"])
            self.assertEqual(working_context["decisions"], ["sc_0_decision_rule"])
            self.assertEqual(working_context["constraints"], ["sc_0_constraint_rule"])
            self.assertEqual(working_context["procedures"], ["sc_0_procedure_flow"])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_artifact_harvest_keeps_already_prefixed_artifact_ids(self) -> None:
        repo_root = _workspace_temp_dir("harvest_prefixed")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=BASELINE,
                candidate={
                    "id": "sc_0_decision_prefixed",
                    "type": "decision",
                    "summary": "already scoped benchmark candidate",
                },
            )

            report = build_post_run_artifact_harvest_report(
                repo_root=repo_root,
                scenario_ids=(SCENARIO_ID,),
                source_modes=(BASELINE,),
                enabled=True,
                runtime_available=True,
            )

            self.assertEqual(report["accepted"], 1)
            self.assertEqual(report["items"][0]["artifact_id"], "sc_0_decision_prefixed")
            self.assertNotIn("original_artifact_id", report["items"][0])
            persisted_path = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "sc_0_decision_prefixed.json"
            )
            self.assertTrue(persisted_path.is_file())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_artifact_harvest_reports_duplicates_rejections_and_invalid_candidates(self) -> None:
        repo_root = _workspace_temp_dir("harvest_mixed")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_decision = (
                repo_root
                / "reasoning_brain_storage"
                / "benchmarks"
                / "runtime"
                / "brain"
                / "decisions"
                / "sc_0_decision_existing.json"
            )
            runtime_decision.write_text(
                json.dumps(
                    {
                        "id": "sc_0_decision_existing",
                        "type": "decision",
                        "summary": "already persisted",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=BASELINE,
                candidate={
                    "id": "decision_existing",
                    "type": "decision",
                    "summary": "already persisted",
                },
            )
            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=PR_LIGHT_BRAIN,
                candidate={
                    "id": "decision_bad_type",
                    "type": "json_schema",
                    "summary": "unsupported type",
                },
            )
            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=PR_EPHEMERAL,
                raw_payload={
                    "artifact_id": "decision_invalid",
                    "artifact_type": "decision",
                },
            )

            report = build_post_run_artifact_harvest_report(
                repo_root=repo_root,
                scenario_ids=(SCENARIO_ID,),
                source_modes=(BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN),
                enabled=True,
                runtime_available=True,
            )

            self.assertEqual(report["duplicates"], 1)
            self.assertEqual(report["rejected"], 1)
            self.assertEqual(report["invalid"], 1)
            self.assertEqual(report["persisted_count"], 0)
            self.assertFalse(report["runtime_updated"])
            duplicate_item = next(
                item for item in report["items"] if item["status"] == "duplicate"
            )
            self.assertEqual(duplicate_item["artifact_id"], "sc_0_decision_existing")
            self.assertEqual(duplicate_item["original_artifact_id"], "decision_existing")
            self.assertEqual(duplicate_item["duplicate_of"], "sc_0_decision_existing")
            seeded_decisions = json.loads(
                (
                    repo_root
                    / "reasoning_brain_storage"
                    / "benchmarks"
                    / "seeded"
                    / "views"
                    / "working_context.json"
                ).read_text(encoding="utf-8")
            )["decisions"]
            self.assertEqual(seeded_decisions, [])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_artifact_harvest_skips_cleanly_when_disabled(self) -> None:
        repo_root = _workspace_temp_dir("harvest_disabled")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            report = build_post_run_artifact_harvest_report(
                repo_root=repo_root,
                scenario_ids=(SCENARIO_ID,),
                source_modes=(BASELINE, PR_LIGHT_BRAIN),
                enabled=False,
                runtime_available=True,
            )
            self.assertFalse(report["enabled"])
            self.assertEqual(report["skip_reason"], "disabled")
            self.assertEqual(report["candidates_seen"], 0)
            self.assertEqual(report["items"], [])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_runner_invokes_post_run_artifact_harvest_before_post_run_lifecycle(self) -> None:
        sequence: list[str] = []
        fake_profile = SimpleNamespace(
            name="test_profile",
            backend="gemini",
            model="gemini-flash-lite-latest",
            scenario_subset=(SCENARIO_ID,),
            diagnostic_modes=SimpleNamespace(
                pr_ephemeral=False,
                post_run_artifact_harvest=True,
            ),
            brain_mode="accumulative",
            brain_in=SimpleNamespace(type="runtime"),
            brain_out=SimpleNamespace(mode="continue"),
            inter_scenario_delay_seconds=1,
            showcase=run_benchmarks_module.SHOWCASE_SCENARIO_ID,
            mode_to_key_mapping="strict",
        )
        fake_backend = SimpleNamespace(
            backend="gemini",
            adapter_name="gemini",
            get_benchmark_agent_metadata=lambda **_: {
                "adapter": "gemini",
                "full_agent_name": "Gemini",
                "agent_model": "gemini-flash-lite-latest",
            },
        )

        with patch.object(
            run_benchmarks_module,
            "parse_args",
            return_value=SimpleNamespace(
                profile="test_profile",
                backend=None,
                artifact_generator_mode=None,
                artifact_filter_mode=None,
                working_context_format=None,
            ),
        ), patch.object(
            run_benchmarks_module,
            "load_profile",
            return_value=fake_profile,
        ), patch.object(
            run_benchmarks_module,
            "resolve_backend",
            return_value=fake_backend,
        ), patch.object(
            run_benchmarks_module,
            "run_preflight",
            side_effect=lambda *args, **kwargs: sequence.append("preflight"),
        ), patch.object(
            run_benchmarks_module,
            "apply_pre_run_brain_lifecycle",
            side_effect=lambda *args, **kwargs: sequence.append("pre_run_lifecycle"),
        ), patch.object(
            run_benchmarks_module,
            "clean_temporary_benchmark_results",
            side_effect=lambda *args, **kwargs: sequence.append("clean_results"),
        ), patch.object(
            run_benchmarks_module,
            "run_all",
            side_effect=lambda *args, **kwargs: sequence.append("run_all")
            or run_benchmarks_module.RunExecutionState(quota_stop_reason=None, total_429_count=0),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_layer_manifest",
            side_effect=lambda *args, **kwargs: Path("scenario_layers.json"),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_interpretation_support_manifest",
            side_effect=lambda *args, **kwargs: Path("scenario_interpretation_support.json"),
        ), patch.object(
            run_benchmarks_module,
            "run_post_processing",
            side_effect=lambda *args, **kwargs: sequence.append("post_processing"),
        ), patch.object(
            run_benchmarks_module,
            "apply_post_run_brain_lifecycle",
            side_effect=lambda *args, **kwargs: sequence.append("post_run_lifecycle"),
        ), patch.object(
            run_benchmarks_module,
            "run_post_run_artifact_harvest",
            side_effect=lambda *args, **kwargs: sequence.append("post_run_harvest")
            or Path(HARVEST_REPORT_FILENAME),
        ), patch.object(
            run_benchmarks_module,
            "build_run_id",
            return_value="test_run",
        ), patch("builtins.print"):
            run_benchmarks_module.main()

        self.assertLess(sequence.index("run_all"), sequence.index("post_processing"))
        self.assertLess(sequence.index("post_processing"), sequence.index("post_run_harvest"))
        self.assertLess(sequence.index("post_run_harvest"), sequence.index("post_run_lifecycle"))

    def test_post_run_artifact_harvest_allows_continue_and_snapshot_modes(self) -> None:
        for brain_out_mode in ("continue", "snapshot"):
            with self.subTest(brain_out_mode=brain_out_mode):
                profile = run_benchmarks_module.BenchmarkProfile(
                    diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(
                        pr_ephemeral=False,
                        post_run_artifact_harvest=True,
                    ),
                    brain_mode="accumulative",
                    brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                    brain_out=run_benchmarks_module.BrainOutPolicy(
                        mode=brain_out_mode,
                        ref=None,
                    ),
                    name="test",
                    backend="gemini",
                    model="gemini-flash-lite-latest",
                    scenario_subset=(SCENARIO_ID,),
                    showcase=SCENARIO_ID,
                    mode_to_key_mapping="strict",
                    timeout_seconds=20,
                    inter_scenario_delay_seconds=1,
                    on_429_first="wait_30s_retry_once",
                    on_429_second="stop_run",
                    purpose="test",
                )

                self.assertTrue(
                    run_benchmarks_module._post_run_harvest_runtime_available(profile)
                )
                self.assertIsNone(
                    run_benchmarks_module._post_run_harvest_skip_reason(
                        profile=profile,
                        execution_completed=True,
                    )
                )

    def test_post_run_artifact_harvest_before_snapshot_includes_baseline_artifacts(self) -> None:
        repo_root = _workspace_temp_dir("hbs")
        run_id = "hbs"
        try:
            self._build_profile_lifecycle_repo(repo_root)
            _write_harvest_event_log(
                repo_root,
                scenario_id=SCENARIO_ID,
                mode=BASELINE,
                candidate={
                    "id": "decision_baseline_harvest",
                    "type": "decision",
                    "summary": "harvest baseline accepted artifact before snapshot",
                },
            )
            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(
                    pr_ephemeral=False,
                    post_run_artifact_harvest=True,
                ),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="snapshot", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            report_path = run_post_run_artifact_harvest(
                repo_root=repo_root,
                run_id=run_id,
                scenario_ids=(SCENARIO_ID,),
                source_modes=(BASELINE,),
                enabled=True,
                runtime_available=run_benchmarks_module._post_run_harvest_runtime_available(
                    profile
                ),
                skip_reason=run_benchmarks_module._post_run_harvest_skip_reason(
                    profile=profile,
                    execution_completed=True,
                ),
            )
            run_benchmarks_module.apply_post_run_brain_lifecycle(
                repo_root,
                run_id=run_id,
                profile=profile,
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["source_modes"], [BASELINE])
            self.assertEqual(report["accepted"], 1)
            self.assertEqual(report["persisted_count"], 1)
            self.assertEqual(
                report["items"][0]["artifact_id"],
                "sc_0_decision_baseline_harvest",
            )
            self.assertEqual(
                report["items"][0]["original_artifact_id"],
                "decision_baseline_harvest",
            )
            snapshot_decision = (
                repo_root
                / "reasoning_brain_storage"
                / "snapshots"
                / run_id
                / "brain"
                / "decisions"
                / "sc_0_decision_baseline_harvest.json"
            )
            self.assertTrue(snapshot_decision.is_file())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapters_parser_accepts_inline_block_and_pretty_artifact_suggestions(self) -> None:
        expected = {
            "id": "cyclic_clock_state_tracking_rule",
            "type": "decision",
            "summary": (
                "In cyclic state movement, verify trigger points (POS_B) at every "
                "partial interval calculation to ensure accurate shift accumulation."
            ),
        }
        output_cases = (
            (
                "inline",
                (
                    "Final Answer: done\n"
                    'Artifact Suggestion: {"id":"cyclic_clock_state_tracking_rule", "type":"decision", "summary":"In cyclic state movement, verify trigger points (POS_B) at every partial interval calculation to ensure accurate shift accumulation."}'
                ),
            ),
            (
                "block_compact",
                (
                    "Final Answer: done\n"
                    "Artifact Suggestion:\n"
                    '{"id":"cyclic_clock_state_tracking_rule","type":"decision","summary":"In cyclic state movement, verify trigger points (POS_B) at every partial interval calculation to ensure accurate shift accumulation."}'
                ),
            ),
            (
                "pretty",
                "\n".join(
                    [
                        "Final Answer: done",
                        "Artifact Suggestion:",
                        "{",
                        '  "id": "cyclic_clock_state_tracking_rule",',
                        '  "type": "decision",',
                        '  "summary": "In cyclic state movement, verify trigger points (POS_B) at every partial interval calculation to ensure accurate shift accumulation."',
                        "}",
                    ]
                ),
            ),
        )
        adapter_cases = (
            (
                "gemini",
                lambda output: gemini_adapter_module._parse_agent_artifact_output_or_none(
                    output,
                    mode=PR_LIGHT_BRAIN,
                ),
            ),
            (
                "openai_codex",
                openai_codex_adapter_module._parse_agent_artifact_output_or_none,
            ),
        )

        for adapter_label, parser in adapter_cases:
            for output_label, agent_output in output_cases:
                with self.subTest(adapter=adapter_label, output=output_label):
                    self.assertEqual(parser(agent_output), expected)

    def test_adapters_parser_classifies_inline_and_block_none_as_none(self) -> None:
        adapter_cases = (
            (
                "gemini",
                lambda output: gemini_adapter_module._classify_agent_artifact_output(
                    output,
                    mode=PR_LIGHT_BRAIN,
                ),
            ),
            (
                "openai_codex",
                openai_codex_adapter_module._classify_agent_artifact_output,
            ),
        )
        output_cases = (
            "Final Answer: done\nArtifact Suggestion: NONE",
            "Final Answer: done\nArtifact Suggestion:\nNONE",
        )

        for adapter_label, classifier in adapter_cases:
            for agent_output in output_cases:
                with self.subTest(adapter=adapter_label, output=agent_output):
                    parser_outcome, suggestion = classifier(agent_output)
                    self.assertEqual(parser_outcome, "none")
                    self.assertIsNone(suggestion)

    def test_adapters_parser_rejects_unsupported_noncanonical_suggestions(self) -> None:
        invalid_outputs = (
            (
                "json_schema_type",
                'Artifact Suggestion: {"artifact_id":"schema","type":"json_schema","summary":"Schema for issues."}',
            ),
            (
                "missing_summary",
                'Artifact Suggestion: {"artifact_id":"decision_missing","type":"decision"}',
            ),
            (
                "wrong_type",
                'Artifact Suggestion: {"id":"task_1","type":"task","summary":"Track the migration."}',
            ),
            (
                "extra_fields",
                'Artifact Suggestion: {"id":"decision_extra","type":"decision","summary":"Track the migration.","status":"accepted"}',
            ),
            (
                "alias_id",
                'Artifact Suggestion: {"artifact_id":"decision_alias","type":"decision","summary":"Track the migration."}',
            ),
            (
                "state_content_shape",
                'Artifact Suggestion: {"task":"knowledge_platform_design","state":"decentralized_p2p","architecture":"CRDT_mesh","status":"finalized"}',
            ),
            (
                "content_only_shape",
                'Artifact Suggestion: {"artifact_id":"mits_core_schema","type":"json_schema","content":{"entity":"Issue"}}',
            ),
        )

        for label, artifact_line in invalid_outputs:
            for adapter_label, parser in (
                (
                    "gemini",
                    lambda output: gemini_adapter_module._parse_agent_artifact_output_or_none(
                        output,
                        mode=PR_LIGHT_BRAIN,
                    ),
                ),
                (
                    "openai_codex",
                    openai_codex_adapter_module._parse_agent_artifact_output_or_none,
                ),
            ):
                with self.subTest(adapter=adapter_label, case=label):
                    agent_output = f"Final Answer: done\n{artifact_line}"
                    self.assertIsNone(parser(agent_output))

    def test_adapters_multi_type_artifact_suggestion_parses_contract_types(self) -> None:
        agent_output = (
            "Final Answer: done\n"
            "Artifact Suggestion:\n"
            + json.dumps(
                {
                    "TaskCard": {
                        "id": "clarify_goal",
                        "summary": "Clarify the durable goal when task framing is ambiguous.",
                    },
                    "DecisionCard": {
                        "id": "choose_boundary_rule",
                        "summary": "Use boundary-trigger rules before applying cyclic state movement.",
                    },
                    "ConstraintCard": {
                        "id": "never_skip_boundary",
                        "summary": "Never skip a checkable boundary trigger during cyclic movement.",
                    },
                    "ProcedureCard": {
                        "id": "apply_boundary_workflow",
                        "summary": "Check boundary, apply trigger, then advance cyclic state.",
                    },
                }
            )
        )

        adapter_cases = (
            (
                "gemini",
                lambda output: gemini_adapter_module._classify_agent_artifact_outputs(
                    output,
                    mode=PR_LIGHT_BRAIN,
                ),
            ),
            ("openai_codex", openai_codex_adapter_module._classify_agent_artifact_outputs),
        )

        for adapter_label, classifier in adapter_cases:
            with self.subTest(adapter=adapter_label):
                outcome, suggestions = classifier(agent_output)
                self.assertEqual(outcome, "valid")
                self.assertEqual(
                    [suggestion["type"] for suggestion in suggestions],
                    ["task", "decision", "constraint", "procedure"],
                )

    def test_adapters_multi_type_artifact_suggestion_rejects_extra_or_multiple_types(self) -> None:
        invalid_payloads = (
            {
                "TaskCard": "NONE",
                "DecisionCard": "NONE",
                "ConstraintCard": "NONE",
                "ProcedureCard": "NONE",
                "IssueCard": "NONE",
            },
            {
                "TaskCard": "NONE",
                "DecisionCard": [
                    {"id": "one", "summary": "First duplicate decision."},
                    {"id": "two", "summary": "Second duplicate decision."},
                ],
                "ConstraintCard": "NONE",
                "ProcedureCard": "NONE",
            },
        )

        for payload in invalid_payloads:
            agent_output = "Final Answer: done\nArtifact Suggestion:\n" + json.dumps(payload)
            with self.subTest(payload=payload):
                self.assertIsNone(
                    gemini_adapter_module._parse_agent_artifact_output_or_none(
                        agent_output,
                        mode=PR_LIGHT_BRAIN,
                    )
                )
                self.assertIsNone(
                    openai_codex_adapter_module._parse_agent_artifact_output_or_none(
                        agent_output
                    )
                )

    def test_adapters_valid_inline_artifact_reaches_soft_filter(self) -> None:
        adapter_cases = (
            (
                "gemini",
                gemini_adapter_module.run_scenario,
                gemini_adapter_module.DEFAULT_ADAPTER_NAME,
                PR_EPHEMERAL,
            ),
            ("openai_codex", run_scenario, ADAPTER_NAME, BASELINE),
        )
        agent_output = (
            "Final Answer: done\n"
            'Artifact Suggestion: {"id":"cyclic_clock_state_tracking_rule", "type":"decision", "summary":"In cyclic state movement, verify trigger points (POS_B) at every partial interval calculation to ensure accurate shift accumulation."}'
        )

        for adapter_label, runner, adapter_name, mode in adapter_cases:
            with self.subTest(adapter=adapter_label):
                repo_root = _workspace_temp_dir(f"{adapter_label}_inline_soft_filter")
                try:
                    scenario_id = f"sc_{adapter_label}_inline_soft_filter"
                    _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)

                    run_result = runner(
                        scenario_id,
                        mode=mode,
                        task_text="Exercise inline artifact parser/filter handoff.",
                        agent_output=agent_output,
                        adapter_name=adapter_name,
                        artifact_filter_mode="soft",
                        repo_root=repo_root,
                        overwrite_existing_artifacts=True,
                    )

                    events = read_events(run_result["event_log_path"])
                    telemetry = _extract_task_completed_artifact_generation(events)
                    self.assertEqual(telemetry["parser_outcome"], "valid")
                    filter_telemetry = _extract_task_completed_artifact_filter(events)
                    self.assertEqual(filter_telemetry["status"], "evaluated")
                    self.assertEqual(filter_telemetry["raw_verdict"], "ACCEPT")
                    self.assertEqual(_count_event_type(events, "artifact_suggested"), 1)
                finally:
                    shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapter_multi_type_artifacts_emit_events_and_reach_filter(self) -> None:
        repo_root = _workspace_temp_dir("multi_type_events_filter")
        try:
            scenario_id = "sc_multi_type_events_filter"
            _build_minimal_adapter_repo(repo_root, scenario_id=scenario_id)
            agent_output = (
                "Final Answer: done\n"
                "Artifact Suggestion:\n"
                + json.dumps(
                    {
                        "TaskCard": {
                            "id": "clarify_goal",
                            "summary": "Clarify durable task goals before solving ambiguous requests.",
                        },
                        "DecisionCard": {
                            "id": "choose_boundary_rule",
                            "summary": "Use boundary-trigger rules before applying cyclic state movement.",
                        },
                        "ConstraintCard": {
                            "id": "never_skip_boundary",
                            "summary": "Never skip a checkable boundary trigger during cyclic movement.",
                        },
                        "ProcedureCard": {
                            "id": "apply_boundary_workflow",
                            "summary": "Check boundary, apply trigger, then advance cyclic state.",
                        },
                    }
                )
            )

            run_result = run_scenario(
                scenario_id,
                mode=BASELINE,
                task_text="Exercise multi-type artifact parser/filter handoff.",
                agent_output=agent_output,
                adapter_name=ADAPTER_NAME,
                artifact_filter_mode="soft",
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            events = read_events(run_result["event_log_path"])
            telemetry = _extract_task_completed_artifact_generation(events)
            self.assertEqual(telemetry["parser_outcome"], "valid")
            self.assertEqual(telemetry["artifact_proposed_count"], 4)
            self.assertEqual(telemetry["per_type"]["TaskCard"]["parser_outcome"], "valid")
            self.assertEqual(telemetry["per_type"]["DecisionCard"]["parser_outcome"], "valid")
            self.assertEqual(telemetry["per_type"]["ConstraintCard"]["parser_outcome"], "valid")
            self.assertEqual(telemetry["per_type"]["ProcedureCard"]["parser_outcome"], "valid")

            artifact_events = [
                event for event in events if event["event_type"] == "artifact_suggested"
            ]
            self.assertEqual(
                [event["payload"]["artifact_type"] for event in artifact_events],
                ["task", "decision", "constraint", "procedure"],
            )
            filter_telemetry = _extract_task_completed_artifact_filter(events)
            self.assertEqual(len(filter_telemetry["items"]), 4)
            self.assertTrue(all(item["raw_verdict"] == "ACCEPT" for item in filter_telemetry["items"]))
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_gemini_executor_uses_same_retry_policy_for_503_as_429(self) -> None:
        retry_options = gemini_executor_module._build_http_retry_options()

        self.assertEqual(
            retry_options.attempts,
            gemini_executor_module.GEMINI_HTTP_RETRY_ATTEMPTS,
        )
        self.assertEqual(
            retry_options.http_status_codes,
            [429, 503],
        )

    def test_gemini_executor_429_emits_warning_and_retries(self) -> None:
        executor = gemini_executor_module.GeminiExecutor(
            config=gemini_executor_module.ExecutionConfig(model="gemini-flash-lite-latest"),
            api_key="test-key",
        )
        error = gemini_errors.ClientError(
            429,
            {
                "error": {
                    "code": 429,
                    "message": "Rate limit exceeded.",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )

        def _raise_429(*, model: str, contents: str, config: object) -> object:
            raise error

        executor._client = SimpleNamespace(
            models=SimpleNamespace(generate_content=_raise_429)
        )

        with self.assertLogs(gemini_executor_module.logger.name, level="WARNING") as captured_logs:
            with self.assertRaisesRegex(
                RuntimeError,
                "retrying after 429 RESOURCE_EXHAUSTED .* failed after 1 retry attempt",
            ) as captured_error:
                executor.execute("Prompt body", timeout_seconds=30)

        self.assertEqual(len(captured_logs.output), 1)
        self.assertIn(
            "Gemini request rate-limited (429 RESOURCE_EXHAUSTED). Retrying with backoff.",
            captured_logs.output[0],
        )
        self.assertIn("retrying after 429 RESOURCE_EXHAUSTED", str(captured_error.exception))

    def test_gemini_executor_503_emits_warning_and_retries(self) -> None:
        executor = gemini_executor_module.GeminiExecutor(
            config=gemini_executor_module.ExecutionConfig(model="gemini-flash-lite-latest"),
            api_key="test-key",
        )

        captured: dict[str, object] = {}
        error = gemini_errors.ServerError(
            503,
            {
                "error": {
                    "code": 503,
                    "message": "This model is currently experiencing high demand.",
                    "status": "UNAVAILABLE",
                }
            },
        )

        def _raise_503(*, model: str, contents: str, config: object) -> object:
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            raise error

        executor._client = SimpleNamespace(
            models=SimpleNamespace(generate_content=_raise_503)
        )

        with self.assertLogs(gemini_executor_module.logger.name, level="WARNING") as captured_logs:
            with self.assertRaisesRegex(
                RuntimeError,
                "retrying after 503 UNAVAILABLE .* failed after 1 retry attempt",
            ) as captured_error:
                executor.execute("Prompt body", timeout_seconds=30)

        retry_options = captured["config"].http_options.retry_options
        self.assertEqual(
            retry_options.attempts,
            gemini_executor_module.GEMINI_HTTP_RETRY_ATTEMPTS,
        )
        self.assertEqual(retry_options.http_status_codes, [429, 503])
        self.assertEqual(len(captured_logs.output), 1)
        self.assertIn(
            "Gemini service unavailable (503 UNAVAILABLE). Retrying. Possible temporary overload.",
            captured_logs.output[0],
        )
        self.assertIn("retrying after 503 UNAVAILABLE", str(captured_error.exception))

    def test_gemini_executor_504_emits_warning_and_does_not_retry(self) -> None:
        executor = gemini_executor_module.GeminiExecutor(
            config=gemini_executor_module.ExecutionConfig(model="gemini-flash-lite-latest"),
            api_key="test-key",
        )
        error = gemini_errors.ServerError(
            504,
            {
                "error": {
                    "code": 504,
                    "message": "Deadline expired before operation could complete.",
                    "status": "DEADLINE_EXCEEDED",
                }
            },
        )

        def _raise_504(*, model: str, contents: str, config: object) -> object:
            raise error

        executor._client = SimpleNamespace(
            models=SimpleNamespace(generate_content=_raise_504)
        )

        with self.assertLogs(gemini_executor_module.logger.name, level="WARNING") as captured_logs:
            with self.assertRaises(gemini_errors.ServerError):
                executor.execute("Prompt body", timeout_seconds=30)

        self.assertEqual(len(captured_logs.output), 1)
        self.assertIn(
            "Gemini request exceeded timeout_seconds (504 DEADLINE_EXCEEDED).",
            captured_logs.output[0],
        )
        self.assertIn("Consider increasing timeout_seconds or simplifying the scenario.", captured_logs.output[0])

    def test_gemini_executor_error_classification_mapping_correct(self) -> None:
        rate_limit = gemini_errors.ClientError(
            429,
            {"error": {"code": 429, "message": "busy", "status": "RESOURCE_EXHAUSTED"}},
        )
        unavailable_by_code = gemini_errors.ServerError(
            503,
            {"error": {"code": 503, "message": "slow", "status": "INTERNAL"}},
        )
        unavailable_by_status = gemini_errors.ServerError(
            500,
            {"error": {"code": 500, "message": "busy", "status": "UNAVAILABLE"}},
        )
        deadline_by_code = gemini_errors.ServerError(
            504,
            {"error": {"code": 504, "message": "slow", "status": "INTERNAL"}},
        )
        deadline_by_status = gemini_errors.ServerError(
            500,
            {"error": {"code": 500, "message": "slow", "status": "DEADLINE_EXCEEDED"}},
        )
        deadline_by_message = gemini_errors.ServerError(
            500,
            {"error": {"code": 500, "message": "Deadline expired while waiting.", "status": "INTERNAL"}},
        )
        other = RuntimeError("not provider")

        self.assertEqual(
            gemini_executor_module._classify_provider_error(rate_limit),
            {"type": "rate_limit", "retryable": True},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(unavailable_by_code),
            {"type": "unavailable", "retryable": True},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(unavailable_by_status),
            {"type": "unavailable", "retryable": True},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(deadline_by_code),
            {"type": "deadline_exceeded", "retryable": False},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(deadline_by_status),
            {"type": "deadline_exceeded", "retryable": False},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(deadline_by_message),
            {"type": "deadline_exceeded", "retryable": False},
        )
        self.assertEqual(
            gemini_executor_module._classify_provider_error(other),
            {"type": "other", "retryable": False},
        )

    def test_gemini_executor_504_failure_reason_text_remains_unchanged(self) -> None:
        executor = gemini_executor_module.GeminiExecutor(
            config=gemini_executor_module.ExecutionConfig(model="gemini-flash-lite-latest"),
            api_key="test-key",
        )
        error = gemini_errors.ServerError(
            504,
            {
                "error": {
                    "code": 504,
                    "message": "Deadline expired before operation could complete.",
                    "status": "DEADLINE_EXCEEDED",
                }
            },
        )

        def _raise_504(*, model: str, contents: str, config: object) -> object:
            raise error

        executor._client = SimpleNamespace(
            models=SimpleNamespace(generate_content=_raise_504)
        )

        with self.assertLogs(gemini_executor_module.logger.name, level="WARNING"):
            with self.assertRaises(gemini_errors.ServerError) as captured_error:
                executor.execute("Prompt body", timeout_seconds=30)

        self.assertEqual(str(captured_error.exception), str(error))

    def test_run_single_surfaces_raw_token_usage_from_adapter_result(self) -> None:
        repo_root = _workspace_temp_dir("run_single_tokens")
        try:
            backend = run_benchmarks_module.BackendSelection(
                backend="gemini",
                adapter_name="gemini",
                run_scenario=lambda scenario_id, **kwargs: {
                    "event_log_path": repo_root / "probe.events.jsonl",
                    "token_usage": {
                        "prompt_tokens": 120,
                        "output_tokens": 45,
                        "total_tokens": 165,
                    },
                },
                get_benchmark_agent_metadata=lambda **kwargs: {
                    "adapter": "gemini",
                    "full_agent_name": "Gemini",
                    "agent_model": "gemini-flash-lite-latest",
                },
            )

            with patch.object(run_benchmarks_module, "derive_result_artifact") as derive_mock, patch.object(
                run_benchmarks_module,
                "_is_quota_exhausted_event_log",
                return_value=False,
            ):
                summary = run_benchmarks_module.run_single(
                    SCENARIO_ID,
                    BASELINE,
                    repo_root=repo_root,
                    backend=backend,
                )

            derive_mock.assert_called_once()
            self.assertEqual(summary.prompt_tokens, 120)
            self.assertEqual(summary.output_tokens, 45)
            self.assertEqual(summary.total_tokens, 165)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_run_benchmarks_cli_accepts_artifact_generation_and_filter_flags(self) -> None:
        for generator_mode in ("legacy", "constrained", "shadow"):
            with self.subTest(generator_mode=generator_mode):
                with patch.object(
                    sys,
                    "argv",
                    [
                        "run_benchmarks.py",
                        "--artifact-generator-mode",
                        generator_mode,
                        "--artifact-filter-mode",
                        "soft",
                        "--working-context-format",
                        "relevant_summaries",
                    ],
                ):
                    args = run_benchmarks_module.parse_args()

                self.assertEqual(args.artifact_generator_mode, generator_mode)
                self.assertEqual(args.artifact_filter_mode, "soft")
                self.assertEqual(args.working_context_format, "relevant_summaries")

    def test_run_benchmarks_cli_artifact_flags_default_to_existing_behavior(self) -> None:
        with patch.object(sys, "argv", ["run_benchmarks.py"]):
            args = run_benchmarks_module.parse_args()

        self.assertIsNone(args.artifact_generator_mode)
        self.assertIsNone(args.artifact_filter_mode)
        self.assertIsNone(args.working_context_format)

    def test_run_benchmarks_cli_rejects_invalid_artifact_modes(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["run_benchmarks.py", "--artifact-generator-mode", "experimental"],
        ):
            with self.assertRaises(SystemExit):
                run_benchmarks_module.parse_args()

        with patch.object(
            sys,
            "argv",
            ["run_benchmarks.py", "--artifact-filter-mode", "hard"],
        ):
            with self.assertRaises(SystemExit):
                run_benchmarks_module.parse_args()

        with patch.object(
            sys,
            "argv",
            ["run_benchmarks.py", "--working-context-format", "verbose"],
        ):
            with self.assertRaises(SystemExit):
                run_benchmarks_module.parse_args()

    def test_load_profile_accepts_artifact_and_context_modes(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profile_artifact_context_modes")
        try:
            profile_path = temp_profiles_dir / "modes.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "modes",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "runtime", "ref": None},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "working_context_format": "relevant_summaries",
                        "artifact_generator_mode": "constrained",
                        "artifact_filter_mode": "soft",
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                profile = run_benchmarks_module.load_profile("modes")

            self.assertEqual(profile.working_context_format, "relevant_summaries")
            self.assertEqual(profile.artifact_generator_mode, "constrained")
            self.assertEqual(profile.artifact_filter_mode, "soft")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_cli_artifact_and_context_modes_override_profile_values(self) -> None:
        captured_kwargs: dict[str, object] = {}
        fake_profile = SimpleNamespace(
            name="profile_modes",
            backend="gemini",
            model="gemini-flash-lite-latest",
            scenario_subset=(SCENARIO_ID,),
            diagnostic_modes=SimpleNamespace(
                pr_ephemeral=False,
                post_run_artifact_harvest=False,
            ),
            brain_mode="accumulative",
            brain_in=SimpleNamespace(type="runtime"),
            brain_out=SimpleNamespace(mode="snapshot"),
            inter_scenario_delay_seconds=1,
            showcase=SCENARIO_ID,
            mode_to_key_mapping="strict",
            timeout_seconds=20,
            on_429_first="wait_30s_retry_once",
            on_429_second="stop_run",
            working_context_format="relevant_summaries",
            artifact_generator_mode="constrained",
            artifact_filter_mode="soft",
        )
        fake_backend = SimpleNamespace(
            backend="gemini",
            adapter_name="gemini",
            get_benchmark_agent_metadata=lambda **_: {
                "adapter": "gemini",
                "full_agent_name": "Gemini",
                "agent_model": "gemini-flash-lite-latest",
            },
        )

        with patch.object(
            run_benchmarks_module,
            "parse_args",
            return_value=SimpleNamespace(
                profile="profile_modes",
                backend=None,
                artifact_generator_mode="shadow",
                artifact_filter_mode="off",
                working_context_format="reference_only",
            ),
        ), patch.object(
            run_benchmarks_module,
            "load_profile",
            return_value=fake_profile,
        ), patch.object(
            run_benchmarks_module,
            "resolve_backend",
            return_value=fake_backend,
        ), patch.object(run_benchmarks_module, "apply_pre_run_brain_lifecycle"), patch.object(
            run_benchmarks_module,
            "clean_temporary_benchmark_results",
        ), patch.object(run_benchmarks_module, "run_preflight"), patch.object(
            run_benchmarks_module,
            "write_resolved_execution_artifacts",
            return_value=[],
        ), patch.object(
            run_benchmarks_module,
            "run_all",
            side_effect=lambda *args, **kwargs: captured_kwargs.update(kwargs)
            or run_benchmarks_module.RunExecutionState(
                quota_stop_reason=None,
                total_429_count=0,
            ),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_layer_manifest",
            return_value=Path("scenario_layers.json"),
        ), patch.object(
            run_benchmarks_module,
            "write_scenario_interpretation_support_manifest",
            return_value=Path("scenario_interpretation_support.json"),
        ), patch.object(run_benchmarks_module, "run_post_processing"), patch.object(
            run_benchmarks_module,
            "generate_retention_artifacts_for_run",
            return_value=[],
        ), patch.object(run_benchmarks_module, "apply_post_run_brain_lifecycle"), patch.object(
            run_benchmarks_module,
            "run_post_run_artifact_harvest",
            return_value=Path(HARVEST_REPORT_FILENAME),
        ), patch.object(run_benchmarks_module, "build_run_id", return_value="test_run"), patch(
            "builtins.print"
        ):
            run_benchmarks_module.main()

        self.assertEqual(captured_kwargs["artifact_generator_mode"], "shadow")
        self.assertEqual(captured_kwargs["artifact_filter_mode"], "off")
        self.assertEqual(captured_kwargs["working_context_format"], "reference_only")

    def test_run_single_passes_artifact_config_to_selected_adapter(self) -> None:
        repo_root = _workspace_temp_dir("run_single_artifact_config")
        captured_kwargs: dict[str, object] = {}
        try:
            def _capture_run_scenario(scenario_id: str, **kwargs: object) -> dict[str, object]:
                captured_kwargs.update(kwargs)
                return {
                    "event_log_path": repo_root / "probe.events.jsonl",
                    "token_usage": {
                        "prompt_tokens": None,
                        "output_tokens": None,
                        "total_tokens": None,
                    },
                }

            backend = run_benchmarks_module.BackendSelection(
                backend="gemini",
                adapter_name="gemini",
                run_scenario=_capture_run_scenario,
                get_benchmark_agent_metadata=lambda **kwargs: {
                    "adapter": "gemini",
                    "full_agent_name": "Gemini",
                    "agent_model": "gemini-flash-lite-latest",
                },
            )

            with patch.object(run_benchmarks_module, "derive_result_artifact"), patch.object(
                run_benchmarks_module,
                "_is_quota_exhausted_event_log",
                return_value=False,
            ):
                run_benchmarks_module.run_single(
                    SCENARIO_ID,
                    BASELINE,
                    repo_root=repo_root,
                    backend=backend,
                    artifact_generator_mode="shadow",
                    working_context_format="relevant_summaries",
                    artifact_filter_mode="soft",
                )

            self.assertEqual(captured_kwargs["artifact_generator_mode"], "shadow")
            self.assertEqual(captured_kwargs["working_context_format"], "relevant_summaries")
            self.assertEqual(captured_kwargs["artifact_filter_mode"], "soft")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_run_single_artifact_config_defaults_preserve_existing_behavior(self) -> None:
        repo_root = _workspace_temp_dir("run_single_artifact_defaults")
        captured_kwargs: dict[str, object] = {}
        try:
            def _capture_run_scenario(scenario_id: str, **kwargs: object) -> dict[str, object]:
                captured_kwargs.update(kwargs)
                return {
                    "event_log_path": repo_root / "probe.events.jsonl",
                    "token_usage": {},
                }

            backend = run_benchmarks_module.BackendSelection(
                backend="gemini",
                adapter_name="gemini",
                run_scenario=_capture_run_scenario,
                get_benchmark_agent_metadata=lambda **kwargs: {
                    "adapter": "gemini",
                    "full_agent_name": "Gemini",
                    "agent_model": "gemini-flash-lite-latest",
                },
            )

            with patch.object(run_benchmarks_module, "derive_result_artifact"), patch.object(
                run_benchmarks_module,
                "_is_quota_exhausted_event_log",
                return_value=False,
            ):
                run_benchmarks_module.run_single(
                    SCENARIO_ID,
                    BASELINE,
                    repo_root=repo_root,
                    backend=backend,
                )

            self.assertEqual(captured_kwargs["artifact_generator_mode"], "legacy")
            self.assertEqual(captured_kwargs["working_context_format"], "reference_only")
            self.assertEqual(captured_kwargs["artifact_filter_mode"], "off")
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_load_profile_accepts_seeded_and_runtime_inputs(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_supported_inputs")
        try:
            seeded_path = temp_profiles_dir / "seeded.json"
            seeded_path.write_text(
                json.dumps(
                    {
                        "name": "seeded",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "seeded", "ref": None},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            runtime_path = temp_profiles_dir / "runtime.json"
            runtime_path.write_text(
                json.dumps(
                    {
                        "name": "runtime",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "runtime", "ref": None},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                seeded_profile = run_benchmarks_module.load_profile("seeded")
                runtime_profile = run_benchmarks_module.load_profile("runtime")

            self.assertEqual(seeded_profile.brain_in.type, "seeded")
            self.assertEqual(runtime_profile.brain_in.type, "runtime")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_load_profile_accepts_snapshot_output_for_supported_brain_modes(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_snapshot_output")
        try:
            for profile_name, brain_mode in (
                ("accumulative_snapshot", "accumulative"),
                ("static_snapshot", "static"),
            ):
                profile_path = temp_profiles_dir / f"{profile_name}.json"
                profile_path.write_text(
                    json.dumps(
                        {
                            "name": profile_name,
                            "backend": "gemini",
                            "model": "gemini-flash-lite-latest",
                            "brain_mode": brain_mode,
                            "brain_in": {"type": "runtime", "ref": None},
                            "brain_out": {"mode": "snapshot", "ref": None},
                            "scenario_subset": [SCENARIO_ID],
                            "showcase": SCENARIO_ID,
                            "mode_to_key_mapping": "strict",
                            "execution": {
                                "timeout_seconds": 20,
                                "inter_scenario_delay_seconds": 1,
                            },
                            "quota_policy": {
                                "on_429_first": "wait_30s_retry_once",
                                "on_429_second": "stop_run",
                            },
                            "purpose": "test",
                        },
                        indent=2,
                    ) + "\n",
                    encoding="utf-8",
                )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                accumulative_profile = run_benchmarks_module.load_profile(
                    "accumulative_snapshot"
                )
                static_profile = run_benchmarks_module.load_profile("static_snapshot")

            self.assertEqual(accumulative_profile.brain_out.mode, "snapshot")
            self.assertEqual(static_profile.brain_out.mode, "snapshot")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_load_profile_rejects_unsupported_lifecycle_cases(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_invalid")
        try:
            profile_path = temp_profiles_dir / "invalid.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "invalid",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "snapshot", "ref": None},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                with self.assertRaisesRegex(ValueError, "unsupported ordinary-run brain_in.type"):
                    run_benchmarks_module.load_profile("invalid")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_load_profile_rejects_non_null_brain_ref_for_this_step(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_invalid_ref")
        try:
            profile_path = temp_profiles_dir / "invalid_ref.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "invalid_ref",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "seeded", "ref": "seed-a"},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                with self.assertRaisesRegex(ValueError, "brain_in.ref"):
                    run_benchmarks_module.load_profile("invalid_ref")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_load_profile_rejects_non_null_brain_out_ref_for_this_step(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_invalid_out_ref")
        try:
            profile_path = temp_profiles_dir / "invalid_out_ref.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "invalid_out_ref",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "accumulative",
                        "brain_in": {"type": "empty", "ref": None},
                        "brain_out": {"mode": "continue", "ref": "snapshot-a"},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                with self.assertRaisesRegex(ValueError, "brain_out.ref"):
                    run_benchmarks_module.load_profile("invalid_out_ref")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_load_profile_rejects_invalid_brain_mode_and_out_pairing(self) -> None:
        temp_profiles_dir = _workspace_temp_dir("profiles_invalid_pairing")
        try:
            profile_path = temp_profiles_dir / "invalid_pairing.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "invalid_pairing",
                        "backend": "gemini",
                        "model": "gemini-flash-lite-latest",
                        "brain_mode": "static",
                        "brain_in": {"type": "empty", "ref": None},
                        "brain_out": {"mode": "continue", "ref": None},
                        "scenario_subset": [SCENARIO_ID],
                        "showcase": SCENARIO_ID,
                        "mode_to_key_mapping": "strict",
                        "execution": {
                            "timeout_seconds": 20,
                            "inter_scenario_delay_seconds": 1,
                        },
                        "quota_policy": {
                            "on_429_first": "wait_30s_retry_once",
                            "on_429_second": "stop_run",
                        },
                        "purpose": "test",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            with patch.object(run_benchmarks_module, "PROFILES_DIR", temp_profiles_dir):
                with self.assertRaisesRegex(
                    ValueError,
                    "brain_mode='static' requires brain_out.mode in",
                ):
                    run_benchmarks_module.load_profile("invalid_pairing")
        finally:
            shutil.rmtree(temp_profiles_dir, ignore_errors=True)

    def test_pre_run_brain_lifecycle_uses_storage_reset_from_empty(self) -> None:
        repo_root = _workspace_temp_dir("runner_pre_lifecycle")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            (runtime_root / "brain" / "decisions" / "stale.json").write_text(
                json.dumps({"id": "stale", "type": "decision", "summary": "stale"}, indent=2) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["stale"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            run_benchmarks_module.apply_pre_run_brain_lifecycle(repo_root)

            self.assertFalse((runtime_root / "brain" / "decisions" / "stale.json").exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8")),
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_pre_run_brain_lifecycle_seeded_recreates_runtime_and_preserves_seeded(self) -> None:
        repo_root = _workspace_temp_dir("runner_pre_seeded")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            seeded_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "seeded"

            seeded_artifact = seeded_root / "brain" / "decisions" / "decision_seed.json"
            seeded_artifact.write_text(
                json.dumps({"id": "decision_seed", "type": "decision", "summary": "seed"}, indent=2) + "\n",
                encoding="utf-8",
            )
            (seeded_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_seed"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            stale_runtime = runtime_root / "brain" / "decisions" / "stale.json"
            stale_runtime.write_text(
                json.dumps({"id": "stale", "type": "decision", "summary": "stale"}, indent=2) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="seeded", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="continue", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_benchmarks_module.apply_pre_run_brain_lifecycle(repo_root, profile=profile)

            self.assertFalse(stale_runtime.exists())
            self.assertTrue((runtime_root / "brain" / "decisions" / "decision_seed.json").exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8"))["decisions"],
                ["decision_seed"],
            )
            self.assertTrue(seeded_artifact.exists())
            self.assertEqual(
                json.loads((seeded_root / "views" / "working_context.json").read_text(encoding="utf-8"))["decisions"],
                ["decision_seed"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_pre_run_brain_lifecycle_runtime_reuses_existing_runtime_state(self) -> None:
        repo_root = _workspace_temp_dir("runner_pre_runtime")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            runtime_artifact = runtime_root / "brain" / "decisions" / "decision_runtime.json"
            runtime_artifact.write_text(
                json.dumps(
                    {"id": "decision_runtime", "type": "decision", "summary": "runtime"},
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_runtime"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="continue", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_benchmarks_module.apply_pre_run_brain_lifecycle(repo_root, profile=profile)

            self.assertTrue(runtime_artifact.exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8"))["decisions"],
                ["decision_runtime"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_brain_lifecycle_continue_preserves_runtime_state(self) -> None:
        repo_root = _workspace_temp_dir("runner_post_continue")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            persisted = runtime_root / "brain" / "decisions" / "decision_keep.json"
            persisted.write_text(
                json.dumps({"id": "decision_keep", "type": "decision", "summary": "keep"}, indent=2) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_keep"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="continue", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_benchmarks_module.apply_post_run_brain_lifecycle(
                repo_root,
                run_id="test_continue",
                profile=profile,
            )

            self.assertTrue(persisted.exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8"))["decisions"],
                ["decision_keep"],
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_brain_lifecycle_empty_resets_runtime_state(self) -> None:
        repo_root = _workspace_temp_dir("runner_post_empty")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            persisted = runtime_root / "brain" / "decisions" / "decision_reset.json"
            persisted.write_text(
                json.dumps({"id": "decision_reset", "type": "decision", "summary": "reset"}, indent=2) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_reset"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="static",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="empty", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_benchmarks_module.apply_post_run_brain_lifecycle(
                repo_root,
                run_id="test_empty",
                profile=profile,
            )

            self.assertFalse(persisted.exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8")),
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_brain_lifecycle_snapshot_accumulative_preserves_runtime(self) -> None:
        repo_root = _workspace_temp_dir("rpsa")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            persisted = runtime_root / "brain" / "decisions" / "decision_snapshot.json"
            persisted.write_text(
                json.dumps(
                    {"id": "decision_snapshot", "type": "decision", "summary": "snapshot"},
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_snapshot"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="snapshot", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_id = "snapa"
            run_benchmarks_module.apply_post_run_brain_lifecycle(
                repo_root,
                run_id=run_id,
                profile=profile,
            )

            snapshot_root = (
                repo_root / "reasoning_brain_storage" / "snapshots" / run_id
            )
            self.assertTrue(snapshot_root.is_dir())
            self.assertTrue(persisted.exists())
            self.assertEqual(
                json.loads(
                    (snapshot_root / "views" / "working_context.json").read_text(
                        encoding="utf-8"
                    )
                )["decisions"],
                ["decision_snapshot"],
            )
            self.assertTrue(
                (snapshot_root / "brain" / "decisions" / "decision_snapshot.json").is_file()
            )
            self.assertEqual(snapshot_root.name, run_id)
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_brain_lifecycle_snapshot_static_captures_then_resets_runtime(self) -> None:
        repo_root = _workspace_temp_dir("rpss")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            persisted = runtime_root / "brain" / "decisions" / "decision_before_reset.json"
            persisted.write_text(
                json.dumps(
                    {
                        "id": "decision_before_reset",
                        "type": "decision",
                        "summary": "capture before reset",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            (runtime_root / "views" / "working_context.json").write_text(
                json.dumps(
                    {
                        "active_task": None,
                        "constraints": [],
                        "decisions": ["decision_before_reset"],
                        "open_issues": [],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="static",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="snapshot", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_id = "snaps"
            run_benchmarks_module.apply_post_run_brain_lifecycle(
                repo_root,
                run_id=run_id,
                profile=profile,
            )

            snapshot_root = (
                repo_root / "reasoning_brain_storage" / "snapshots" / run_id
            )
            self.assertTrue(snapshot_root.is_dir())
            self.assertEqual(
                json.loads(
                    (snapshot_root / "views" / "working_context.json").read_text(
                        encoding="utf-8"
                    )
                )["decisions"],
                ["decision_before_reset"],
            )
            self.assertTrue(
                (snapshot_root / "brain" / "decisions" / "decision_before_reset.json").is_file()
            )
            self.assertFalse(persisted.exists())
            self.assertEqual(
                json.loads((runtime_root / "views" / "working_context.json").read_text(encoding="utf-8")),
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": [],
                    "open_issues": [],
                },
            )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_post_run_brain_lifecycle_snapshot_fails_loudly_on_collision(self) -> None:
        repo_root = _workspace_temp_dir("rpsc")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            (runtime_root / "brain" / "decisions" / "decision_collision.json").write_text(
                json.dumps(
                    {
                        "id": "decision_collision",
                        "type": "decision",
                        "summary": "collision",
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            profile = run_benchmarks_module.BenchmarkProfile(
                diagnostic_modes=run_benchmarks_module.DiagnosticModesPolicy(pr_ephemeral=False),
                brain_mode="accumulative",
                brain_in=run_benchmarks_module.BrainInPolicy(type="runtime", ref=None),
                brain_out=run_benchmarks_module.BrainOutPolicy(mode="snapshot", ref=None),
                name="test",
                backend="gemini",
                model="gemini-flash-lite-latest",
                scenario_subset=(SCENARIO_ID,),
                showcase=SCENARIO_ID,
                mode_to_key_mapping="strict",
                timeout_seconds=20,
                inter_scenario_delay_seconds=1,
                on_429_first="wait_30s_retry_once",
                on_429_second="stop_run",
                purpose="test",
            )

            run_id = "snapc"
            snapshot_root = (
                repo_root / "reasoning_brain_storage" / "snapshots" / run_id
            )
            snapshot_root.mkdir(parents=True)

            with self.assertRaisesRegex(Exception, "already exists"):
                run_benchmarks_module.apply_post_run_brain_lifecycle(
                    repo_root,
                    run_id=run_id,
                    profile=profile,
                )
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_result_cleanup_remains_separate_from_brain_lifecycle(self) -> None:
        repo_root = _workspace_temp_dir("result_cleanup_only")
        try:
            self._build_profile_lifecycle_repo(repo_root)
            runtime_root = repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime"
            persisted = runtime_root / "brain" / "decisions" / "decision_survives.json"
            persisted.write_text(
                json.dumps(
                    {"id": "decision_survives", "type": "decision", "summary": "survives"},
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                artifact_path = repo_root / "benchmarks" / "results" / mode / f"{SCENARIO_ID}{TRACE_LOG_SUFFIX}"
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text("temporary\n", encoding="utf-8")

            clean_temporary_benchmark_results(repo_root)

            self.assertTrue(persisted.exists())
            for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
                mode_dir = repo_root / "benchmarks" / "results" / mode
                self.assertEqual(list(mode_dir.iterdir()), [])
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)

    def test_adapter_emits_events_and_logs_before_event_only_result_derivation(self) -> None:
        repo_root = _workspace_temp_dir("adapter_boundary")
        try:
            scenario_id = "sc_phase5_boundary_probe"

            (repo_root / "benchmarks" / "scenarios").mkdir(parents=True)
            (repo_root / "benchmarks" / "results").mkdir(parents=True)
            (repo_root / "benchmarks" / "reports").mkdir(parents=True)

            (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.md").write_text(
                "# Boundary Probe\n",
                encoding="utf-8",
            )
            (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.json").write_text(
                json.dumps(
                    {
                        "scenario_id": scenario_id,
                        "scenario_name": "Boundary Probe",
                        "scenario_type": "contract_test",
                        "description": "Minimal scenario for boundary enforcement.",
                        "steps": [
                            {
                                "step_id": "step_1",
                                "instruction": "Follow the probe instruction.",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.metadata.json").write_text(
                json.dumps(
                    {
                        "contract_version": "1.4",
                        "identity": {"scenario_id": scenario_id},
                        "migration_lock": {
                            "execution_contract": False,
                            "interpretation_support": False,
                            "interpretation_contract": False,
                            "retention_contract": True,
                            "ghost_contract": True,
                            "correctness_contract": True,
                        },
                        "execution_contract": {
                            "scenario_mode": "standard",
                            "showcase": False,
                            "status": "stable",
                            "return_to_origin": False,
                        },
                        "interpretation_support": {
                            "supports_retention": False,
                            "supports_correctness": False,
                            "supports_ghost": False,
                            "supports_temporal_ghost": False,
                            "trajectory_readiness": "unsupported",
                        },
                        "interpretation_contract": {
                            "interpretation_variant": "none",
                            "layer_support": {
                                "retention": "unsupported",
                                "correctness": "unsupported",
                                "ghost": "unsupported",
                            },
                        },
                        "retention_contract": None,
                        "ghost_contract": None,
                        "correctness_contract": None,
                        "trajectory_contract": None,
                        "expected_ready": False,
                        "expected_file": None,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            run_result = run_scenario(
                scenario_id,
                mode=BASELINE,
                task_text="Execute the boundary probe.",
                agent_output="",
                adapter_name=ADAPTER_NAME,
                repo_root=repo_root,
                overwrite_existing_artifacts=True,
            )

            self.assertTrue(run_result["event_log_path"].is_file())
            self.assertTrue(run_result["raw_log_path"].is_file())

            result_path = repo_root / "benchmarks" / "results" / BASELINE / (
                f"{scenario_id}{RESULT_JSON_SUFFIX}"
            )
            self.assertFalse(result_path.exists())

            derive_result_artifact(
                run_result["event_log_path"],
                output_path=result_path,
                adapter_name=ADAPTER_NAME,
                overwrite=True,
            )
            self.assertTrue(result_path.is_file())
        finally:
            shutil.rmtree(repo_root, ignore_errors=True)


def _extract_task_completed_artifact_generation(
    events: list[dict[str, object]],
) -> dict[str, object]:
    payload = _extract_task_completed_payload(events)
    artifact_generation = payload.get("artifact_generation")
    if not isinstance(artifact_generation, dict):
        raise AssertionError("task_completed payload must include artifact_generation telemetry")

    return artifact_generation


def _extract_task_completed_artifact_generation_shadow(
    events: list[dict[str, object]],
) -> dict[str, object]:
    payload = _extract_task_completed_payload(events)
    artifact_generation_shadow = payload.get("artifact_generation_shadow")
    if not isinstance(artifact_generation_shadow, dict):
        raise AssertionError(
            "task_completed payload must include artifact_generation_shadow telemetry"
        )

    return artifact_generation_shadow


def _extract_task_completed_artifact_filter_shadow(
    events: list[dict[str, object]],
) -> dict[str, object]:
    payload = _extract_task_completed_payload(events)
    artifact_filter_shadow = payload.get("artifact_filter_shadow")
    if not isinstance(artifact_filter_shadow, dict):
        raise AssertionError("task_completed payload must include artifact_filter_shadow telemetry")

    return artifact_filter_shadow


def _extract_task_completed_artifact_filter(
    events: list[dict[str, object]],
) -> dict[str, object]:
    payload = _extract_task_completed_payload(events)
    artifact_filter = payload.get("artifact_filter")
    if not isinstance(artifact_filter, dict):
        raise AssertionError("task_completed payload must include artifact_filter telemetry")

    return artifact_filter


def _extract_task_completed_payload(events: list[dict[str, object]]) -> dict[str, object]:
    completed_events = [
        event for event in events if event.get("event_type") == "task_completed"
    ]
    if len(completed_events) != 1:
        raise AssertionError(f"expected exactly one task_completed event, got {len(completed_events)}")

    payload = completed_events[0].get("payload")
    if not isinstance(payload, dict):
        raise AssertionError("task_completed payload must be a dict")

    return payload


def _count_event_type(events: list[dict[str, object]], event_type: str) -> int:
    return sum(1 for event in events if event.get("event_type") == event_type)


def _build_baseline_events() -> list[dict[str, object]]:
    return [
        _event("task_started", BASELINE, 1),
        _event(
            "reasoning_step",
            BASELINE,
            2,
            payload={"task_text": "Execute the baseline task.", "execution_phase": "started"},
        ),
        _event(
            "task_completed",
            BASELINE,
            3,
            payload={"success": True, "execution_source": "manual_override"},
        ),
    ]


def _build_emission_only_events(mode: str) -> list[dict[str, object]]:
    return [
        _event("task_started", mode, 1),
        _event("working_context_loaded", mode, 2, payload={"reference_count": 0}),
        _event(
            "reasoning_step",
            mode,
            3,
            payload={"task_text": "Emit one benchmark suggestion.", "execution_phase": "started"},
        ),
        _event(
            "artifact_suggested",
            mode,
            4,
            payload={"artifact_id": "decision_emit", "artifact_type": "decision"},
        ),
        _event(
            "task_completed",
            mode,
            5,
            payload={"success": True, "execution_source": "manual_override"},
        ),
    ]


def _build_reuse_focused_events(mode: str) -> list[dict[str, object]]:
    return [
        _event("task_started", mode, 1),
        _event("working_context_loaded", mode, 2, payload={"reference_count": 1}),
        _event(
            "reasoning_step",
            mode,
            3,
            payload={"task_text": "Reuse the persisted decision.", "execution_phase": "started"},
        ),
        _event(
            "task_completed",
            mode,
            4,
            payload={"success": True, "execution_source": "manual_override"},
        ),
    ]


def _event(
    event_type: str,
    mode: str,
    step_index: int,
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "event_type": event_type,
        "mode": mode,
        "scenario_id": SCENARIO_ID,
        "step_index": step_index,
    }
    if payload is not None:
        event["payload"] = payload
    return event


def _artifact_calibration_completed_event(
    parser_outcome: str,
    *,
    filter_payload: dict[str, object] | None = None,
    shadow_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "success": True,
        "execution_source": "manual_override",
        "artifact_generation": _artifact_generation_payload(parser_outcome),
    }
    if filter_payload is not None:
        payload["artifact_filter"] = filter_payload
    if shadow_payload is not None:
        payload["artifact_generation_shadow"] = shadow_payload
    return _event("task_completed", BASELINE, 3, payload=payload)


def _artifact_generation_payload(parser_outcome: str) -> dict[str, object]:
    return {
        "parser_outcome": parser_outcome,
        "artifact_proposed_count": 1 if parser_outcome == "valid" else 0,
        "none_output_count": 1 if parser_outcome == "none" else 0,
        "malformed_output_count": 1 if parser_outcome == "malformed" else 0,
    }


def _artifact_filter_payload(
    verdict: str,
    *,
    reasons: list[str],
) -> dict[str, object]:
    return {
        "enabled": True,
        "mode": "soft",
        "status": "evaluated",
        "verdict": verdict,
        "reasons": reasons,
        "structural_valid": verdict == "accepted",
        "prohibited_flag": False,
        "duplicate_flag": False,
        "semantic_valid": verdict == "accepted",
        "raw_verdict": "ACCEPT" if verdict == "accepted" else "REJECT",
    }


def _workspace_temp_dir(label: str) -> Path:
    root = REPO_ROOT / "benchmarks" / "tools" / "tests" / "_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{label}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _copy_repo_scenario_bundle(repo_root: Path, scenario_id: str) -> None:
    for suffix in (".json", ".metadata.json", ".md", ".expected.json"):
        source = REPO_ROOT / "benchmarks" / "scenarios" / f"{scenario_id}{suffix}"
        if not source.exists():
            continue
        target = repo_root / "benchmarks" / "scenarios" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _build_minimal_adapter_repo(repo_root: Path, *, scenario_id: str) -> None:
    (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

    (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.md").write_text(
        "# Boundary Probe\n",
        encoding="utf-8",
    )
    (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.json").write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "scenario_name": "Boundary Probe",
                "scenario_type": "contract_test",
                "description": "Minimal scenario for boundary enforcement.",
                "steps": [
                    {
                        "step_id": "step_1",
                        "instruction": "Follow the probe instruction.",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "benchmarks" / "scenarios" / f"{scenario_id}.metadata.json").write_text(
        json.dumps(
            {
                "contract_version": "1.4",
                "identity": {"scenario_id": scenario_id},
                "migration_lock": {
                    "execution_contract": False,
                    "interpretation_support": False,
                    "interpretation_contract": False,
                    "retention_contract": True,
                    "ghost_contract": True,
                    "correctness_contract": True,
                },
                "execution_contract": {
                    "scenario_mode": "standard",
                    "showcase": False,
                    "status": "stable",
                    "return_to_origin": False,
                },
                "interpretation_support": {
                    "supports_retention": False,
                    "supports_correctness": False,
                    "supports_ghost": False,
                    "supports_temporal_ghost": False,
                    "trajectory_readiness": "unsupported",
                },
                "interpretation_contract": {
                    "interpretation_variant": "none",
                    "layer_support": {
                        "retention": "unsupported",
                        "correctness": "unsupported",
                        "ghost": "unsupported",
                    },
                },
                "retention_contract": None,
                "ghost_contract": None,
                "correctness_contract": None,
                "trajectory_contract": None,
                "expected_ready": False,
                "expected_file": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    empty_context = {
        "active_task": None,
        "constraints": [],
        "decisions": [],
        "open_issues": [],
    }
    for brain_root in (
        repo_root / "reasoning_brain_storage" / "templates" / "empty",
        repo_root / "reasoning_brain_storage" / "benchmarks" / "runtime",
        repo_root / "reasoning_brain_storage" / "benchmarks" / "seeded",
    ):
        _create_minimal_brain_root(brain_root, empty_context)


def _write_harvest_event_log(
    repo_root: Path,
    *,
    scenario_id: str,
    mode: str,
    candidate: dict[str, object] | None = None,
    raw_payload: dict[str, object] | None = None,
) -> Path:
    paths = BenchmarkPaths(repo_root=repo_root)
    event_path = result_events_path(paths, mode, scenario_id)
    logger = BenchmarkEventLogger(
        event_log_path=event_path,
        scenario_id=scenario_id,
        mode=mode,
        auto_reset=True,
        allow_overwrite=True,
    )
    logger.log_task_started()
    payload = (
        raw_payload
        if raw_payload is not None
        else {
            "artifact_id": candidate["id"],
            "artifact_type": candidate["type"],
            "artifact_candidate": candidate,
        }
    )
    logger.log_artifact_suggested(payload)
    logger.log_task_completed({"success": True, "execution_source": "manual_override"})
    return event_path


def _build_structural_retention_repo(repo_root: Path) -> None:
    (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

    _copy_repo_scenario_bundle(repo_root, CANONICAL_STRUCTURAL_RETENTION_SCENARIO_ID)


def _build_math_state_loss_repo(repo_root: Path) -> None:
    (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

    _copy_repo_scenario_bundle(repo_root, MATH_STATE_LOSS_SCENARIO_ID)


def _build_sc9_repo(repo_root: Path) -> None:
    (repo_root / "benchmarks" / "scenarios").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "results").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "reports").mkdir(parents=True, exist_ok=True)

    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        (repo_root / "benchmarks" / "results" / mode).mkdir(parents=True, exist_ok=True)

    for scenario_id in ("sc_99_killer_all_scenarios", *SC9_COMPOSITION_SOURCE_SCENARIO_IDS):
        _copy_repo_scenario_bundle(repo_root, scenario_id)


def _write_retention_trace_log(
    repo_root: Path,
    *,
    mode: str,
    scenario_id: str,
    agent_output: str,
) -> Path:
    paths = BenchmarkPaths(repo_root=repo_root)
    trace_path = result_log_path(paths, mode, scenario_id)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(
            [
                "Persistent Reasoning Light Benchmark Log",
                f"scenario_id: {scenario_id}",
                "scenario_name: Structural Retention",
                "scenario_type: structural_retention",
                "adapter: gemini",
                f"mode: {mode}",
                "",
                "Task:",
                "Execute the structural retention scenario.",
                "",
                "Prompt:",
                "Return the required exact headings.",
                "",
                "Agent Output:",
                agent_output,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return trace_path


def _retention_agent_output(
    *,
    initial: tuple[str, ...],
    forward_5: tuple[str, ...],
    forward_10: tuple[str, ...],
    reverse_5: tuple[str, ...],
    final_retained: tuple[str, ...],
    final_lost: tuple[str, ...],
) -> str:
    return "\n\n".join(
        [
            "CHECKPOINT 0 - INITIAL\n" + _format_retention_groups(initial),
            "CHECKPOINT 5 - FORWARD\n" + _format_retention_groups(forward_5),
            "CHECKPOINT 10 - FORWARD\n" + _format_retention_groups(forward_10),
            "CHECKPOINT 15 - REVERSE\n" + _format_retention_groups(reverse_5),
            "CHECKPOINT 20 - FINAL\n" + _format_retention_groups(final_retained),
            "FINAL RETAINED UNITS\n" + (", ".join(final_retained) if final_retained else "NONE"),
            "FINAL LOST UNITS\n" + (", ".join(final_lost) if final_lost else "NONE"),
        ]
    )


def _format_retention_groups(unit_ids: tuple[str, ...]) -> str:
    facts = [unit_id for unit_id in unit_ids if unit_id.startswith("F")]
    dependencies = [unit_id for unit_id in unit_ids if unit_id.startswith("D")]
    constraints = [unit_id for unit_id in unit_ids if unit_id.startswith("C")]
    extras = [
        unit_id
        for unit_id in unit_ids
        if unit_id not in set(facts) and unit_id not in set(dependencies) and unit_id not in set(constraints)
    ]
    return "\n".join(
        [
            f"FACTS: {', '.join(facts) if facts else 'NONE'}",
            f"DEPENDENCIES: {', '.join(dependencies) if dependencies else 'NONE'}",
            f"CONSTRAINTS: {', '.join(constraints) if constraints else 'NONE'}",
            f"EXTRA: {', '.join(extras) if extras else 'NONE'}",
        ]
    )


def _math_state_loss_agent_output(
    *,
    slot_lines: tuple[str, ...],
    retained_slots: tuple[str, ...],
    lost_slots: tuple[str, ...],
) -> str:
    return "\n\n".join(
        [
            "CHECKPOINT 0 - INITIAL STATE\n" + "\n".join(slot_lines),
            "CHECKPOINT 5 - FORWARD STATE\n" + "\n".join(slot_lines),
            "CHECKPOINT 10 - FORWARD STATE\n" + "\n".join(slot_lines),
            "CHECKPOINT 15 - RECOVERED STATE\n" + "\n".join(slot_lines),
            "CHECKPOINT 20 - FINAL STATE\n" + "\n".join(slot_lines),
            "FINAL RETAINED UNITS\n" + (", ".join(retained_slots) if retained_slots else "NONE"),
            "FINAL LOST UNITS\n" + (", ".join(lost_slots) if lost_slots else "NONE"),
        ]
    )


def _sc9_agent_output(
    *,
    structural_units: tuple[str, ...],
    math_slot_lines: tuple[str, ...],
    retained_sections: tuple[str, ...],
    lost_sections: tuple[str, ...],
) -> str:
    structural_block = "\n".join(
        [
            f"FACTS: {', '.join(unit for unit in structural_units if unit.startswith('F')) or 'NONE'}",
            f"DEPENDENCIES: {', '.join(unit for unit in structural_units if unit.startswith('D')) or 'NONE'}",
            f"CONSTRAINTS: {', '.join(unit for unit in structural_units if unit.startswith('C')) or 'NONE'}",
            f"EXTRA: {', '.join(unit for unit in structural_units if unit.startswith('X')) or 'NONE'}",
        ]
    )
    sequence_block = "A B C D E F G H I J K L M N O P Q R S T"
    trail_block = "1-A 2-B 3-C 4-D 5-E 6-F 7-G 8-H 9-I 10-J"
    clock_block = "\n".join(
        [
            "TIME: 12:00",
            "HOUR_HAND: 12",
            "MINUTE_HAND: 12",
            "POS_12: top",
            "POS_3: right",
            "POS_6: bottom",
            "POS_9: left",
        ]
    )
    checkpoint_block = "\n\n".join(
        [
            "SECTION 1 - STRUCTURAL RETENTION\n" + structural_block,
            "SECTION 2 - MATH STATE LOSS\n" + "\n".join(math_slot_lines),
            "SECTION 3 - N-BACK ANOMALY TRAP\n" + sequence_block,
            "SECTION 4 - TRAIL MAKING\n" + trail_block,
            "SECTION 5 - MOVE CLOCK HANDS\n" + clock_block,
        ]
    )
    return "\n\n".join(
        [
            "CHECKPOINT 0 - INITIAL COMPOSITE\n" + checkpoint_block,
            "CHECKPOINT 5 - FORWARD COMPOSITE\n" + checkpoint_block,
            "CHECKPOINT 10 - FORWARD COMPOSITE\n" + checkpoint_block,
            "CHECKPOINT 15 - RECOVERED COMPOSITE\n" + checkpoint_block,
            "CHECKPOINT 20 - FINAL COMPOSITE\n" + checkpoint_block,
            "FINAL RETAINED SECTIONS\n" + ("\n".join(retained_sections) if retained_sections else "NONE"),
            "FINAL LOST SECTIONS\n" + ("\n".join(lost_sections) if lost_sections else "NONE"),
        ]
    )


def _create_minimal_brain_root(root: Path, empty_context: dict[str, object]) -> None:
    for relative in (
        "brain/tasks",
        "brain/decisions",
        "brain/constraints",
        "brain/procedures",
        "brain/issues",
        "runtime/drafts",
        "runtime/inbox",
        "relations",
        "views",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    (root / "views" / "working_context.json").write_text(
        json.dumps(empty_context, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_decision_artifact(
    brain_root: Path,
    artifact_id: str,
    summary: str,
    *,
    body: str | None = None,
) -> Path:
    payload: dict[str, object] = {
        "id": artifact_id,
        "type": "decision",
        "summary": summary,
    }
    if body is not None:
        payload["body"] = body
    path = brain_root / "brain" / "decisions" / f"{artifact_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
