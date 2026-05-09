# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Generate strict retention artifacts for benchmark scenarios.

This tool is intentionally narrow:
- only explicitly supported retention_type variants
- exact section headings only
- exact unit ids or exact slot labels only
- count-based presence/absence only

Ghost logic is supported only when a scenario explicitly defines ghost_spec.
It does not implement:
- heuristic parsing
- retention parsing for unrelated scenarios
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.benchmark_modes import (  # noqa: E402
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmark_adapters.common.benchmark_paths import (  # noqa: E402
    BenchmarkPaths,
    get_benchmark_paths,
    result_log_path,
    scenario_json_path,
)
from benchmark_adapters.common.scenario_utils import load_benchmark_scenario  # noqa: E402


RETENTION_LAYER_SUFFIX = ".retention_layer.json"
RETENTION_SUMMARY_SUFFIX = ".retention_summary.md"
STRUCTURAL_RETENTION_TYPE = "structural_retention"
MATH_RETENTION_WITH_CORRECTNESS_TYPE = "math_retention_with_correctness"
SECTIONED_COMPOSITE_RETENTION_TYPE = "sectioned_composite_retention"
SUPPORT_ENABLED = "enabled"
SUPPORT_DEFERRED = "deferred"
SUPPORT_UNSUPPORTED = "unsupported"
SCENARIO_INTERPRETATION_MANIFEST_FILENAME = "scenario_interpretation_support.json"
STRUCTURAL_INTERPRETATION_VARIANTS = {
    "structural_retention",
    "structural_retention_with_ghost",
}
MATH_INTERPRETATION_VARIANT = "math_retention_with_correctness"
COMPOSITE_INTERPRETATION_VARIANT = "sectioned_composite_interpretation"
RETURN_TO_ORIGIN_ALLOWED_SCENARIO_IDS = {
    "sc_03_math_state_loss",
    "sc_08_move_clock_hands",
}
TRAJECTORY_READINESS_READY = "ready"
TRAJECTORY_READINESS_DEFERRED = "deferred"
TRAJECTORY_READINESS_UNSUPPORTED = "unsupported"
VALID_TRAJECTORY_READINESS_VALUES = {
    TRAJECTORY_READINESS_READY,
    TRAJECTORY_READINESS_DEFERRED,
    TRAJECTORY_READINESS_UNSUPPORTED,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate strict structural retention artifacts for a benchmark scenario."
    )
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=[BASELINE, PR_LIGHT_BRAIN],
        help="Executed benchmark modes to inspect.",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def generate_retention_artifacts_for_run(
    *,
    repo_root: Path,
    run_id: str,
    scenario_ids: tuple[str, ...],
    source_modes: tuple[str, ...],
    overwrite: bool = True,
) -> list[tuple[Path, Path]]:
    generated: list[tuple[Path, Path]] = []
    for scenario_id in scenario_ids:
        artifact_paths = generate_retention_artifacts_for_scenario(
            repo_root=repo_root,
            run_id=run_id,
            scenario_id=scenario_id,
            source_modes=source_modes,
            overwrite=overwrite,
        )
        if artifact_paths is not None:
            generated.append(artifact_paths)
    return generated


def generate_retention_artifacts_for_scenario(
    *,
    repo_root: Path,
    run_id: str,
    scenario_id: str,
    source_modes: tuple[str, ...],
    overwrite: bool = True,
) -> tuple[Path, Path] | None:
    paths = get_benchmark_paths(repo_root)
    scenario = load_benchmark_scenario(paths, scenario_id)
    trajectory_readiness = _load_trajectory_readiness(scenario.config)
    scenario_type = _require_string(scenario.config, "scenario_type", "scenario")
    interpretation_contract = resolve_scenario_interpretation_contract(
        scenario_id=scenario_id,
        scenario_type=scenario_type,
        scenario_config=scenario.config,
    )
    retention_spec = _load_enabled_retention_spec(
        scenario.config,
        interpretation_contract=interpretation_contract,
    )
    if retention_spec is None:
        return None

    interpretation_variant = _require_string(
        interpretation_contract,
        "interpretation_variant",
        "interpretation_contract",
    )
    retention_type = _require_string(retention_spec, "retention_type", "retention_spec")
    if (
        interpretation_variant in STRUCTURAL_INTERPRETATION_VARIANTS
        and retention_type == STRUCTURAL_RETENTION_TYPE
    ):
        retention_layer = build_structural_retention_layer(
            paths=paths,
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            source_modes=source_modes,
            retention_spec=retention_spec,
            interpretation_contract=interpretation_contract,
            trajectory_readiness=trajectory_readiness,
        )
    elif (
        interpretation_variant == MATH_INTERPRETATION_VARIANT
        and retention_type == MATH_RETENTION_WITH_CORRECTNESS_TYPE
    ):
        retention_layer = build_math_retention_with_correctness_layer(
            paths=paths,
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            source_modes=source_modes,
            retention_spec=retention_spec,
            interpretation_contract=interpretation_contract,
        )
    elif (
        interpretation_variant == COMPOSITE_INTERPRETATION_VARIANT
        and retention_type == SECTIONED_COMPOSITE_RETENTION_TYPE
    ):
        retention_layer = build_sectioned_composite_retention_layer(
            paths=paths,
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            source_modes=source_modes,
            retention_spec=retention_spec,
            interpretation_contract=interpretation_contract,
        )
    else:
        raise ValueError(
            "enabled interpretation variant is not supported by the current engine: "
            f"interpretation_variant={interpretation_variant} retention_type={retention_type}"
        )
    retention_summary = build_retention_summary(retention_layer)

    scenarios_reports_dir = paths.reports_root / run_id / "scenarios"
    scenarios_reports_dir.mkdir(parents=True, exist_ok=True)
    retention_layer_path = scenarios_reports_dir / f"{scenario_id}{RETENTION_LAYER_SUFFIX}"
    retention_summary_path = scenarios_reports_dir / f"{scenario_id}{RETENTION_SUMMARY_SUFFIX}"

    _write_json_artifact(retention_layer_path, retention_layer, overwrite=overwrite)
    _write_text_artifact(retention_summary_path, retention_summary, overwrite=overwrite)
    return retention_layer_path, retention_summary_path


def build_structural_retention_layer(
    *,
    paths: BenchmarkPaths,
    scenario_id: str,
    scenario_type: str,
    source_modes: tuple[str, ...],
    retention_spec: dict[str, Any],
    interpretation_contract: dict[str, Any],
    trajectory_readiness: str,
) -> dict[str, Any]:
    all_unit_ids = _collect_all_unit_ids(retention_spec)
    checkpoints = _load_checkpoints(retention_spec)
    final_sections = _load_final_sections(retention_spec)
    required_headings = _load_required_headings(retention_spec)
    ghost_spec = _load_ghost_spec(retention_spec)

    parsed_by_mode: dict[str, dict[str, Any] | None] = {}
    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        if mode not in source_modes:
            parsed_by_mode[mode] = None
            continue
        trace_path = result_log_path(paths, mode, scenario_id)
        if not trace_path.exists():
            parsed_by_mode[mode] = None
            continue
        parsed_by_mode[mode] = _parse_structural_retention_trace(
            trace_path=trace_path,
            all_unit_ids=all_unit_ids,
            checkpoints=checkpoints,
            final_sections=final_sections,
            required_headings=required_headings,
            ghost_spec=ghost_spec,
        )

    step_trajectory: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        step_trajectory.append(
            {
                "checkpoint_id": checkpoint["checkpoint_id"],
                "checkpoint_label": checkpoint["checkpoint_label"],
                "section_heading": checkpoint["section_heading"],
                BASELINE: _mode_checkpoint_summary(parsed_by_mode[BASELINE], checkpoint["checkpoint_id"]),
                PR_EPHEMERAL: _mode_checkpoint_summary(parsed_by_mode[PR_EPHEMERAL], checkpoint["checkpoint_id"]),
                PR_LIGHT_BRAIN: _mode_checkpoint_summary(
                    parsed_by_mode[PR_LIGHT_BRAIN],
                    checkpoint["checkpoint_id"],
                ),
            }
        )

    baseline_trajectory = _build_trajectory_diagnostics_for_structural_retention(
        parsed_mode=parsed_by_mode[BASELINE],
        trajectory_readiness=trajectory_readiness,
        checkpoints=checkpoints,
        all_unit_ids=all_unit_ids,
    )
    pr_ephemeral_trajectory = _build_trajectory_diagnostics_for_structural_retention(
        parsed_mode=parsed_by_mode[PR_EPHEMERAL],
        trajectory_readiness=trajectory_readiness,
        checkpoints=checkpoints,
        all_unit_ids=all_unit_ids,
    )
    pr_light_brain_trajectory = _build_trajectory_diagnostics_for_structural_retention(
        parsed_mode=parsed_by_mode[PR_LIGHT_BRAIN],
        trajectory_readiness=trajectory_readiness,
        checkpoints=checkpoints,
        all_unit_ids=all_unit_ids,
    )

    baseline_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[BASELINE], all_unit_ids),
        parsed_mode=parsed_by_mode[BASELINE],
        scenario_id=scenario_id,
        trajectory_diagnostics=baseline_trajectory,
    )
    pr_ephemeral_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[PR_EPHEMERAL], all_unit_ids),
        parsed_mode=parsed_by_mode[PR_EPHEMERAL],
        scenario_id=scenario_id,
        trajectory_diagnostics=pr_ephemeral_trajectory,
    )
    pr_light_brain_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[PR_LIGHT_BRAIN], all_unit_ids),
        parsed_mode=parsed_by_mode[PR_LIGHT_BRAIN],
        scenario_id=scenario_id,
        trajectory_diagnostics=pr_light_brain_trajectory,
    )

    return {
        "interpretation_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "interpretation_variant": interpretation_contract["interpretation_variant"],
        },
        "layer_support": interpretation_contract["layer_support"],
        "retention_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "retention_type": STRUCTURAL_RETENTION_TYPE,
            "counting_policy": "presence_absence_only",
            "strictness": "exact_headings_exact_unit_ids_only",
            "source_modes": list(source_modes),
            "ghost_policy": (
                "explicit_token_match_only"
                if ghost_spec is not None
                else "deferred"
            ),
            "notes": [
                "Phase 1A is count-based presence/absence only.",
                "No correctness layer.",
                (
                    "Structural ghost counts extra non-canonical unit ids in the final state only."
                    if ghost_spec is not None
                    else "No ghost layer."
                ),
                "Temporal ghost is diagnostic only and is computed from intermediate checkpoints only.",
            ],
        },
        "unit_groups": _build_unit_groups_payload(retention_spec),
        "step_trajectory": step_trajectory,
        "final_summary": {
            BASELINE: baseline_final,
            PR_EPHEMERAL: pr_ephemeral_final,
            PR_LIGHT_BRAIN: pr_light_brain_final,
            "delta_vs_baseline": _build_delta_summary(
                baseline_final=baseline_final,
                pr_light_brain_final=pr_light_brain_final,
            ),
        },
    }


def build_math_retention_with_correctness_layer(
    *,
    paths: BenchmarkPaths,
    scenario_id: str,
    scenario_type: str,
    source_modes: tuple[str, ...],
    retention_spec: dict[str, Any],
    interpretation_contract: dict[str, Any],
) -> dict[str, Any]:
    all_unit_ids = _collect_all_unit_ids(retention_spec)
    checkpoints = _load_checkpoints(retention_spec)
    final_sections = _load_final_sections(retention_spec)
    required_headings = _load_required_headings(retention_spec)
    correctness_spec = _load_correctness_spec(retention_spec)

    parsed_by_mode: dict[str, dict[str, Any] | None] = {}
    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        if mode not in source_modes:
            parsed_by_mode[mode] = None
            continue
        trace_path = result_log_path(paths, mode, scenario_id)
        if not trace_path.exists():
            parsed_by_mode[mode] = None
            continue
        parsed_by_mode[mode] = _parse_math_retention_with_correctness_trace(
            trace_path=trace_path,
            all_unit_ids=all_unit_ids,
            checkpoints=checkpoints,
            final_sections=final_sections,
            required_headings=required_headings,
            correctness_spec=correctness_spec,
        )

    step_trajectory: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        step_trajectory.append(
            {
                "checkpoint_id": checkpoint["checkpoint_id"],
                "checkpoint_label": checkpoint["checkpoint_label"],
                "section_heading": checkpoint["section_heading"],
                BASELINE: _mode_checkpoint_summary(parsed_by_mode[BASELINE], checkpoint["checkpoint_id"]),
                PR_EPHEMERAL: _mode_checkpoint_summary(parsed_by_mode[PR_EPHEMERAL], checkpoint["checkpoint_id"]),
                PR_LIGHT_BRAIN: _mode_checkpoint_summary(
                    parsed_by_mode[PR_LIGHT_BRAIN],
                    checkpoint["checkpoint_id"],
                ),
            }
        )

    baseline_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[BASELINE], all_unit_ids),
        parsed_mode=parsed_by_mode[BASELINE],
        scenario_id=scenario_id,
    )
    pr_ephemeral_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[PR_EPHEMERAL], all_unit_ids),
        parsed_mode=parsed_by_mode[PR_EPHEMERAL],
        scenario_id=scenario_id,
    )
    pr_light_brain_final = _augment_mode_summary_with_contract_signals(
        _mode_final_summary(parsed_by_mode[PR_LIGHT_BRAIN], all_unit_ids),
        parsed_mode=parsed_by_mode[PR_LIGHT_BRAIN],
        scenario_id=scenario_id,
    )

    return {
        "interpretation_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "interpretation_variant": interpretation_contract["interpretation_variant"],
        },
        "layer_support": interpretation_contract["layer_support"],
        "retention_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "retention_type": MATH_RETENTION_WITH_CORRECTNESS_TYPE,
            "counting_policy": "presence_absence_only",
            "correctness_policy": "exact_value_match_only",
            "strictness": "exact_headings_exact_slot_labels_exact_values_only",
            "source_modes": list(source_modes),
            "notes": [
                "Retention is independent from correctness.",
                "Correctness uses exact slot-value matching only.",
                "No ghost layer.",
                "Temporal ghost is diagnostic only and is computed from intermediate checkpoints only.",
            ],
        },
        "unit_groups": _build_unit_groups_payload(retention_spec),
        "step_trajectory": step_trajectory,
        "final_summary": {
            BASELINE: baseline_final,
            PR_EPHEMERAL: pr_ephemeral_final,
            PR_LIGHT_BRAIN: pr_light_brain_final,
            "delta_vs_baseline": _build_math_delta_summary(
                baseline_final=baseline_final,
                pr_light_brain_final=pr_light_brain_final,
            ),
        },
    }


def build_sectioned_composite_retention_layer(
    *,
    paths: BenchmarkPaths,
    scenario_id: str,
    scenario_type: str,
    source_modes: tuple[str, ...],
    retention_spec: dict[str, Any],
    interpretation_contract: dict[str, Any],
) -> dict[str, Any]:
    checkpoints = _load_checkpoints(retention_spec)
    final_sections = _load_final_sections(retention_spec)
    required_headings = _load_required_headings(retention_spec)
    composite_sections = _load_composite_sections(retention_spec)

    parsed_by_mode: dict[str, dict[str, Any] | None] = {}
    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        if mode not in source_modes:
            parsed_by_mode[mode] = None
            continue
        trace_path = result_log_path(paths, mode, scenario_id)
        if not trace_path.exists():
            parsed_by_mode[mode] = None
            continue
        parsed_by_mode[mode] = _parse_sectioned_composite_trace(
            trace_path=trace_path,
            checkpoints=checkpoints,
            final_sections=final_sections,
            required_headings=required_headings,
            composite_sections=composite_sections,
        )

    sections_payload: list[dict[str, Any]] = []
    for composite_section in composite_sections:
        section_entry: dict[str, Any] = {
            "section_id": composite_section["section_id"],
            "section_label": composite_section["section_label"],
            "section_heading": composite_section["section_heading"],
            "source_scenario_id": composite_section.get("source_scenario_id"),
            "include_steps": composite_section.get("include_steps"),
            "max_percent": composite_section["max_percent"],
            "interpretation_variant": composite_section["interpretation_variant"],
            "layer_support": composite_section["layer_support"],
            "section_spec_ref": composite_section.get("section_spec_ref"),
            "return_to_origin": composite_section.get("return_to_origin"),
        }
        reason = composite_section.get("reason")
        if isinstance(reason, str) and reason.strip():
            section_entry["reason"] = reason.strip()

        section_result: dict[str, Any] | None
        section_layer_support = _require_dict(
            composite_section,
            "layer_support",
            "composite section",
        )
        if (
            _require_support_value(section_layer_support, "retention", "composite section.layer_support")
            != SUPPORT_ENABLED
        ):
            section_result = None
        else:
            section_variant = _require_string(
                composite_section,
                "interpretation_variant",
                "composite section",
            )
            section_retention_type = _require_string(
                composite_section,
                "retention_type",
                "composite section",
            )
            if (
                section_variant in STRUCTURAL_INTERPRETATION_VARIANTS
                and section_retention_type == STRUCTURAL_RETENTION_TYPE
            ):
                section_result = _build_composite_structural_section_result(
                    composite_section=composite_section,
                    composite_checkpoints=checkpoints,
                    parsed_by_mode=parsed_by_mode,
                )
            elif (
                section_variant == MATH_INTERPRETATION_VARIANT
                and section_retention_type == MATH_RETENTION_WITH_CORRECTNESS_TYPE
            ):
                section_result = _build_composite_math_section_result(
                    composite_section=composite_section,
                    composite_checkpoints=checkpoints,
                    parsed_by_mode=parsed_by_mode,
                )
            else:
                raise ValueError(
                    "composite section uses an unsupported enabled interpretation variant: "
                    f"section_id={composite_section['section_id']} "
                    f"interpretation_variant={section_variant} "
                    f"retention_type={section_retention_type}"
                )
        section_entry["section_result"] = section_result
        sections_payload.append(section_entry)

    baseline_final = _build_composite_final_summary_for_mode(
        mode_key=BASELINE,
        parsed_mode=parsed_by_mode[BASELINE],
        sections_payload=sections_payload,
    )
    pr_ephemeral_final = _build_composite_final_summary_for_mode(
        mode_key=PR_EPHEMERAL,
        parsed_mode=parsed_by_mode[PR_EPHEMERAL],
        sections_payload=sections_payload,
    )
    pr_light_brain_final = _build_composite_final_summary_for_mode(
        mode_key=PR_LIGHT_BRAIN,
        parsed_mode=parsed_by_mode[PR_LIGHT_BRAIN],
        sections_payload=sections_payload,
    )

    return {
        "interpretation_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "interpretation_variant": interpretation_contract["interpretation_variant"],
            "composite": True,
        },
        "layer_support": interpretation_contract["layer_support"],
        "retention_metadata": {
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "retention_type": SECTIONED_COMPOSITE_RETENTION_TYPE,
            "aggregation_policy": "section_level_only",
            "strictness": "exact_top_level_headings_exact_section_headings_only",
            "source_modes": list(source_modes),
            "notes": [
                "Each section is evaluated independently.",
                "Totals are sums of section contributions only.",
                "No raw-unit merging across sections is allowed.",
                "Deferred sections remain visible but do not produce fake section results.",
            ],
        },
        "sections": sections_payload,
        "final_summary": {
            BASELINE: baseline_final,
            PR_EPHEMERAL: pr_ephemeral_final,
            PR_LIGHT_BRAIN: pr_light_brain_final,
            "delta_vs_baseline": _build_composite_delta_summary(
                baseline_final=baseline_final,
                pr_light_brain_final=pr_light_brain_final,
            ),
        },
    }


def build_retention_summary(retention_layer: dict[str, Any]) -> str:
    interpretation_metadata = _require_dict(
        retention_layer,
        "interpretation_metadata",
        "retention_layer",
    )
    interpretation_variant = _require_string(
        interpretation_metadata,
        "interpretation_variant",
        "interpretation_metadata",
    )
    if interpretation_variant == COMPOSITE_INTERPRETATION_VARIANT:
        return build_composite_retention_summary(retention_layer)
    layer_support = _require_dict(retention_layer, "layer_support", "retention_layer")
    metadata = _require_dict(retention_layer, "retention_metadata", "retention_layer")
    unit_groups = _require_list(retention_layer, "unit_groups", "retention_layer")
    step_trajectory = _require_list(retention_layer, "step_trajectory", "retention_layer")
    final_summary = _require_dict(retention_layer, "final_summary", "retention_layer")

    scenario_id = _require_string(metadata, "scenario_id", "retention_metadata")
    scenario_type = _require_string(metadata, "scenario_type", "retention_metadata")
    pr_ephemeral_present = final_summary.get(PR_EPHEMERAL) is not None
    retention_support = _require_support_value(layer_support, "retention", "layer_support")
    correctness_support = _require_support_value(layer_support, "correctness", "layer_support")
    ghost_support = _require_support_value(layer_support, "ghost", "layer_support")
    correctness_enabled = correctness_support == SUPPORT_ENABLED
    ghost_enabled = ghost_support == SUPPORT_ENABLED

    lines: list[str] = []
    lines.append(f"# Retention Summary - {scenario_id}")
    lines.append("")
    lines.append(f"- scenario_id: {scenario_id}")
    lines.append(f"- scenario_type: {scenario_type}")
    lines.append(f"- interpretation_variant: {interpretation_variant}")
    lines.append("- counting_policy: presence/absence only")
    lines.append("")
    lines.append("## Layer Support")
    lines.append("")
    lines.append(f"- retention: {retention_support}")
    lines.append(f"- correctness: {correctness_support}")
    lines.append(f"- ghost: {ghost_support}")
    lines.append("")
    lines.append("## Unit Groups")
    lines.append("")
    lines.append("| Group | Units | Count |")
    lines.append("|-------|-------|-------|")
    for group in unit_groups:
        if not isinstance(group, dict):
            raise ValueError("unit_groups entries must be objects")
        lines.append(
            "| "
            f"{_require_string(group, 'label', 'unit_group')} | "
            f"{', '.join(_require_string_list(group, 'unit_ids', 'unit_group'))} | "
            f"{_require_int(group, 'unit_count', 'unit_group')} |"
        )
    lines.append("")
    lines.append("## Checkpoint Counts")
    lines.append("")
    if pr_ephemeral_present:
        lines.append("| Checkpoint | Baseline Retained/Lost | PR-Ephemeral Retained/Lost | PR-Light + Brain Retained/Lost |")
        lines.append("|------------|------------------------|----------------------------|--------------------------------|")
    else:
        lines.append("| Checkpoint | Baseline Retained/Lost | PR-Light + Brain Retained/Lost |")
        lines.append("|------------|------------------------|--------------------------------|")

    for checkpoint in step_trajectory:
        if not isinstance(checkpoint, dict):
            raise ValueError("step_trajectory entries must be objects")
        baseline_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, BASELINE))
        brain_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, PR_LIGHT_BRAIN))
        if pr_ephemeral_present:
            ephemeral_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, PR_EPHEMERAL))
            lines.append(
                "| "
                f"{_require_string(checkpoint, 'checkpoint_label', 'step_trajectory entry')} | "
                f"{baseline_cell} | "
                f"{ephemeral_cell} | "
                f"{brain_cell} |"
            )
        else:
            lines.append(
                "| "
                f"{_require_string(checkpoint, 'checkpoint_label', 'step_trajectory entry')} | "
                f"{baseline_cell} | "
                f"{brain_cell} |"
            )

    baseline_final = _require_optional_mode_summary(final_summary, BASELINE)
    brain_final = _require_optional_mode_summary(final_summary, PR_LIGHT_BRAIN)
    delta = _require_dict(final_summary, "delta_vs_baseline", "final_summary")

    lines.append("")
    lines.append("## Final Summary")
    lines.append("")
    lines.append(
        f"- baseline: retained={baseline_final['retained_count']} lost={baseline_final['lost_count']} retention_percent={baseline_final['retention_percent']:.2f}"
    )
    if pr_ephemeral_present:
        ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
        lines.append(
            f"- pr_ephemeral: retained={ephemeral_final['retained_count']} lost={ephemeral_final['lost_count']} retention_percent={ephemeral_final['retention_percent']:.2f}"
        )
    lines.append(
        f"- pr_light_brain: retained={brain_final['retained_count']} lost={brain_final['lost_count']} retention_percent={brain_final['retention_percent']:.2f}"
    )
    lines.append(
        f"- delta_vs_baseline: retained_count_delta={delta['retained_count_delta']} retention_percent_delta={delta['retention_percent_delta']:.2f}"
    )
    if correctness_enabled:
        lines.append("")
        lines.append("## Optional Correctness Layer")
        lines.append("")
        lines.append(
            f"- baseline: retention_percent={baseline_final['retention_percent']:.2f} correctness_percent={baseline_final['correctness_percent']:.2f} gap={baseline_final['retention_correctness_gap']:.2f}"
        )
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
            lines.append(
                f"- pr_ephemeral: retention_percent={ephemeral_final['retention_percent']:.2f} correctness_percent={ephemeral_final['correctness_percent']:.2f} gap={ephemeral_final['retention_correctness_gap']:.2f}"
            )
        lines.append(
            f"- pr_light_brain: retention_percent={brain_final['retention_percent']:.2f} correctness_percent={brain_final['correctness_percent']:.2f} gap={brain_final['retention_correctness_gap']:.2f}"
        )
    if ghost_enabled:
        lines.append("")
        lines.append("## Ghost Artifacts")
        lines.append("")
        lines.append("- ghost_percent = ghost_units / canonical_unit_count")
        lines.append("- structural ghost is final-state only")
        lines.append("- ghost is separate from retained/lost accounting")
        lines.append("")
        lines.append(
            f"- baseline: ghost_units={baseline_final['ghost_units']} ghost_percent={baseline_final['ghost_percent']:.2f}"
        )
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
            lines.append(
                f"- pr_ephemeral: ghost_units={ephemeral_final['ghost_units']} ghost_percent={ephemeral_final['ghost_percent']:.2f}"
            )
        lines.append(
            f"- pr_light_brain: ghost_units={brain_final['ghost_units']} ghost_percent={brain_final['ghost_percent']:.2f}"
        )
        lines.append(
            f"- delta_vs_baseline: ghost_units_delta={delta['ghost_units_delta']} ghost_percent_delta={delta['ghost_percent_delta']:.2f}"
        )
    if _summary_has_return_to_origin(final_summary):
        lines.append("")
        lines.append("## Return To Origin")
        lines.append("")
        lines.append(
            f"- baseline: enabled={baseline_final['return_to_origin']['enabled']} matches={baseline_final['return_to_origin']['matches']}"
        )
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
            if ephemeral_final is not None and "return_to_origin" in ephemeral_final:
                lines.append(
                    f"- pr_ephemeral: enabled={ephemeral_final['return_to_origin']['enabled']} matches={ephemeral_final['return_to_origin']['matches']}"
                )
        lines.append(
            f"- pr_light_brain: enabled={brain_final['return_to_origin']['enabled']} matches={brain_final['return_to_origin']['matches']}"
        )
    if _summary_has_temporal_diagnostics(final_summary):
        lines.append("")
        lines.append("## Temporal Diagnostics")
        lines.append("")
        lines.append("- temporal ghost is diagnostic only")
        lines.append("- temporal ghost is computed from intermediate checkpoints only")
        lines.append("")
        lines.append(
            f"- baseline: detected={baseline_final['temporal_diagnostics']['temporal_ghost_detected']} count={baseline_final['temporal_diagnostics']['temporal_ghost_count']}"
        )
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
            if ephemeral_final is not None and "temporal_diagnostics" in ephemeral_final:
                lines.append(
                    f"- pr_ephemeral: detected={ephemeral_final['temporal_diagnostics']['temporal_ghost_detected']} count={ephemeral_final['temporal_diagnostics']['temporal_ghost_count']}"
                )
        lines.append(
            f"- pr_light_brain: detected={brain_final['temporal_diagnostics']['temporal_ghost_detected']} count={brain_final['temporal_diagnostics']['temporal_ghost_count']}"
        )
    if _summary_has_trajectory_diagnostics(final_summary):
        lines.append("")
        lines.append("## Trajectory Diagnostics")
        lines.append("")
        lines.append("- trajectory diagnostics are diagnostic only")
        lines.append("- checkpoint_count uses observable checkpoint count, not raw scenario instruction count")
        lines.append("")
        lines.append(_trajectory_summary_line("baseline", baseline_final))
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
            if ephemeral_final is not None and "trajectory_diagnostics" in ephemeral_final:
                lines.append(_trajectory_summary_line("pr_ephemeral", ephemeral_final))
        lines.append(_trajectory_summary_line("pr_light_brain", brain_final))
    lines.append("")
    return "\n".join(lines)


def build_composite_retention_summary(retention_layer: dict[str, Any]) -> str:
    interpretation_metadata = _require_dict(
        retention_layer,
        "interpretation_metadata",
        "retention_layer",
    )
    layer_support = _require_dict(retention_layer, "layer_support", "retention_layer")
    metadata = _require_dict(retention_layer, "retention_metadata", "retention_layer")
    sections = _require_list(retention_layer, "sections", "retention_layer")
    final_summary = _require_dict(retention_layer, "final_summary", "retention_layer")

    scenario_id = _require_string(metadata, "scenario_id", "retention_metadata")
    scenario_type = _require_string(metadata, "scenario_type", "retention_metadata")
    interpretation_variant = _require_string(
        interpretation_metadata,
        "interpretation_variant",
        "interpretation_metadata",
    )
    pr_ephemeral_present = final_summary.get(PR_EPHEMERAL) is not None

    lines: list[str] = []
    lines.append(f"# Retention Summary - {scenario_id}")
    lines.append("")
    lines.append(f"- scenario_id: {scenario_id}")
    lines.append(f"- scenario_type: {scenario_type}")
    lines.append(f"- interpretation_variant: {interpretation_variant}")
    lines.append("- composite: section-based independent evaluation")
    lines.append("- aggregation_policy: section_level_only")
    lines.append("")
    lines.append("## Layer Support")
    lines.append("")
    lines.append(
        f"- retention: {_require_support_value(layer_support, 'retention', 'layer_support')}"
    )
    lines.append(
        f"- correctness: {_require_support_value(layer_support, 'correctness', 'layer_support')}"
    )
    lines.append(f"- ghost: {_require_support_value(layer_support, 'ghost', 'layer_support')}")
    lines.append("")
    lines.append("## Section Support")
    lines.append("")
    lines.append("| Section | Max % | Variant | Retention | Correctness | Ghost |")
    lines.append("|---------|-------|---------|-----------|-------------|-------|")
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("sections entries must be objects")
        section_support = _require_dict(section, "layer_support", "section entry")
        lines.append(
            "| "
            f"{_require_string(section, 'section_label', 'section entry')} | "
            f"{_require_number(section, 'max_percent', 'section entry'):.2f} | "
            f"{_require_string(section, 'interpretation_variant', 'section entry')} | "
            f"{_require_support_value(section_support, 'retention', 'section entry.layer_support')} | "
            f"{_require_support_value(section_support, 'correctness', 'section entry.layer_support')} | "
            f"{_require_support_value(section_support, 'ghost', 'section entry.layer_support')} |"
        )
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("sections entries must be objects")
        section_result = section.get("section_result")
        if not isinstance(section_result, dict):
            continue
        lines.append("")
        lines.append(f"## {_require_string(section, 'section_label', 'section entry')}")
        lines.append("")
        lines.append(
            f"- section_id: {_require_string(section, 'section_id', 'section entry')}"
        )
        lines.append(
            f"- section_heading: {_require_string(section, 'section_heading', 'section entry')}"
        )
        lines.append(
            f"- max_percent: {_require_number(section, 'max_percent', 'section entry'):.2f}"
        )
        step_trajectory = _require_list(section_result, "step_trajectory", "section_result")
        lines.append("")
        lines.append("### Checkpoint Counts")
        lines.append("")
        if pr_ephemeral_present:
            lines.append("| Checkpoint | Baseline Retained/Lost | PR-Ephemeral Retained/Lost | PR-Light + Brain Retained/Lost |")
            lines.append("|------------|------------------------|----------------------------|--------------------------------|")
        else:
            lines.append("| Checkpoint | Baseline Retained/Lost | PR-Light + Brain Retained/Lost |")
            lines.append("|------------|------------------------|--------------------------------|")
        for checkpoint in step_trajectory:
            if not isinstance(checkpoint, dict):
                raise ValueError("section_result.step_trajectory entries must be objects")
            baseline_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, BASELINE))
            brain_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, PR_LIGHT_BRAIN))
            if pr_ephemeral_present:
                ephemeral_cell = _summary_count_cell(_require_optional_mode_summary(checkpoint, PR_EPHEMERAL))
                lines.append(
                    "| "
                    f"{_require_string(checkpoint, 'checkpoint_label', 'step_trajectory entry')} | "
                    f"{baseline_cell} | {ephemeral_cell} | {brain_cell} |"
                )
            else:
                lines.append(
                    "| "
                    f"{_require_string(checkpoint, 'checkpoint_label', 'step_trajectory entry')} | "
                    f"{baseline_cell} | {brain_cell} |"
                )

        section_final = _require_dict(section_result, "final_summary", "section_result")
        baseline_final = _require_optional_mode_summary(section_final, BASELINE)
        brain_final = _require_optional_mode_summary(section_final, PR_LIGHT_BRAIN)
        lines.append("")
        lines.append("### Final Section Summary")
        lines.append("")
        lines.append(
            f"- baseline: retained={baseline_final['retained_count']} lost={baseline_final['lost_count']} retention_percent={baseline_final['retention_percent']:.2f}"
        )
        if "correctness_percent" in baseline_final:
            lines.append(
                f"  correctness_percent={baseline_final['correctness_percent']:.2f} gap={baseline_final['retention_correctness_gap']:.2f}"
            )
        if "ghost_units" in baseline_final:
            lines.append(
                f"  ghost_units={baseline_final['ghost_units']} ghost_percent={baseline_final['ghost_percent']:.2f}"
            )
        if pr_ephemeral_present:
            ephemeral_final = _require_optional_mode_summary(section_final, PR_EPHEMERAL)
            lines.append(
                f"- pr_ephemeral: retained={ephemeral_final['retained_count']} lost={ephemeral_final['lost_count']} retention_percent={ephemeral_final['retention_percent']:.2f}"
            )
        lines.append(
            f"- pr_light_brain: retained={brain_final['retained_count']} lost={brain_final['lost_count']} retention_percent={brain_final['retention_percent']:.2f}"
        )
        if "correctness_percent" in brain_final:
            lines.append(
                f"  correctness_percent={brain_final['correctness_percent']:.2f} gap={brain_final['retention_correctness_gap']:.2f}"
            )
        if "ghost_units" in brain_final:
            lines.append(
                f"  ghost_units={brain_final['ghost_units']} ghost_percent={brain_final['ghost_percent']:.2f}"
            )
        if "return_to_origin" in baseline_final:
            lines.append(
                f"  return_to_origin.enabled={baseline_final['return_to_origin']['enabled']} return_to_origin.matches={baseline_final['return_to_origin']['matches']}"
            )
        if "temporal_diagnostics" in baseline_final:
            lines.append(
                f"  temporal_ghost_detected={baseline_final['temporal_diagnostics']['temporal_ghost_detected']} temporal_ghost_count={baseline_final['temporal_diagnostics']['temporal_ghost_count']}"
            )
        if "return_to_origin" in brain_final:
            lines.append(
                f"  return_to_origin.enabled={brain_final['return_to_origin']['enabled']} return_to_origin.matches={brain_final['return_to_origin']['matches']}"
            )
        if "temporal_diagnostics" in brain_final:
            lines.append(
                f"  temporal_ghost_detected={brain_final['temporal_diagnostics']['temporal_ghost_detected']} temporal_ghost_count={brain_final['temporal_diagnostics']['temporal_ghost_count']}"
            )

    baseline_final = _require_optional_mode_summary(final_summary, BASELINE)
    brain_final = _require_optional_mode_summary(final_summary, PR_LIGHT_BRAIN)
    delta = _require_dict(final_summary, "delta_vs_baseline", "final_summary")

    lines.append("")
    lines.append("## Composite Final Summary")
    lines.append("")
    lines.append("- totals are sums of section contributions only")
    lines.append("- no raw-unit merging across sections is used")
    lines.append(
        f"- baseline: retained_sections={', '.join(baseline_final['retained_section_ids']) if baseline_final['retained_section_ids'] else 'NONE'} lost_sections={', '.join(baseline_final['lost_section_ids']) if baseline_final['lost_section_ids'] else 'NONE'} total_retained_percent={baseline_final['total_retained_percent']:.2f} total_correctness_percent={baseline_final['total_correctness_percent']:.2f} total_ghost_percent={baseline_final['total_ghost_percent']:.2f}"
    )
    if pr_ephemeral_present:
        ephemeral_final = _require_optional_mode_summary(final_summary, PR_EPHEMERAL)
        lines.append(
            f"- pr_ephemeral: retained_sections={', '.join(ephemeral_final['retained_section_ids']) if ephemeral_final['retained_section_ids'] else 'NONE'} lost_sections={', '.join(ephemeral_final['lost_section_ids']) if ephemeral_final['lost_section_ids'] else 'NONE'} total_retained_percent={ephemeral_final['total_retained_percent']:.2f} total_correctness_percent={ephemeral_final['total_correctness_percent']:.2f} total_ghost_percent={ephemeral_final['total_ghost_percent']:.2f}"
        )
    lines.append(
        f"- pr_light_brain: retained_sections={', '.join(brain_final['retained_section_ids']) if brain_final['retained_section_ids'] else 'NONE'} lost_sections={', '.join(brain_final['lost_section_ids']) if brain_final['lost_section_ids'] else 'NONE'} total_retained_percent={brain_final['total_retained_percent']:.2f} total_correctness_percent={brain_final['total_correctness_percent']:.2f} total_ghost_percent={brain_final['total_ghost_percent']:.2f}"
    )
    lines.append(
        f"- delta_vs_baseline: total_retained_percent_delta={delta['total_retained_percent_delta']:.2f} total_correctness_percent_delta={delta['total_correctness_percent_delta']:.2f} total_ghost_percent_delta={delta['total_ghost_percent_delta']:.2f}"
    )
    lines.append("")
    return "\n".join(lines)


def _load_enabled_retention_spec(
    config: dict[str, Any],
    *,
    interpretation_contract: dict[str, Any],
) -> dict[str, Any] | None:
    layer_support = _require_dict(
        interpretation_contract,
        "layer_support",
        "interpretation_contract",
    )
    retention_support = _require_support_value(
        layer_support,
        "retention",
        "interpretation_contract.layer_support",
    )
    if retention_support != SUPPORT_ENABLED:
        return None

    retention_spec = config.get("retention_spec")
    if not isinstance(retention_spec, dict):
        raise ValueError(
            "retention-enabled interpretation requires retention_spec to be an object"
        )
    return retention_spec


def resolve_scenario_interpretation_contract(
    *,
    scenario_id: str,
    scenario_type: str,
    scenario_config: dict[str, Any],
) -> dict[str, Any]:
    interpretation_spec = scenario_config.get("interpretation_spec")
    if isinstance(interpretation_spec, dict):
        contract: dict[str, Any] = {
            "interpretation_variant": _require_string(
                interpretation_spec,
                "interpretation_variant",
                "interpretation_spec",
            ),
            "layer_support": _load_interpretation_layer_support(interpretation_spec),
        }
        reason = interpretation_spec.get("reason")
        if isinstance(reason, str) and reason.strip():
            contract["reason"] = reason.strip()
        return contract

    if scenario_type == "sectioned_composite_retention":
        return {
            "interpretation_variant": "composite_stress_not_decomposed",
            "layer_support": {
                "retention": SUPPORT_DEFERRED,
                "correctness": SUPPORT_DEFERRED,
                "ghost": SUPPORT_DEFERRED,
            },
            "reason": "not yet sectioned/decomposed for deterministic interpretation",
        }

    retention_spec = scenario_config.get("retention_spec")
    if not isinstance(retention_spec, dict):
        return {
            "interpretation_variant": "none",
            "layer_support": {
                "retention": SUPPORT_UNSUPPORTED,
                "correctness": SUPPORT_UNSUPPORTED,
                "ghost": SUPPORT_UNSUPPORTED,
            },
        }

    retention_type = retention_spec.get("retention_type")
    if retention_type == MATH_RETENTION_WITH_CORRECTNESS_TYPE:
        return {
            "interpretation_variant": "math_retention_with_correctness",
            "layer_support": {
                "retention": SUPPORT_ENABLED,
                "correctness": SUPPORT_ENABLED,
                "ghost": SUPPORT_UNSUPPORTED,
            },
        }

    if retention_type == STRUCTURAL_RETENTION_TYPE:
        ghost_spec = retention_spec.get("ghost_spec")
        if isinstance(ghost_spec, dict):
            interpretation_variant = "structural_retention_with_ghost"
            ghost_support = SUPPORT_ENABLED
        else:
            interpretation_variant = "structural_retention"
            ghost_support = SUPPORT_DEFERRED
        return {
            "interpretation_variant": interpretation_variant,
            "layer_support": {
                "retention": SUPPORT_ENABLED,
                "correctness": SUPPORT_DEFERRED,
                "ghost": ghost_support,
            },
        }

    return {
        "interpretation_variant": "none",
        "layer_support": {
            "retention": SUPPORT_UNSUPPORTED,
            "correctness": SUPPORT_UNSUPPORTED,
            "ghost": SUPPORT_UNSUPPORTED,
        },
    }


def _load_interpretation_layer_support(
    interpretation_spec: dict[str, Any],
) -> dict[str, str]:
    layer_support = _require_dict(
        interpretation_spec,
        "layer_support",
        "interpretation_spec",
    )
    return {
        "retention": _require_support_value(
            layer_support,
            "retention",
            "interpretation_spec.layer_support",
        ),
        "correctness": _require_support_value(
            layer_support,
            "correctness",
            "interpretation_spec.layer_support",
        ),
        "ghost": _require_support_value(
            layer_support,
            "ghost",
            "interpretation_spec.layer_support",
        ),
    }


def _load_composite_sections(retention_spec: dict[str, Any]) -> list[dict[str, Any]]:
    sections = retention_spec.get("resolved_sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError(
            "sectioned_composite_retention interpretation requires a non-empty "
            "retention_spec.resolved_sections list"
        )
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_headings: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("retention_spec.sections entries must be objects")
        section_id = _require_string(section, "section_id", "composite section")
        if section_id in seen_ids:
            raise ValueError(f"duplicate composite section_id: {section_id}")
        seen_ids.add(section_id)
        section_heading = _require_string(section, "section_heading", "composite section")
        if section_heading in seen_headings:
            raise ValueError(f"duplicate composite section_heading: {section_heading}")
        seen_headings.add(section_heading)
        normalized_section: dict[str, Any] = {
            "section_id": section_id,
            "section_label": _require_string(section, "section_label", "composite section"),
            "section_heading": section_heading,
            "max_percent": _require_number(section, "max_percent", "composite section"),
            "interpretation_variant": _require_string(
                section,
                "interpretation_variant",
                "composite section",
            ),
            "layer_support": _load_interpretation_layer_support({"layer_support": _require_dict(section, "layer_support", "composite section")}),
        }
        for optional_field in (
            "source_scenario_id",
            "include_steps",
            "return_to_origin",
            "resolved_contract",
            "resolved_steps",
            "section_spec_ref",
            "retention_type",
            "reason",
            "ghost_spec",
            "correctness_spec",
            "unit_groups",
        ):
            if optional_field in section:
                normalized_section[optional_field] = section[optional_field]
        normalized.append(normalized_section)
    return normalized


def _collect_all_unit_ids(retention_spec: dict[str, Any]) -> tuple[str, ...]:
    unit_groups = retention_spec.get("unit_groups")
    if not isinstance(unit_groups, list) or not unit_groups:
        raise ValueError("retention_spec.unit_groups must be a non-empty list")
    ordered: list[str] = []
    seen: set[str] = set()
    for group in unit_groups:
        if not isinstance(group, dict):
            raise ValueError("retention_spec.unit_groups entries must be objects")
        unit_ids = group.get("unit_ids")
        if not isinstance(unit_ids, list) or not unit_ids:
            raise ValueError("retention_spec.unit_groups entries must include non-empty unit_ids")
        for unit_id in unit_ids:
            if not isinstance(unit_id, str) or not unit_id.strip():
                raise ValueError("retention_spec.unit_ids must contain non-empty strings")
            cleaned = unit_id.strip()
            if cleaned in seen:
                raise ValueError(f"duplicate retention unit id: {cleaned}")
            seen.add(cleaned)
            ordered.append(cleaned)
    return tuple(ordered)


def _load_checkpoints(retention_spec: dict[str, Any]) -> list[dict[str, str]]:
    checkpoints = retention_spec.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError("retention_spec.checkpoints must be a non-empty list")
    normalized: list[dict[str, str]] = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            raise ValueError("retention_spec.checkpoints entries must be objects")
        normalized.append(
            {
                "checkpoint_id": _require_string(checkpoint, "checkpoint_id", "retention checkpoint"),
                "checkpoint_label": _require_string(checkpoint, "checkpoint_label", "retention checkpoint"),
                "section_heading": _require_string(checkpoint, "section_heading", "retention checkpoint"),
            }
        )
    return normalized


def _load_final_sections(retention_spec: dict[str, Any]) -> dict[str, str]:
    final_sections = retention_spec.get("final_sections")
    if not isinstance(final_sections, dict):
        raise ValueError("retention_spec.final_sections must be an object")
    return {
        "retained": _require_string(final_sections, "retained", "retention_spec.final_sections"),
        "lost": _require_string(final_sections, "lost", "retention_spec.final_sections"),
    }


def _load_required_headings(retention_spec: dict[str, Any]) -> tuple[str, ...]:
    headings = retention_spec.get("required_exact_section_headings")
    if not isinstance(headings, list) or not headings:
        raise ValueError("retention_spec.required_exact_section_headings must be a non-empty list")
    normalized: list[str] = []
    for heading in headings:
        if not isinstance(heading, str) or not heading.strip():
            raise ValueError("required section headings must be non-empty strings")
        normalized.append(heading.strip())
    return tuple(normalized)


def _load_ghost_spec(retention_spec: dict[str, Any]) -> dict[str, Any] | None:
    ghost_spec = retention_spec.get("ghost_spec")
    if ghost_spec is None:
        return None
    if not isinstance(ghost_spec, dict):
        raise ValueError("retention_spec.ghost_spec must be an object")
    token_pattern = _require_string(ghost_spec, "token_pattern", "ghost_spec")
    valid_transformations = ghost_spec.get("valid_transformations")
    if not isinstance(valid_transformations, dict):
        raise ValueError("ghost_spec.valid_transformations must be an object")
    for canonical_id, transformed_ids in valid_transformations.items():
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            raise ValueError("ghost_spec.valid_transformations keys must be non-empty strings")
        if not isinstance(transformed_ids, list):
            raise ValueError("ghost_spec.valid_transformations values must be lists")
        for transformed_id in transformed_ids:
            if not isinstance(transformed_id, str) or not transformed_id.strip():
                raise ValueError("ghost_spec transformation ids must be non-empty strings")
    return {
        "token_pattern": token_pattern,
        "valid_transformations": valid_transformations,
    }


def _parse_structural_retention_trace(
    *,
    trace_path: Path,
    all_unit_ids: tuple[str, ...],
    checkpoints: list[dict[str, str]],
    final_sections: dict[str, str],
    required_headings: tuple[str, ...],
    ghost_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    trace_text = trace_path.read_text(encoding="utf-8")
    agent_output = _extract_agent_output(trace_text)
    sections = _split_sections(
        text=agent_output,
        headings=required_headings,
    )

    checkpoint_summaries: dict[str, dict[str, Any]] = {}
    checkpoint_state_snapshots: dict[str, str] = {}
    intermediate_ghost_ids: set[str] = set()
    for index, checkpoint in enumerate(checkpoints):
        checkpoint_text = sections[checkpoint["section_heading"]]
        retained_ids = _find_present_unit_ids(
            checkpoint_text,
            all_unit_ids,
        )
        checkpoint_summaries[checkpoint["checkpoint_id"]] = _build_mode_summary(
            retained_ids=retained_ids,
            all_unit_ids=all_unit_ids,
        )
        checkpoint_state_snapshots[checkpoint["checkpoint_id"]] = checkpoint_text
        if 0 < index < (len(checkpoints) - 1):
            temporal_ghost_ids = _find_ghost_unit_ids(
                checkpoint_text,
                all_unit_ids,
                ghost_spec,
            )
            if temporal_ghost_ids is not None:
                intermediate_ghost_ids.update(temporal_ghost_ids)

    final_retained_section = sections[final_sections["retained"]]
    final_lost_section = sections[final_sections["lost"]]
    final_retained_ids = _find_present_unit_ids(
        final_retained_section,
        all_unit_ids,
    )
    final_retained_ghost_ids = _find_ghost_unit_ids(
        final_retained_section,
        all_unit_ids,
        ghost_spec,
    )
    final_lost_ghost_ids = _find_ghost_unit_ids(
        final_lost_section,
        all_unit_ids,
        ghost_spec,
    )
    explicit_final_lost_ids = _parse_explicit_lost_units(
        final_lost_section,
        all_unit_ids,
        allow_extra_structure=ghost_spec is not None,
        ghost_unit_ids=tuple(sorted(set(final_lost_ghost_ids))),
    )
    expected_final_lost_ids = tuple(
        unit_id for unit_id in all_unit_ids if unit_id not in set(final_retained_ids)
    )
    if tuple(explicit_final_lost_ids) != expected_final_lost_ids:
        raise ValueError(
            "FINAL LOST UNITS must match the complement of FINAL RETAINED UNITS exactly"
        )

    return {
        "checkpoints": checkpoint_summaries,
        "final": _build_mode_summary(
            retained_ids=final_retained_ids,
            all_unit_ids=all_unit_ids,
            ghost_unit_ids=tuple(sorted(set(final_retained_ghost_ids + final_lost_ghost_ids))),
        ),
        "state_snapshots": checkpoint_state_snapshots,
        "initial_state": sections[checkpoints[0]["section_heading"]],
        "final_state": sections[checkpoints[-1]["section_heading"]],
        "temporal_diagnostics": _build_temporal_diagnostics(tuple(sorted(intermediate_ghost_ids))),
    }


def _parse_sectioned_composite_trace(
    *,
    trace_path: Path,
    checkpoints: list[dict[str, str]],
    final_sections: dict[str, str],
    required_headings: tuple[str, ...],
    composite_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    trace_text = trace_path.read_text(encoding="utf-8")
    agent_output = _extract_agent_output(trace_text)
    top_level_sections = _split_sections(text=agent_output, headings=required_headings)

    section_headings = tuple(
        _require_string(section, "section_heading", "composite section")
        for section in composite_sections
    )
    checkpoint_sections: dict[str, dict[str, str]] = {}
    for checkpoint in checkpoints:
        section_map = _split_sections(
            text=top_level_sections[checkpoint["section_heading"]],
            headings=section_headings,
        )
        checkpoint_sections[checkpoint["checkpoint_id"]] = {
            _require_string(section, "section_id", "composite section"): section_map[
                _require_string(section, "section_heading", "composite section")
            ]
            for section in composite_sections
        }

    section_ids = tuple(
        _require_string(section, "section_id", "composite section")
        for section in composite_sections
    )
    retained_section_ids = _parse_explicit_section_ids(
        top_level_sections[final_sections["retained"]],
        section_ids,
    )
    lost_section_ids = _parse_explicit_section_ids(
        top_level_sections[final_sections["lost"]],
        section_ids,
    )
    expected_lost_section_ids = tuple(
        section_id for section_id in section_ids if section_id not in set(retained_section_ids)
    )
    if tuple(lost_section_ids) != expected_lost_section_ids:
        raise ValueError(
            "FINAL LOST SECTIONS must match the complement of FINAL RETAINED SECTIONS exactly"
        )
    return {
        "checkpoints": checkpoint_sections,
        "final": {
            "retained_section_ids": list(retained_section_ids),
            "lost_section_ids": list(lost_section_ids),
        },
    }


def _build_composite_structural_section_result(
    *,
    composite_section: dict[str, Any],
    composite_checkpoints: list[dict[str, str]],
    parsed_by_mode: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    all_unit_ids = _collect_all_unit_ids(composite_section)
    ghost_spec = composite_section.get("ghost_spec")

    step_trajectory: list[dict[str, Any]] = []
    final_by_mode: dict[str, dict[str, Any] | None] = {}
    for checkpoint in composite_checkpoints:
        checkpoint_summary: dict[str, Any] = {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "checkpoint_label": checkpoint["checkpoint_label"],
            "section_heading": checkpoint["section_heading"],
        }
        for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
            parsed_mode = parsed_by_mode.get(mode)
            if parsed_mode is None:
                checkpoint_summary[mode] = None
                continue
            checkpoint_text = _require_nested_text(
                parsed_mode,
                "checkpoints",
                checkpoint["checkpoint_id"],
                composite_section["section_id"],
            )
            retained_ids = _find_present_unit_ids(checkpoint_text, all_unit_ids)
            checkpoint_summary[mode] = _build_mode_summary(
                retained_ids=retained_ids,
                all_unit_ids=all_unit_ids,
            )
        step_trajectory.append(checkpoint_summary)
    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        parsed_mode = parsed_by_mode.get(mode)
        if parsed_mode is None:
            final_by_mode[mode] = None
            continue
        intermediate_ghost_ids: set[str] = set()
        for checkpoint in composite_checkpoints[1:-1]:
            checkpoint_text = _require_nested_text(
                parsed_mode,
                "checkpoints",
                checkpoint["checkpoint_id"],
                composite_section["section_id"],
            )
            temporal_ghost_ids = _find_ghost_unit_ids(checkpoint_text, all_unit_ids, ghost_spec)
            if temporal_ghost_ids is not None:
                intermediate_ghost_ids.update(temporal_ghost_ids)
        final_checkpoint = composite_checkpoints[-1]
        initial_checkpoint = composite_checkpoints[0]
        final_checkpoint_text = _require_nested_text(
            parsed_mode,
            "checkpoints",
            final_checkpoint["checkpoint_id"],
            composite_section["section_id"],
        )
        initial_checkpoint_text = _require_nested_text(
            parsed_mode,
            "checkpoints",
            initial_checkpoint["checkpoint_id"],
            composite_section["section_id"],
        )
        final_retained_ids = _find_present_unit_ids(final_checkpoint_text, all_unit_ids)
        final_ghost_ids = _find_ghost_unit_ids(final_checkpoint_text, all_unit_ids, ghost_spec)
        final_by_mode[mode] = _augment_mode_summary_with_contract_signals(
            _build_mode_summary(
                retained_ids=final_retained_ids,
                all_unit_ids=all_unit_ids,
                ghost_unit_ids=final_ghost_ids,
            ),
            temporal_diagnostics=_build_temporal_diagnostics(tuple(sorted(intermediate_ghost_ids))),
            return_to_origin_enabled=False,
            initial_state=initial_checkpoint_text,
            final_state=final_checkpoint_text,
        )

    return {
        "retention_metadata": {
            "retention_type": STRUCTURAL_RETENTION_TYPE,
            "counting_policy": "presence_absence_only",
            "ghost_policy": (
                "explicit_token_match_only"
                if isinstance(ghost_spec, dict)
                else "unsupported"
            ),
        },
        "unit_groups": _build_unit_groups_payload(composite_section),
        "step_trajectory": step_trajectory,
        "final_summary": {
            BASELINE: final_by_mode[BASELINE],
            PR_EPHEMERAL: final_by_mode[PR_EPHEMERAL],
            PR_LIGHT_BRAIN: final_by_mode[PR_LIGHT_BRAIN],
            "delta_vs_baseline": _build_delta_summary(
                baseline_final=final_by_mode[BASELINE],
                pr_light_brain_final=final_by_mode[PR_LIGHT_BRAIN],
            ),
        },
    }


def _build_composite_math_section_result(
    *,
    composite_section: dict[str, Any],
    composite_checkpoints: list[dict[str, str]],
    parsed_by_mode: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    all_unit_ids = _collect_all_unit_ids(composite_section)
    correctness_spec = _load_correctness_spec(
        {
            "correctness_spec": _require_dict(
                composite_section,
                "correctness_spec",
                "composite section",
            )
        }
    )
    expected_slot_values = _require_dict(
        correctness_spec,
        "expected_slot_values",
        "correctness_spec",
    )

    step_trajectory: list[dict[str, Any]] = []
    final_by_mode: dict[str, dict[str, Any] | None] = {}
    for checkpoint in composite_checkpoints:
        checkpoint_summary: dict[str, Any] = {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "checkpoint_label": checkpoint["checkpoint_label"],
            "section_heading": checkpoint["section_heading"],
        }
        for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
            parsed_mode = parsed_by_mode.get(mode)
            if parsed_mode is None:
                checkpoint_summary[mode] = None
                continue
            checkpoint_text = _require_nested_text(
                parsed_mode,
                "checkpoints",
                checkpoint["checkpoint_id"],
                composite_section["section_id"],
            )
            slot_assignments = _parse_exact_slot_assignments(checkpoint_text, all_unit_ids)
            checkpoint_summary[mode] = _build_math_mode_summary(
                slot_assignments=slot_assignments,
                expected_slot_values=expected_slot_values,
                all_unit_ids=all_unit_ids,
            )
        step_trajectory.append(checkpoint_summary)
    for mode in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        parsed_mode = parsed_by_mode.get(mode)
        if parsed_mode is None:
            final_by_mode[mode] = None
            continue
        initial_checkpoint = composite_checkpoints[0]
        final_checkpoint = composite_checkpoints[-1]
        initial_checkpoint_text = _require_nested_text(
            parsed_mode,
            "checkpoints",
            initial_checkpoint["checkpoint_id"],
            composite_section["section_id"],
        )
        final_checkpoint_text = _require_nested_text(
            parsed_mode,
            "checkpoints",
            final_checkpoint["checkpoint_id"],
            composite_section["section_id"],
        )
        final_assignments = _parse_exact_slot_assignments(final_checkpoint_text, all_unit_ids)
        final_by_mode[mode] = _augment_mode_summary_with_contract_signals(
            _build_math_mode_summary(
                slot_assignments=final_assignments,
                expected_slot_values=expected_slot_values,
                all_unit_ids=all_unit_ids,
            ),
            temporal_diagnostics=_build_temporal_diagnostics(()),
            return_to_origin_enabled=False,
            initial_state=initial_checkpoint_text,
            final_state=final_checkpoint_text,
        )

    return {
        "retention_metadata": {
            "retention_type": MATH_RETENTION_WITH_CORRECTNESS_TYPE,
            "counting_policy": "presence_absence_only",
            "correctness_policy": "exact_value_match_only",
        },
        "unit_groups": _build_unit_groups_payload(composite_section),
        "step_trajectory": step_trajectory,
        "final_summary": {
            BASELINE: final_by_mode[BASELINE],
            PR_EPHEMERAL: final_by_mode[PR_EPHEMERAL],
            PR_LIGHT_BRAIN: final_by_mode[PR_LIGHT_BRAIN],
            "delta_vs_baseline": _build_math_delta_summary(
                baseline_final=final_by_mode[BASELINE],
                pr_light_brain_final=final_by_mode[PR_LIGHT_BRAIN],
            ),
        },
    }


def _build_composite_final_summary_for_mode(
    *,
    mode_key: str,
    parsed_mode: dict[str, Any] | None,
    sections_payload: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if parsed_mode is None:
        return None
    final_payload = _require_dict(parsed_mode, "final", "parsed_mode")
    retained_section_ids = _require_optional_string_list(
        final_payload,
        "retained_section_ids",
        "parsed composite final",
    )
    lost_section_ids = _require_optional_string_list(
        final_payload,
        "lost_section_ids",
        "parsed composite final",
    )
    total_retained_percent = 0.0
    total_correctness_percent = 0.0
    total_ghost_percent = 0.0
    retention_supported_max_percent = 0.0
    correctness_supported_max_percent = 0.0
    ghost_supported_max_percent = 0.0

    for section in sections_payload:
        if not isinstance(section, dict):
            raise ValueError("sections entries must be objects")
        section_support = _require_dict(section, "layer_support", "section entry")
        section_result = section.get("section_result")
        max_percent = _require_number(section, "max_percent", "section entry")
        if not isinstance(section_result, dict):
            continue
        section_final_summary = _require_dict(section_result, "final_summary", "section_result")
        mode_summary = _require_optional_mode_summary(section_final_summary, mode_key)
        if mode_summary is None:
            continue
        if _require_support_value(section_support, "retention", "section entry.layer_support") == SUPPORT_ENABLED:
            retention_supported_max_percent += max_percent
            total_retained_percent += max_percent * float(mode_summary["retention_percent"])
        if (
            _require_support_value(section_support, "correctness", "section entry.layer_support")
            == SUPPORT_ENABLED
            and "correctness_percent" in mode_summary
        ):
            correctness_supported_max_percent += max_percent
            total_correctness_percent += max_percent * float(mode_summary["correctness_percent"])
        if (
            _require_support_value(section_support, "ghost", "section entry.layer_support")
            == SUPPORT_ENABLED
            and "ghost_percent" in mode_summary
        ):
            ghost_supported_max_percent += max_percent
            total_ghost_percent += max_percent * float(mode_summary["ghost_percent"])
    return {
        "retained_section_ids": retained_section_ids,
        "lost_section_ids": lost_section_ids,
        "total_retained_percent": round(total_retained_percent, 6),
        "total_correctness_percent": round(total_correctness_percent, 6),
        "total_ghost_percent": round(total_ghost_percent, 6),
        "retention_supported_max_percent": round(retention_supported_max_percent, 6),
        "correctness_supported_max_percent": round(correctness_supported_max_percent, 6),
        "ghost_supported_max_percent": round(ghost_supported_max_percent, 6),
    }


def _build_composite_delta_summary(
    *,
    baseline_final: dict[str, Any] | None,
    pr_light_brain_final: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if baseline_final is None or pr_light_brain_final is None:
        return None
    return {
        "total_retained_percent_delta": round(
            float(pr_light_brain_final["total_retained_percent"])
            - float(baseline_final["total_retained_percent"]),
            6,
        ),
        "total_correctness_percent_delta": round(
            float(pr_light_brain_final["total_correctness_percent"])
            - float(baseline_final["total_correctness_percent"]),
            6,
        ),
        "total_ghost_percent_delta": round(
            float(pr_light_brain_final["total_ghost_percent"])
            - float(baseline_final["total_ghost_percent"]),
            6,
        ),
    }


def _load_correctness_spec(retention_spec: dict[str, Any]) -> dict[str, Any]:
    correctness_spec = retention_spec.get("correctness_spec")
    if not isinstance(correctness_spec, dict):
        raise ValueError("math_retention_with_correctness requires correctness_spec")
    expected_slot_values = correctness_spec.get("expected_slot_values")
    if not isinstance(expected_slot_values, dict) or not expected_slot_values:
        raise ValueError("correctness_spec.expected_slot_values must be a non-empty object")
    _require_string(correctness_spec, "slot_section_heading", "correctness_spec")
    _require_string(correctness_spec, "value_match_policy", "correctness_spec")
    for slot_name, slot_value in expected_slot_values.items():
        if not isinstance(slot_name, str) or not slot_name.strip():
            raise ValueError("correctness_spec slot names must be non-empty strings")
        if not isinstance(slot_value, str) or not slot_value.strip():
            raise ValueError("correctness_spec slot values must be non-empty strings")
    return correctness_spec


def _parse_math_retention_with_correctness_trace(
    *,
    trace_path: Path,
    all_unit_ids: tuple[str, ...],
    checkpoints: list[dict[str, str]],
    final_sections: dict[str, str],
    required_headings: tuple[str, ...],
    correctness_spec: dict[str, Any],
) -> dict[str, Any]:
    trace_text = trace_path.read_text(encoding="utf-8")
    agent_output = _extract_agent_output(trace_text)
    sections = _split_sections(
        text=agent_output,
        headings=required_headings,
    )

    expected_slot_values = _require_dict(
        correctness_spec,
        "expected_slot_values",
        "correctness_spec",
    )
    slot_section_heading = _require_string(
        correctness_spec,
        "slot_section_heading",
        "correctness_spec",
    )
    checkpoint_summaries: dict[str, dict[str, Any]] = {}
    checkpoint_state_snapshots: dict[str, str] = {}
    for checkpoint in checkpoints:
        checkpoint_text = sections[checkpoint["section_heading"]]
        slot_assignments = _parse_exact_slot_assignments(
            checkpoint_text,
            all_unit_ids,
        )
        checkpoint_summaries[checkpoint["checkpoint_id"]] = _build_math_mode_summary(
            slot_assignments=slot_assignments,
            expected_slot_values=expected_slot_values,
            all_unit_ids=all_unit_ids,
        )
        checkpoint_state_snapshots[checkpoint["checkpoint_id"]] = checkpoint_text

    final_checkpoint_id = None
    for checkpoint in checkpoints:
        if checkpoint["section_heading"] == slot_section_heading:
            final_checkpoint_id = checkpoint["checkpoint_id"]
            break
    if final_checkpoint_id is None:
        raise ValueError("correctness_spec.slot_section_heading must match a declared checkpoint")
    recovered_state_summary = dict(checkpoint_summaries[final_checkpoint_id])

    final_retained_ids = _find_present_unit_ids(
        sections[final_sections["retained"]],
        all_unit_ids,
    )
    explicit_final_lost_ids = _parse_explicit_lost_units(
        sections[final_sections["lost"]],
        all_unit_ids,
    )
    expected_final_lost_ids = tuple(
        unit_id for unit_id in all_unit_ids if unit_id not in set(final_retained_ids)
    )
    if tuple(explicit_final_lost_ids) != expected_final_lost_ids:
        raise ValueError(
            "FINAL LOST UNITS must match the complement of FINAL RETAINED UNITS exactly"
        )
    if tuple(final_retained_ids) != tuple(recovered_state_summary["retained_unit_ids"]):
        raise ValueError(
            "FINAL RETAINED UNITS must match the slot labels retained in the declared final slot section"
        )

    return {
        "checkpoints": checkpoint_summaries,
        "final": dict(recovered_state_summary),
        "state_snapshots": checkpoint_state_snapshots,
        "initial_state": sections[checkpoints[0]["section_heading"]],
        "final_state": sections[slot_section_heading],
        "temporal_diagnostics": _build_temporal_diagnostics(()),
    }


def _parse_exact_slot_assignments(
    section_text: str,
    all_unit_ids: tuple[str, ...],
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([A-Z0-9_]+):\s*(.+)$", line)
        if match is None:
            raise ValueError("slot section contains a malformed line; expected SLOT_NAME: VALUE")
        slot_name = match.group(1).strip()
        slot_value = match.group(2).strip()
        if slot_name not in all_unit_ids:
            raise ValueError(f"unexpected slot label in correctness section: {slot_name}")
        if slot_name in assignments:
            raise ValueError(f"duplicate slot label in correctness section: {slot_name}")
        assignments[slot_name] = slot_value
    return assignments


def _build_math_mode_summary(
    *,
    slot_assignments: dict[str, str],
    expected_slot_values: dict[str, Any],
    all_unit_ids: tuple[str, ...],
) -> dict[str, Any]:
    retained_ids = tuple(unit_id for unit_id in all_unit_ids if unit_id in slot_assignments)
    base_summary = _build_mode_summary(
        retained_ids=retained_ids,
        all_unit_ids=all_unit_ids,
    )
    correct_units = 0
    for unit_id in all_unit_ids:
        expected_value = expected_slot_values.get(unit_id)
        if unit_id in slot_assignments and slot_assignments[unit_id] == expected_value:
            correct_units += 1
    total_units = len(all_unit_ids)
    correctness_percent = round((correct_units / total_units), 6) if total_units else 0.0
    base_summary["correct_units"] = correct_units
    base_summary["incorrect_units"] = total_units - correct_units
    base_summary["correctness_percent"] = correctness_percent
    base_summary["retention_correctness_gap"] = round(
        float(base_summary["retention_percent"]) - correctness_percent,
        6,
    )
    return base_summary


def _extract_agent_output(trace_text: str) -> str:
    marker = "\nAgent Output:\n"
    if marker not in trace_text:
        raise ValueError("trace log is missing the Agent Output section")
    agent_output = trace_text.split(marker, 1)[1]
    artifact_marker = "\n\nArtifact Suggestion:\n"
    if artifact_marker in agent_output:
        agent_output = agent_output.split(artifact_marker, 1)[0]
    return agent_output.strip()


def _split_sections(*, text: str, headings: tuple[str, ...]) -> dict[str, str]:
    positions: list[tuple[str, int, int]] = []
    for heading in headings:
        match = re.search(rf"(?m)^{re.escape(heading)}\s*$", text)
        if match is None:
            raise ValueError(f"required exact section heading missing: {heading}")
        positions.append((heading, match.start(), match.end()))

    positions.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (heading, _start, end) in enumerate(positions):
        next_start = positions[index + 1][1] if index + 1 < len(positions) else len(text)
        sections[heading] = text[end:next_start].strip()
    return sections


def _find_present_unit_ids(section_text: str, all_unit_ids: tuple[str, ...]) -> tuple[str, ...]:
    present: list[str] = []
    for unit_id in all_unit_ids:
        if re.search(rf"\b{re.escape(unit_id)}\b", section_text):
            present.append(unit_id)
    return tuple(present)


def _find_ghost_unit_ids(
    section_text: str,
    all_unit_ids: tuple[str, ...],
    ghost_spec: dict[str, Any] | None,
) -> tuple[str, ...] | None:
    if ghost_spec is None:
        return None
    token_pattern = _require_string(ghost_spec, "token_pattern", "ghost_spec")
    valid_transformations = _require_dict(ghost_spec, "valid_transformations", "ghost_spec")
    allowed_transformation_ids: set[str] = set()
    for transformed_ids in valid_transformations.values():
        if not isinstance(transformed_ids, list):
            raise ValueError("ghost_spec.valid_transformations values must be lists")
        for transformed_id in transformed_ids:
            if not isinstance(transformed_id, str) or not transformed_id.strip():
                raise ValueError("ghost_spec transformation ids must be non-empty strings")
            allowed_transformation_ids.add(transformed_id.strip())
    ghost_ids = {
        match.group(0)
        for match in re.finditer(token_pattern, section_text)
        if match.group(0) not in all_unit_ids and match.group(0) not in allowed_transformation_ids
    }
    return tuple(sorted(ghost_ids))


def _parse_explicit_lost_units(
    section_text: str,
    all_unit_ids: tuple[str, ...],
    *,
    allow_extra_structure: bool = False,
    ghost_unit_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    stripped = section_text.strip()
    found_ids = _find_present_unit_ids(stripped, all_unit_ids)
    has_none = bool(re.search(r"(?m)^\s*NONE\s*$", stripped))

    if has_none and (found_ids or ghost_unit_ids):
        raise ValueError("FINAL LOST UNITS must contain either exact unit ids or NONE")
    if has_none:
        return ()
    if not found_ids:
        if allow_extra_structure and ghost_unit_ids:
            return ()
        raise ValueError("FINAL LOST UNITS must explicitly list lost unit ids or NONE")
    return found_ids


def _parse_explicit_section_ids(
    section_text: str,
    all_section_ids: tuple[str, ...],
) -> tuple[str, ...]:
    stripped = section_text.strip()
    found_ids = tuple(
        section_id
        for section_id in all_section_ids
        if re.search(rf"\b{re.escape(section_id)}\b", stripped)
    )
    has_none = bool(re.search(r"(?m)^\s*NONE\s*$", stripped))
    if has_none and found_ids:
        raise ValueError("FINAL section lists must contain either exact section ids or NONE")
    if has_none:
        return ()
    if not found_ids:
        raise ValueError("FINAL section lists must explicitly list section ids or NONE")
    return found_ids


def _build_mode_summary(
    *,
    retained_ids: tuple[str, ...],
    all_unit_ids: tuple[str, ...],
    ghost_unit_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    lost_ids = [unit_id for unit_id in all_unit_ids if unit_id not in set(retained_ids)]
    total = len(all_unit_ids)
    summary: dict[str, Any] = {
        "retained_unit_ids": list(retained_ids),
        "lost_unit_ids": lost_ids,
        "retained_count": len(retained_ids),
        "lost_count": len(lost_ids),
        "retention_percent": (len(retained_ids) / total) if total else 0.0,
    }
    if ghost_unit_ids is not None:
        summary["ghost_unit_ids"] = list(ghost_unit_ids)
        summary["ghost_units"] = len(ghost_unit_ids)
        summary["ghost_percent"] = (len(ghost_unit_ids) / total) if total else 0.0
    return summary


def _build_temporal_diagnostics(temporal_ghost_ids: tuple[str, ...]) -> dict[str, Any]:
    return {
        "temporal_ghost_detected": len(temporal_ghost_ids) > 0,
        "temporal_ghost_count": len(temporal_ghost_ids),
    }


def _build_trajectory_diagnostics_for_structural_retention(
    *,
    parsed_mode: dict[str, Any] | None,
    trajectory_readiness: str,
    checkpoints: list[dict[str, str]],
    all_unit_ids: tuple[str, ...],
) -> dict[str, Any] | None:
    if parsed_mode is None or trajectory_readiness != TRAJECTORY_READINESS_READY:
        return None

    checkpoint_count = len(checkpoints)
    if checkpoint_count <= 0:
        raise ValueError("trajectory diagnostics require at least one observable checkpoint")

    checkpoint_weight = 100.0 / checkpoint_count
    expected_unit_ids = tuple(all_unit_ids)
    deviation_active = False
    deviation_segments = 0
    first_deviation_step: int | None = None
    deviation_start_step: int | None = None
    recovery_step: int | None = None
    cumulative_penalty = 0.0
    erosion_curve: list[dict[str, Any]] = []

    parsed_checkpoints = _require_dict(parsed_mode, "checkpoints", "parsed_mode")
    for step_index, checkpoint in enumerate(checkpoints):
        checkpoint_id = _require_string(checkpoint, "checkpoint_id", "checkpoint")
        checkpoint_summary = _require_dict(parsed_checkpoints, checkpoint_id, "parsed checkpoints")
        observed_unit_ids = tuple(
            _require_string_list(
                checkpoint_summary,
                "retained_unit_ids",
                "checkpoint_summary",
            )
        )
        matches_expected = observed_unit_ids == expected_unit_ids
        deviation_triggered = False

        if not matches_expected:
            if not deviation_active:
                deviation_segments += 1
                if first_deviation_step is None:
                    first_deviation_step = step_index
                if deviation_start_step is None:
                    deviation_start_step = step_index
                cumulative_penalty += checkpoint_weight
                deviation_active = True
                deviation_triggered = True
        elif deviation_active:
            if recovery_step is None:
                recovery_step = step_index
            deviation_active = False

        trajectory_score = max(0.0, 100.0 - cumulative_penalty)
        erosion_curve.append(
            {
                "step_index": step_index,
                "checkpoint_id": checkpoint_id,
                "deviation_triggered": deviation_triggered,
                "deviation_active": deviation_active,
                "cumulative_penalty": round(cumulative_penalty, 6),
                "trajectory_score": round(trajectory_score, 6),
            }
        )

    recovered_after_deviation = recovery_step is not None
    return {
        "enabled": True,
        "trajectory_score": round(max(0.0, 100.0 - cumulative_penalty), 6),
        "checkpoint_count": checkpoint_count,
        "checkpoint_weight": round(checkpoint_weight, 6),
        "deviation_segments": deviation_segments,
        "first_deviation_step": first_deviation_step,
        "recovery_signal": {
            "recovered_after_deviation": recovered_after_deviation,
            "deviation_start_step": deviation_start_step,
            "recovery_step": recovery_step,
            "recovery_distance": (
                (recovery_step - deviation_start_step)
                if recovered_after_deviation and deviation_start_step is not None
                else None
            ),
        },
        "erosion_curve": erosion_curve,
    }


def _load_trajectory_readiness(scenario_config: dict[str, Any]) -> str:
    readiness = _require_string(scenario_config, "trajectory_readiness", "scenario")
    if readiness not in VALID_TRAJECTORY_READINESS_VALUES:
        raise ValueError(
            "scenario trajectory_readiness must be one of "
            f"{sorted(VALID_TRAJECTORY_READINESS_VALUES)}: got {readiness!r}"
        )
    return readiness


def _evaluate_return_to_origin(initial_state: str, final_state: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "matches": final_state == initial_state,
    }


def _return_to_origin_enabled_for_scenario(scenario_id: str) -> bool:
    return scenario_id in RETURN_TO_ORIGIN_ALLOWED_SCENARIO_IDS


def _augment_mode_summary_with_contract_signals(
    summary: dict[str, Any] | None,
    *,
    parsed_mode: dict[str, Any] | None = None,
    scenario_id: str | None = None,
    temporal_diagnostics: dict[str, Any] | None = None,
    trajectory_diagnostics: dict[str, Any] | None = None,
    return_to_origin_enabled: bool | None = None,
    initial_state: str | None = None,
    final_state: str | None = None,
) -> dict[str, Any] | None:
    if summary is None:
        return None
    payload = dict(summary)
    payload["evaluation_status"] = "valid"

    if temporal_diagnostics is None and isinstance(parsed_mode, dict):
        parsed_temporal = parsed_mode.get("temporal_diagnostics")
        if isinstance(parsed_temporal, dict):
            temporal_diagnostics = parsed_temporal
    if temporal_diagnostics is None:
        temporal_diagnostics = _build_temporal_diagnostics(())
    payload["temporal_diagnostics"] = temporal_diagnostics

    if trajectory_diagnostics is not None:
        payload["trajectory_diagnostics"] = trajectory_diagnostics

    enabled = (
        return_to_origin_enabled
        if return_to_origin_enabled is not None
        else (
            _return_to_origin_enabled_for_scenario(scenario_id)
            if isinstance(scenario_id, str)
            else False
        )
    )
    if enabled:
        if initial_state is None and isinstance(parsed_mode, dict):
            initial_value = parsed_mode.get("initial_state")
            if isinstance(initial_value, str):
                initial_state = initial_value
        if final_state is None and isinstance(parsed_mode, dict):
            final_value = parsed_mode.get("final_state")
            if isinstance(final_value, str):
                final_state = final_value
        if not isinstance(initial_state, str) or not isinstance(final_state, str):
            raise ValueError("return_to_origin requires exact initial_state and final_state strings")
        payload["return_to_origin"] = _evaluate_return_to_origin(initial_state, final_state)
    return payload


def _build_delta_summary(
    *,
    baseline_final: dict[str, Any] | None,
    pr_light_brain_final: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if baseline_final is None or pr_light_brain_final is None:
        return None
    return {
        "retained_count_delta": (
            int(pr_light_brain_final["retained_count"]) - int(baseline_final["retained_count"])
        ),
        "retention_percent_delta": (
            float(pr_light_brain_final["retention_percent"]) - float(baseline_final["retention_percent"])
        ),
        **(
            {
                "ghost_units_delta": (
                    int(pr_light_brain_final["ghost_units"]) - int(baseline_final["ghost_units"])
                ),
                "ghost_percent_delta": (
                    float(pr_light_brain_final["ghost_percent"]) - float(baseline_final["ghost_percent"])
                ),
            }
            if "ghost_units" in baseline_final and "ghost_units" in pr_light_brain_final
            else {}
        ),
    }


def _build_math_delta_summary(
    *,
    baseline_final: dict[str, Any] | None,
    pr_light_brain_final: dict[str, Any] | None,
) -> dict[str, Any] | None:
    delta = _build_delta_summary(
        baseline_final=baseline_final,
        pr_light_brain_final=pr_light_brain_final,
    )
    if delta is None:
        return None
    delta["correctness_percent_delta"] = (
        round(
            float(pr_light_brain_final["correctness_percent"]) - float(baseline_final["correctness_percent"]),
            6,
        )
    )
    delta["retention_correctness_gap_delta"] = (
        round(
            float(pr_light_brain_final["retention_correctness_gap"])
            - float(baseline_final["retention_correctness_gap"]),
            6,
        )
    )
    return delta


def _build_unit_groups_payload(retention_spec: dict[str, Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for group in retention_spec["unit_groups"]:
        payload.append(
            {
                "group_id": _require_string(group, "group_id", "unit_group"),
                "label": _require_string(group, "label", "unit_group"),
                "unit_ids": _require_string_list(group, "unit_ids", "unit_group"),
                "unit_count": len(_require_string_list(group, "unit_ids", "unit_group")),
            }
        )
    return payload


def _mode_checkpoint_summary(
    parsed_mode: dict[str, Any] | None,
    checkpoint_id: str,
) -> dict[str, Any] | None:
    if parsed_mode is None:
        return None
    checkpoints = _require_dict(parsed_mode, "checkpoints", "parsed_mode")
    value = checkpoints.get(checkpoint_id)
    if not isinstance(value, dict):
        raise ValueError(f"parsed checkpoint missing: {checkpoint_id}")
    return value


def _mode_final_summary(
    parsed_mode: dict[str, Any] | None,
    all_unit_ids: tuple[str, ...],
) -> dict[str, Any] | None:
    if parsed_mode is None:
        return None
    final = _require_dict(parsed_mode, "final", "parsed_mode")
    if not isinstance(final, dict):
        raise ValueError("parsed final summary must be an object")
    if int(final.get("retained_count", -1)) + int(final.get("lost_count", -1)) != len(all_unit_ids):
        raise ValueError("final retained/lost counts must cover the full unit set")
    return final


def _summary_has_correctness(final_summary: dict[str, Any]) -> bool:
    for field_name in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        value = final_summary.get(field_name)
        if isinstance(value, dict) and "correctness_percent" in value:
            return True
    return False


def _summary_has_ghost(final_summary: dict[str, Any]) -> bool:
    for field_name in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        value = final_summary.get(field_name)
        if isinstance(value, dict) and "ghost_units" in value:
            return True
    return False


def _summary_has_return_to_origin(final_summary: dict[str, Any]) -> bool:
    for field_name in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        value = final_summary.get(field_name)
        if isinstance(value, dict) and "return_to_origin" in value:
            return True
    return False


def _summary_has_temporal_diagnostics(final_summary: dict[str, Any]) -> bool:
    for field_name in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        value = final_summary.get(field_name)
        if isinstance(value, dict) and "temporal_diagnostics" in value:
            return True
    return False


def _summary_has_trajectory_diagnostics(final_summary: dict[str, Any]) -> bool:
    for field_name in (BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN):
        value = final_summary.get(field_name)
        if isinstance(value, dict) and "trajectory_diagnostics" in value:
            return True
    return False


def _trajectory_summary_line(label: str, summary: dict[str, Any] | None) -> str:
    if summary is None:
        return f"- {label}: n/a"
    diagnostics = _require_dict(summary, "trajectory_diagnostics", "mode summary")
    recovery_signal = _require_dict(diagnostics, "recovery_signal", "trajectory_diagnostics")
    return (
        f"- {label}: "
        f"score={diagnostics['trajectory_score']:.2f} "
        f"checkpoint_count={diagnostics['checkpoint_count']} "
        f"deviation_segments={diagnostics['deviation_segments']} "
        f"first_deviation_step={diagnostics['first_deviation_step']} "
        f"recovered={recovery_signal['recovered_after_deviation']} "
        f"recovery_step={recovery_signal['recovery_step']} "
        f"recovery_distance={recovery_signal['recovery_distance']}"
    )


def _summary_count_cell(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "n/a"
    return f"{summary['retained_count']} / {summary['lost_count']}"


def _summary_ghost_cell(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "n/a"
    return f"{summary['ghost_units']} / {summary['ghost_percent']:.2f}"


def _section_final_mode_summary(
    step_trajectory: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any] | None:
    if not step_trajectory:
        raise ValueError("section step_trajectory must be non-empty")
    return _require_optional_mode_summary(step_trajectory[-1], mode)


def _require_nested_text(
    data: dict[str, Any],
    field_name: str,
    nested_key: str,
    leaf_key: str,
) -> str:
    nested = _require_dict(data, field_name, "nested object")
    value = nested.get(nested_key)
    if not isinstance(value, dict):
        raise ValueError(f"nested object field '{field_name}.{nested_key}' must be an object")
    leaf = value.get(leaf_key)
    if not isinstance(leaf, str):
        raise ValueError(f"nested object field '{field_name}.{nested_key}.{leaf_key}' must be a string")
    return leaf


def _require_optional_mode_summary(
    data: dict[str, Any],
    field_name: str,
) -> dict[str, Any] | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object or null")
    return value


def _require_optional_string_list(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> list[str]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{label} field '{field_name}' must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} field '{field_name}' must contain non-empty strings")
        normalized.append(item.strip())
    return normalized


def _require_support_value(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> str:
    value = _require_string(data, field_name, label)
    if value not in {SUPPORT_ENABLED, SUPPORT_DEFERRED, SUPPORT_UNSUPPORTED}:
        raise ValueError(
            f"{label} field '{field_name}' must be one of: "
            f"{SUPPORT_ENABLED}, {SUPPORT_DEFERRED}, {SUPPORT_UNSUPPORTED}"
        )
    return value


def _write_json_artifact(path: Path, payload: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text_artifact(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _require_dict(data: dict[str, Any], field_name: str, label: str) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{label} field '{field_name}' must be an object")
    return value


def _require_list(data: dict[str, Any], field_name: str, label: str) -> list[Any]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{label} field '{field_name}' must be a list")
    return value


def _require_string(data: dict[str, Any], field_name: str, label: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} field '{field_name}' must be a non-empty string")
    return value.strip()


def _require_string_list(data: dict[str, Any], field_name: str, label: str) -> list[str]:
    value = data.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} field '{field_name}' must be a non-empty list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} field '{field_name}' must contain non-empty strings")
        normalized.append(item.strip())
    return normalized


def _require_int(data: dict[str, Any], field_name: str, label: str) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} field '{field_name}' must be an integer")
    return value


def _require_number(data: dict[str, Any], field_name: str, label: str) -> float:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} field '{field_name}' must be numeric")
    return float(value)


def main() -> None:
    args = parse_args()
    artifact_paths = generate_retention_artifacts_for_scenario(
        repo_root=Path(args.repo_root).resolve(),
        run_id=args.run_id,
        scenario_id=args.scenario_id,
        source_modes=tuple(args.modes),
        overwrite=args.overwrite,
    )
    if artifact_paths is None:
        print("scenario does not define a supported retention layer; no retention artifacts generated")
        return
    retention_layer_path, retention_summary_path = artifact_paths
    print(f"retention layer saved: {retention_layer_path}")
    print(f"retention summary saved: {retention_summary_path}")


if __name__ == "__main__":
    main()
