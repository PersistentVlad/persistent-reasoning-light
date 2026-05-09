# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark prompt utilities for Persistent Reasoning Light.

This module defines deterministic helpers for building benchmark-specific prompt
wrappers around runtime adapter prompt primitives.

Benchmark prompt utilities may depend on reasoning-adapter prompt helpers, but
must not reimplement production prompt logic.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from reasoning_adapters.common.prompt_utils import (
    build_agent_prompt,
    build_context_payload,
    build_prompt_sections,
)

from .benchmark_modes import (
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
    validate_benchmark_mode,
)
from .scenario_utils import BenchmarkScenario


DEFAULT_BENCHMARK_PROMPT_TITLE: Final[str] = "Persistent Reasoning Light Benchmark Prompt"
ARTIFACT_GENERATOR_MODE_LEGACY: Final[str] = "legacy"
ARTIFACT_GENERATOR_MODE_CONSTRAINED: Final[str] = "constrained"
ARTIFACT_GENERATOR_MODE_SHADOW: Final[str] = "shadow"
DEFAULT_ARTIFACT_GENERATOR_MODE: Final[str] = ARTIFACT_GENERATOR_MODE_LEGACY
WORKING_CONTEXT_FORMAT_REFERENCE_ONLY: Final[str] = "reference_only"
WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES: Final[str] = "relevant_summaries"
DEFAULT_WORKING_CONTEXT_FORMAT: Final[str] = WORKING_CONTEXT_FORMAT_REFERENCE_ONLY
ARTIFACT_GENERATOR_MODES: Final[tuple[str, ...]] = (
    ARTIFACT_GENERATOR_MODE_LEGACY,
    ARTIFACT_GENERATOR_MODE_CONSTRAINED,
    ARTIFACT_GENERATOR_MODE_SHADOW,
)
WORKING_CONTEXT_FORMATS: Final[tuple[str, ...]] = (
    WORKING_CONTEXT_FORMAT_REFERENCE_ONLY,
    WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES,
)
GLOBAL_DECISION_PREFIXES: Final[tuple[str, ...]] = (
    "global_",
    "benchmark_",
    "common_",
)
RELEVANT_ARTIFACT_GROUPS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("tasks", "relevant_tasks", "tasks", "Relevant Task Cards"),
    ("decisions", "relevant_decisions", "decisions", "Relevant Decisions"),
    ("constraints", "relevant_constraints", "constraints", "Relevant Constraints"),
    ("procedures", "relevant_procedures", "procedures", "Relevant Procedures"),
)

MODE_DESCRIPTIONS: Final[dict[str, str]] = {
    BASELINE: "Run without PR-Light runtime context or seeded reasoning artifacts.",
    PR_EPHEMERAL: "Run with PR-Ephemeral runtime enabled and an empty benchmark reasoning brain.",
    PR_LIGHT_BRAIN: "Run with PR-Light runtime enabled and a seeded benchmark reasoning brain.",
}


def build_mode_description(mode: str) -> str:
    validated_mode = validate_benchmark_mode(mode)
    return MODE_DESCRIPTIONS[validated_mode]


def build_benchmark_header(
    scenario: BenchmarkScenario,
    *,
    mode: str,
    adapter_name: str,
    title: str = DEFAULT_BENCHMARK_PROMPT_TITLE,
) -> str:
    validated_mode = validate_benchmark_mode(mode)
    validated_adapter = _validate_adapter_name(adapter_name)

    lines = [
        title,
        "",
        "Benchmark Run Metadata:",
        f"- scenario_id: {scenario.scenario_id}",
        f"- scenario_name: {scenario.config['scenario_name']}",
        f"- scenario_type: {scenario.config['scenario_type']}",
        f"- adapter: {validated_adapter}",
        f"- mode: {validated_mode}",
        f"- mode_description: {build_mode_description(validated_mode)}",
    ]
    return "\n".join(lines)


def build_scenario_instruction_block(
    scenario: BenchmarkScenario,
    *,
    include_description: bool = True,
) -> str:
    lines = ["Scenario Instructions:"]

    if include_description:
        lines.append(f"- description: {scenario.config['description']}")

    lines.append("- steps:")
    for step in scenario.config["steps"]:
        lines.append(f"  - {step['step_id']}: {step['instruction']}")

    return "\n".join(lines)


def build_benchmark_instructions(
    *,
    mode: str,
    include_proposal_rule: bool = True,
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
) -> list[str]:
    validated_mode = validate_benchmark_mode(mode)
    validated_artifact_generator_mode = validate_artifact_generator_mode(
        artifact_generator_mode
    )
    active_artifact_generator_mode = active_artifact_generator_mode_for_prompt(
        validated_artifact_generator_mode
    )

    instructions = [
        "Follow the scenario steps exactly and do not skip steps.",
        "Preserve deterministic behavior and avoid introducing unsupported assumptions.",
        "Do not invent missing benchmark inputs.",
        "Keep outputs compact and structurally clear.",
    ]

    if validated_mode == BASELINE:
        instructions.append(
            "Do not assume Persistent Reasoning Light runtime support or preloaded reasoning context."
        )
    else:
        instructions.append(
            "Use the provided Persistent Reasoning Light working context without expanding it into full artifact bodies."
        )

    if include_proposal_rule and active_artifact_generator_mode == ARTIFACT_GENERATOR_MODE_LEGACY:
        instructions.extend(
            [
                "Your response must contain exactly these two explicit sections: 'Final Answer:' and 'Artifact Suggestion:'.",
                "Final Answer must contain the task solution only.",
                'Artifact Suggestion is mandatory on every run and must be either NONE or one parser-safe JSON object with exactly these keys: TaskCard, DecisionCard, ConstraintCard, ProcedureCard.',
                'For each type, output exactly one value: "NONE" or {"id":"...", "summary":"..."}.',
                "Default for every artifact type is NONE.",
                "At most one artifact per type is allowed.",
                "Use TaskCard only for clarified goals, DecisionCard for durable approach decisions, ConstraintCard for explicit non-violable rules, and ProcedureCard for deterministic workflows.",
                "Do not use aliases such as artifact_id or lower-case card names.",
                "Do not output reasoning traces, explanations, narratives, comments, markdown fences, multiple artifacts per type, or any extra fields.",
                "If no high-confidence durable artifact exists for a type, output NONE for that type.",
                "Do not place artifact JSON anywhere outside the Artifact Suggestion section.",
                'Example Artifact Suggestion JSON: {"TaskCard":"NONE","DecisionCard":{"id":"...","summary":"..."},"ConstraintCard":"NONE","ProcedureCard":"NONE"}.',
            ]
        )

    if (
        include_proposal_rule
        and active_artifact_generator_mode == ARTIFACT_GENERATOR_MODE_CONSTRAINED
    ):
        instructions.extend(
            [
                "Your response must contain exactly these two explicit sections: 'Final Answer:' and 'Artifact Suggestion:'.",
                "Final Answer must contain the task solution only.",
                "Default Artifact Suggestion output for every artifact type is NONE.",
                'Artifact Suggestion is mandatory on every run and must be either NONE or one parser-safe JSON object with exactly these keys: TaskCard, DecisionCard, ConstraintCard, ProcedureCard.',
                'For each type, output exactly one value: "NONE" or {"id":"...", "summary":"..."}.',
                "At most one artifact per type is allowed.",
                "Propose TaskCard only when goal clarification reduces ambiguity.",
                "Propose DecisionCard when the current result establishes a durable approach decision.",
                "Propose ConstraintCard when the result establishes an explicit checkable rule that must never be violated.",
                "Propose ProcedureCard when the result establishes a reusable deterministic workflow.",
                "The artifact must be durable, structural, non-temporary, non-redundant, independent, and useful across future reasoning steps.",
                "Do not propose artifacts for temporary calculations, intermediate states, step-local notes, restatements of the current answer, duplicate provided context, or paraphrases of the current step.",
                "Do not output reasoning traces, explanations, narratives, comments, markdown fences, multiple artifacts per type, or extra fields in Artifact Suggestion.",
                "Do not use aliases such as artifact_id or lower-case card names.",
                "If confidence is not high for a type, output NONE for that type.",
                "Do not place artifact JSON anywhere outside the Artifact Suggestion section.",
                "If the task answer needs structured output, keep that structure only inside Final Answer.",
                'Example Artifact Suggestion JSON: {"TaskCard":"NONE","DecisionCard":{"id":"...","summary":"..."},"ConstraintCard":"NONE","ProcedureCard":"NONE"}.',
            ]
        )

    return instructions


def validate_artifact_generator_mode(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("artifact_generator_mode must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError("artifact_generator_mode must not contain surrounding whitespace")
    if cleaned not in ARTIFACT_GENERATOR_MODES:
        allowed = ", ".join(ARTIFACT_GENERATOR_MODES)
        raise ValueError(f"artifact_generator_mode must be one of: {allowed}")
    return cleaned


def active_artifact_generator_mode_for_prompt(value: object) -> str:
    validated = validate_artifact_generator_mode(value)
    if validated == ARTIFACT_GENERATOR_MODE_SHADOW:
        return ARTIFACT_GENERATOR_MODE_LEGACY
    return validated


def validate_working_context_format(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("working_context_format must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError("working_context_format must not contain surrounding whitespace")
    if cleaned not in WORKING_CONTEXT_FORMATS:
        allowed = ", ".join(WORKING_CONTEXT_FORMATS)
        raise ValueError(f"working_context_format must be one of: {allowed}")
    return cleaned


def build_relevant_summary_context(
    context: Mapping[str, object],
    *,
    brain_root: Path,
    scenario_id: str,
) -> dict[str, object]:
    """
    Attach compact scenario-relevant artifact summaries for Working Context v2.

    This reads only selected persisted artifact summaries and never embeds full
    artifact bodies into the prompt-facing context.
    """
    normalized_context = _normalize_reference_context(context)
    scenario_prefix = _scenario_decision_prefix(scenario_id)

    enriched = dict(normalized_context)
    for source_field, relevant_field, folder_name, _title in RELEVANT_ARTIFACT_GROUPS:
        artifact_ids = [
            artifact_id
            for artifact_id in normalized_context[source_field]
            if _is_relevant_decision_id(artifact_id, scenario_prefix)
        ]
        artifact_root = brain_root / "brain" / folder_name
        enriched[relevant_field] = [
            {
                "id": artifact_id,
                "summary": _load_artifact_summary(
                    artifact_root / f"{artifact_id}.json",
                    artifact_id,
                    source_field,
                ),
            }
            for artifact_id in artifact_ids
        ]
    return enriched


def build_runtime_prompt_block(
    context: Mapping[str, object],
    *,
    task_text: str,
    mode: str,
    extra_references: Sequence[str] = (),
    title: str = "Runtime Adapter Prompt",
    scenario_id: str | None = None,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> str:
    """
    Build a benchmark-visible runtime prompt block.

    In baseline mode, this helper does not imply PR-Light runtime support.
    Any provided context is treated as benchmark-visible input only.

    In PR modes, the provided context is treated as compact PR-Light working context
    and must preserve reference-only semantics.
    """
    validated_mode = validate_benchmark_mode(mode)
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )

    runtime_instructions: list[str] = []
    if validated_mode == BASELINE:
        runtime_instructions.append(
            "Treat provided context as benchmark-visible input only; do not assume runtime persistence support."
        )
    else:
        if validated_working_context_format == WORKING_CONTEXT_FORMAT_REFERENCE_ONLY:
            runtime_instructions.append(
                "Use the provided working context as compact PR-Light context and preserve reference-only semantics."
            )
        else:
            runtime_instructions.append(
                "Use only the provided scenario-relevant artifact summaries as compact PR-Light context; do not expand them into full artifact bodies."
            )

    if validated_working_context_format == WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES:
        if scenario_id is None:
            raise ValueError(
                "scenario_id is required when working_context_format is relevant_summaries"
            )
        return _build_relevant_summary_runtime_prompt_block(
            context,
            task_text=task_text,
            instructions=runtime_instructions,
            extra_references=extra_references,
            title=title,
        )

    return build_agent_prompt(
        _legacy_reference_context(context),
        task_text=task_text,
        instructions=runtime_instructions,
        extra_references=extra_references,
        title=title,
    )


def build_benchmark_prompt(
    scenario: BenchmarkScenario,
    context: Mapping[str, object],
    *,
    mode: str,
    adapter_name: str,
    task_text: str,
    extra_references: Sequence[str] = (),
    title: str = DEFAULT_BENCHMARK_PROMPT_TITLE,
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> str:
    """
    Build a deterministic benchmark prompt.

    Prompt structure:
    - benchmark header
    - scenario instructions
    - runtime-facing prompt block
    - benchmark-level execution instructions
    """
    validated_mode = validate_benchmark_mode(mode)
    validated_artifact_generator_mode = validate_artifact_generator_mode(
        artifact_generator_mode
    )
    active_artifact_generator_mode = active_artifact_generator_mode_for_prompt(
        validated_artifact_generator_mode
    )
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )

    blocks = [
        build_benchmark_header(
            scenario,
            mode=validated_mode,
            adapter_name=adapter_name,
            title=title,
        ),
        "",
        build_scenario_instruction_block(scenario),
        "",
        build_runtime_prompt_block(
            context,
            task_text=task_text,
            mode=validated_mode,
            extra_references=extra_references,
            scenario_id=scenario.scenario_id,
            working_context_format=validated_working_context_format,
        ),
        "",
        "Benchmark Instructions:",
    ]

    for instruction in build_benchmark_instructions(
        mode=validated_mode,
        artifact_generator_mode=active_artifact_generator_mode,
    ):
        blocks.append(f"- {instruction}")

    return "\n".join(blocks)


def build_benchmark_prompt_payload(
    scenario: BenchmarkScenario,
    context: Mapping[str, object],
    *,
    mode: str,
    adapter_name: str,
    task_text: str,
    extra_references: Sequence[str] = (),
    title: str = DEFAULT_BENCHMARK_PROMPT_TITLE,
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> dict[str, Any]:
    validated_mode = validate_benchmark_mode(mode)
    validated_adapter = _validate_adapter_name(adapter_name)
    validated_artifact_generator_mode = validate_artifact_generator_mode(
        artifact_generator_mode
    )
    active_artifact_generator_mode = active_artifact_generator_mode_for_prompt(
        validated_artifact_generator_mode
    )
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )
    validated_task = _normalize_required_text(task_text, "task_text")
    validated_references = _normalize_string_sequence(
        extra_references,
        "extra_references",
    )

    return {
        "metadata": {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.config["scenario_name"],
            "scenario_type": scenario.config["scenario_type"],
            "adapter": validated_adapter,
            "mode": validated_mode,
            "mode_description": build_mode_description(validated_mode),
        },
        "task": validated_task,
        "scenario_description": scenario.config["description"],
        "scenario_steps": [
            {
                "step_id": step["step_id"],
                "instruction": step["instruction"],
            }
            for step in scenario.config["steps"]
        ],
        "context": build_context_payload_for_format(
            context,
            working_context_format=validated_working_context_format,
        ),
        "runtime_sections": build_prompt_sections_for_format(
            context,
            task_text=validated_task,
            working_context_format=validated_working_context_format,
        ),
        "benchmark_instructions": build_benchmark_instructions(
            mode=validated_mode,
            artifact_generator_mode=active_artifact_generator_mode,
        ),
        "extra_references": validated_references,
        "prompt": build_benchmark_prompt(
            scenario,
            context,
            mode=validated_mode,
            adapter_name=validated_adapter,
            task_text=validated_task,
            extra_references=validated_references,
            title=title,
            artifact_generator_mode=active_artifact_generator_mode,
            working_context_format=validated_working_context_format,
        ),
    }


def build_context_payload_for_format(
    context: Mapping[str, object],
    *,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> dict[str, object]:
    validated_format = validate_working_context_format(working_context_format)
    if validated_format == WORKING_CONTEXT_FORMAT_REFERENCE_ONLY:
        return build_context_payload(_legacy_reference_context(context))

    normalized = _normalize_relevant_summary_context(context)
    return {
        "active_task": normalized["active_task"],
        "relevant_tasks": [
            dict(task) for task in normalized["relevant_tasks"]
        ],
        "relevant_decisions": [
            dict(decision) for decision in normalized["relevant_decisions"]
        ],
        "relevant_constraints": [
            dict(constraint) for constraint in normalized["relevant_constraints"]
        ],
        "relevant_procedures": [
            dict(procedure) for procedure in normalized["relevant_procedures"]
        ],
        "open_issues": list(normalized["open_issues"]),
    }


def build_prompt_sections_for_format(
    context: Mapping[str, object],
    *,
    task_text: str,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> list[tuple[str, list[str]]]:
    validated_task = _normalize_required_text(task_text, "task_text")
    validated_format = validate_working_context_format(working_context_format)
    if validated_format == WORKING_CONTEXT_FORMAT_REFERENCE_ONLY:
        return build_prompt_sections(
            _legacy_reference_context(context),
            task_text=validated_task,
            instructions=(),
        )

    normalized = _normalize_relevant_summary_context(context)
    sections: list[tuple[str, list[str]]] = [("task", [validated_task])]
    active_task = normalized["active_task"]
    sections.append(("active_task", [active_task] if isinstance(active_task, str) else []))
    for _source_field, relevant_field, _folder_name, _title in RELEVANT_ARTIFACT_GROUPS:
        sections.append(
            (
                relevant_field,
                [
                    f"{artifact['id']}: {artifact['summary']}"
                    for artifact in normalized[relevant_field]
                ],
            )
        )
    sections.append(("open_issues", list(normalized["open_issues"])))
    return sections


def _build_relevant_summary_runtime_prompt_block(
    context: Mapping[str, object],
    *,
    task_text: str,
    instructions: Sequence[str],
    extra_references: Sequence[str],
    title: str,
) -> str:
    task = _normalize_required_text(task_text, "task_text")
    normalized = _normalize_relevant_summary_context(context)

    lines = [
        title,
        "",
        "Task:",
        task,
        "",
        "Persistent Reasoning Light Context",
    ]
    _append_optional_reference_section(lines, "Active Task", normalized["active_task"])
    for _source_field, relevant_field, _folder_name, title in RELEVANT_ARTIFACT_GROUPS:
        _append_reference_list_section(
            lines,
            title,
            [
                f"{artifact['id']}: {artifact['summary']}"
                for artifact in normalized[relevant_field]
            ],
        )
    _append_reference_list_section(lines, "Open Issues", normalized["open_issues"])

    normalized_instructions = _normalize_string_sequence(instructions, "instructions")
    if normalized_instructions:
        lines.extend(["", "Instructions"])
        for instruction in normalized_instructions:
            lines.append(f"- {instruction}")

    normalized_references = _normalize_string_sequence(
        extra_references,
        "extra_references",
    )
    if normalized_references:
        lines.extend(["", "References"])
        for reference in normalized_references:
            lines.append(f"- {reference}")

    return "\n".join(lines)


def _append_optional_reference_section(
    lines: list[str],
    title: str,
    value: object,
) -> None:
    lines.append(f"{title}:")
    if isinstance(value, str):
        lines.append(f"- {value}")
    else:
        lines.append("- none")


def _append_reference_list_section(
    lines: list[str],
    title: str,
    values: Sequence[str],
) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("- none")
        return
    for value in values:
        lines.append(f"- {value}")


def _normalize_reference_context(context: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(context, Mapping):
        raise ValueError("working context must be a mapping")

    active_task = context.get("active_task")
    if active_task is not None and not isinstance(active_task, str):
        raise ValueError("active_task must be a string or null")
    normalized: dict[str, object] = {"active_task": active_task}
    for field_name in ("tasks", "constraints", "decisions", "procedures", "open_issues"):
        value = context.get(field_name)
        if value is None and field_name in {"tasks", "procedures"}:
            value = []
        normalized[field_name] = _normalize_string_sequence(
            value,
            field_name,
        )
    return normalized


def _legacy_reference_context(context: Mapping[str, object]) -> dict[str, object]:
    normalized = _normalize_reference_context(context)
    return {
        "active_task": normalized["active_task"],
        "constraints": list(normalized["constraints"]),
        "decisions": list(normalized["decisions"]),
        "open_issues": list(normalized["open_issues"]),
    }


def _normalize_relevant_summary_context(
    context: Mapping[str, object],
) -> dict[str, object]:
    normalized = _normalize_reference_context(context)
    for _source_field, relevant_field, _folder_name, _title in RELEVANT_ARTIFACT_GROUPS:
        normalized[relevant_field] = _normalize_relevant_artifact_summaries(
            context.get(relevant_field, []),
            relevant_field,
        )
    return normalized


def _normalize_relevant_artifact_summaries(
    value: object,
    field_name: str,
) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of objects")

    relevant_artifacts: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be objects")
        artifact_id = _normalize_required_text(item.get("id"), f"{field_name}.id")
        summary = _normalize_summary_text(item.get("summary"), f"{field_name}.summary")
        if artifact_id in seen_ids:
            raise ValueError(f"{field_name} must not contain duplicate ids")
        seen_ids.add(artifact_id)
        relevant_artifacts.append({"id": artifact_id, "summary": summary})

    return relevant_artifacts


def _normalize_summary_text(value: object, field_name: str) -> str:
    text = _normalize_required_text(value, field_name)
    return " ".join(text.split())


def _scenario_decision_prefix(scenario_id: str) -> str:
    normalized = _normalize_required_text(scenario_id, "scenario_id")
    parts = normalized.split("_", 2)
    if len(parts) >= 2 and parts[0] == "sc":
        return f"{parts[0]}_{parts[1]}_"
    return f"{normalized}_"


def _is_relevant_decision_id(decision_id: str, scenario_prefix: str) -> bool:
    return decision_id.startswith(scenario_prefix) or decision_id.startswith(
        GLOBAL_DECISION_PREFIXES
    )


def _load_artifact_summary(
    artifact_path: Path,
    expected_artifact_id: str,
    artifact_label: str,
) -> str:
    if not artifact_path.exists():
        raise FileNotFoundError(f"{artifact_label} artifact not found: {artifact_path}")
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{artifact_label} artifact is not valid JSON: {artifact_path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{artifact_label} artifact must contain an object: {artifact_path}")
    artifact_id = _normalize_required_text(payload.get("id"), f"{artifact_label}.id")
    if artifact_id != expected_artifact_id:
        raise ValueError(
            f"{artifact_label} artifact id mismatch: "
            f"{expected_artifact_id} != {artifact_id}"
        )
    for field_name in ("summary", "goal", "statement", "name", "question"):
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return _normalize_summary_text(value, f"{artifact_label}.{field_name}")
    steps = payload.get("steps")
    if isinstance(steps, list):
        step_text = " ".join(item for item in steps if isinstance(item, str))
        if step_text.strip():
            return _normalize_summary_text(step_text, f"{artifact_label}.steps")
    raise ValueError(f"{artifact_label} artifact must contain a compact summary field")


def _normalize_string_sequence(value: object, field_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = item.strip()
        if not cleaned:
            raise ValueError(f"{field_name} must not contain empty strings")
        normalized.append(cleaned)

    return normalized


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _validate_adapter_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("adapter_name must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("adapter_name must not be empty")
    if cleaned != value:
        raise ValueError("adapter_name must not contain surrounding whitespace")
    return cleaned


__all__ = [
    "DEFAULT_BENCHMARK_PROMPT_TITLE",
    "DEFAULT_ARTIFACT_GENERATOR_MODE",
    "DEFAULT_WORKING_CONTEXT_FORMAT",
    "active_artifact_generator_mode_for_prompt",
    "ARTIFACT_GENERATOR_MODE_CONSTRAINED",
    "ARTIFACT_GENERATOR_MODE_LEGACY",
    "ARTIFACT_GENERATOR_MODE_SHADOW",
    "ARTIFACT_GENERATOR_MODES",
    "WORKING_CONTEXT_FORMAT_REFERENCE_ONLY",
    "WORKING_CONTEXT_FORMAT_RELEVANT_SUMMARIES",
    "WORKING_CONTEXT_FORMATS",
    "MODE_DESCRIPTIONS",
    "build_context_payload_for_format",
    "build_benchmark_header",
    "build_benchmark_instructions",
    "build_benchmark_prompt",
    "build_benchmark_prompt_payload",
    "build_prompt_sections_for_format",
    "build_relevant_summary_context",
    "build_mode_description",
    "build_runtime_prompt_block",
    "build_scenario_instruction_block",
    "validate_artifact_generator_mode",
    "validate_working_context_format",
]
