# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
OpenAI Codex benchmark adapter for Persistent Reasoning Light.

This module defines the controlled benchmark execution flow for OpenAI Codex-based
benchmark runs, including scenario loading, mode-aware context loading,
prompt construction, event logging, and raw log writing.

This adapter does not compute final benchmark result metrics.
Result artifacts must be derived separately from *.events.jsonl files.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmark_adapters.common.artifact_suggestion_utils import (
    ARTIFACT_PARSE_MALFORMED,
    ARTIFACT_PARSE_MISSING,
    ARTIFACT_PARSE_NONE,
    ARTIFACT_PARSE_VALID,
    build_artifact_generation_telemetry,
    parse_benchmark_artifact_suggestions,
)
from benchmark_adapters.common.benchmark_modes import (
    BASELINE,
    validate_benchmark_mode,
)
from benchmark_adapters.common.benchmark_paths import (
    BenchmarkPaths,
    benchmark_brain_root_for_mode,
    get_benchmark_paths,
    result_events_path,
    result_log_path,
)
from benchmark_adapters.common.benchmark_prompt_utils import (
    ARTIFACT_GENERATOR_MODE_CONSTRAINED,
    ARTIFACT_GENERATOR_MODE_SHADOW,
    DEFAULT_ARTIFACT_GENERATOR_MODE,
    DEFAULT_WORKING_CONTEXT_FORMAT,
    active_artifact_generator_mode_for_prompt,
    build_benchmark_prompt,
    build_benchmark_prompt_payload,
    build_relevant_summary_context,
    validate_artifact_generator_mode,
    validate_working_context_format,
)
from benchmark_adapters.common.event_log_utils import BenchmarkEventLogger
from benchmark_adapters.common.result_utils import save_raw_log
from benchmark_adapters.common.scenario_utils import (
    BenchmarkScenario,
    load_benchmark_scenario,
)
from benchmark_execution.base import ExecutionConfig
from benchmark_execution.openai_executor import OpenAIExecutor
from core.artifact_filter import (
    ACCEPT,
    POSSIBLE_DUPLICATE,
    filter_artifact_suggestion,
)
from reasoning_brain_storage.tools import load_benchmark_visible_working_context
from reasoning_adapters.codex.adapter import (
    extract_artifact_suggestion,
)


DEFAULT_ADAPTER_NAME = "openai_codex"
DEFAULT_FULL_AGENT_NAME = "OpenAI Codex"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_EXECUTION_TIMEOUT_SECONDS = 60
_ARTIFACT_PARSE_CANDIDATE = "candidate"
ARTIFACT_FILTER_MODE_OFF = "off"
ARTIFACT_FILTER_MODE_SHADOW = "shadow"
ARTIFACT_FILTER_MODE_SOFT = "soft"
ARTIFACT_FILTER_MODES = (
    ARTIFACT_FILTER_MODE_OFF,
    ARTIFACT_FILTER_MODE_SHADOW,
    ARTIFACT_FILTER_MODE_SOFT,
)
FILTER_NORMALIZATION_REASON = "Normalized from benchmark artifact for filter evaluation"


def load_scenario(
    paths: BenchmarkPaths,
    scenario_id: str,
) -> BenchmarkScenario:
    """
    Load a benchmark scenario by id.
    """
    return load_benchmark_scenario(paths, scenario_id)


def select_mode(mode: str) -> str:
    """
    Validate and return the benchmark execution mode.
    """
    return validate_benchmark_mode(mode)


def resolve_brain_root(
    paths: BenchmarkPaths,
    mode: str,
) -> Path | None:
    """
    Resolve the benchmark brain root for the selected mode.
    """
    return benchmark_brain_root_for_mode(paths, mode)


def load_mode_context(
    paths: BenchmarkPaths,
    mode: str,
    *,
    scenario_id: str | None = None,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> dict[str, object]:
    """
    Load benchmark-visible working context for the selected mode.

    Baseline mode intentionally returns an empty benchmark-visible context shape.
    PR modes load prepared working context from the benchmark brain root.
    """
    validated_mode = select_mode(mode)
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )

    if validated_mode == BASELINE:
        return {
            "active_task": None,
            "tasks": [],
            "constraints": [],
            "decisions": [],
            "procedures": [],
            "open_issues": [],
        }

    brain_root = resolve_brain_root(paths, validated_mode)
    if brain_root is None:
        raise ValueError(f"brain root must exist for mode: {validated_mode}")

    _validate_required_benchmark_brain_files(brain_root)
    context = load_benchmark_visible_working_context(root=brain_root)
    if validated_working_context_format == DEFAULT_WORKING_CONTEXT_FORMAT:
        return context
    if scenario_id is None:
        raise ValueError(
            "scenario_id is required when working_context_format is relevant_summaries"
        )
    return build_relevant_summary_context(
        context,
        brain_root=brain_root,
        scenario_id=scenario_id,
    )


def build_prompt(
    paths: BenchmarkPaths,
    scenario: BenchmarkScenario,
    *,
    mode: str,
    adapter_name: str,
    task_text: str,
    extra_references: Sequence[str] = (),
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> str:
    """
    Build a benchmark prompt for OpenAI Codex execution.
    """
    validated_adapter = _validate_adapter_name(adapter_name)
    validated_task = _normalize_required_text(task_text, "task_text")
    validated_references = _normalize_string_sequence(
        extra_references,
        "extra_references",
    )
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )

    context = load_mode_context(
        paths,
        mode,
        scenario_id=scenario.scenario_id,
        working_context_format=validated_working_context_format,
    )
    return build_benchmark_prompt(
        scenario,
        context,
        mode=mode,
        adapter_name=validated_adapter,
        task_text=validated_task,
        extra_references=validated_references,
        artifact_generator_mode=artifact_generator_mode,
        working_context_format=validated_working_context_format,
    )


def build_prompt_payload(
    paths: BenchmarkPaths,
    scenario: BenchmarkScenario,
    *,
    mode: str,
    adapter_name: str,
    task_text: str,
    extra_references: Sequence[str] = (),
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
) -> dict[str, Any]:
    """
    Build a structured benchmark prompt payload for callers that prefer
    structured transport over flat prompt text.
    """
    validated_adapter = _validate_adapter_name(adapter_name)
    validated_task = _normalize_required_text(task_text, "task_text")
    validated_references = _normalize_string_sequence(
        extra_references,
        "extra_references",
    )
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )

    context = load_mode_context(
        paths,
        mode,
        scenario_id=scenario.scenario_id,
        working_context_format=validated_working_context_format,
    )
    return build_benchmark_prompt_payload(
        scenario,
        context,
        mode=mode,
        adapter_name=validated_adapter,
        task_text=validated_task,
        extra_references=validated_references,
        artifact_generator_mode=artifact_generator_mode,
        working_context_format=validated_working_context_format,
    )


def extract_suggestion(
    agent_output: Mapping[str, object] | str,
) -> dict[str, object]:
    """
    Extract a validated artifact suggestion from OpenAI Codex output.
    """
    return extract_artifact_suggestion(agent_output)


def parse_agent_artifact_output(
    agent_output: str | None,
) -> dict[str, object] | None:
    """
    Parse a candidate artifact suggestion from agent output text.

    Returns None when no artifact suggestion is provided.
    """
    if agent_output is None:
        return None

    if not isinstance(agent_output, str):
        raise ValueError("agent_output must be a string or null")

    if not agent_output:
        return None

    artifact_payload = _extract_artifact_suggestion_payload(agent_output)
    if artifact_payload is None:
        return None
    suggestions = parse_benchmark_artifact_suggestions(artifact_payload)
    return suggestions[0] if suggestions else None


def serialize_prompt_payload(payload: Mapping[str, object]) -> str:
    """
    Serialize a structured benchmark payload for deterministic transport or inspection.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")

    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def build_raw_log_text(
    scenario: BenchmarkScenario,
    *,
    mode: str,
    adapter_name: str,
    prompt: str,
    task_text: str,
    agent_output: str,
    suggestion: Mapping[str, object] | None,
) -> str:
    """
    Build a deterministic raw benchmark log text.

    This helper expects task_text and agent_output to already be normalized.
    """
    validated_mode = select_mode(mode)
    validated_adapter = _validate_adapter_name(adapter_name)

    lines = [
        "Persistent Reasoning Light Benchmark Log",
        f"scenario_id: {scenario.scenario_id}",
        f"scenario_name: {scenario.config['scenario_name']}",
        f"scenario_type: {scenario.config['scenario_type']}",
        f"adapter: {validated_adapter}",
        f"mode: {validated_mode}",
        "",
        "Task:",
        task_text,
        "",
        "Prompt:",
        prompt,
        "",
        "Agent Output:",
        agent_output,
    ]

    return "\n".join(lines)


def run_scenario(
    scenario_id: str,
    *,
    mode: str,
    task_text: str,
    agent_output: str,
    adapter_name: str = DEFAULT_ADAPTER_NAME,
    extra_references: Sequence[str] = (),
    artifact_generator_mode: str = DEFAULT_ARTIFACT_GENERATOR_MODE,
    working_context_format: str = DEFAULT_WORKING_CONTEXT_FORMAT,
    artifact_generator_shadow_output: str | None = None,
    artifact_filter_shadow_mode: bool = False,
    artifact_filter_mode: str = ARTIFACT_FILTER_MODE_OFF,
    repo_root: Path | None = None,
    overwrite_existing_artifacts: bool = False,
) -> dict[str, Any]:
    """
    Run a single controlled benchmark scenario for the OpenAI Codex benchmark adapter.

    This function:
    - loads scenario definition
    - resolves mode and benchmark paths
    - builds benchmark prompt
    - emits benchmark event log
    - writes raw trace log

    It does not:
    - compute final benchmark metrics
    - write result.json
    - compare results
    - generate summary reports
    - mutate canonical reasoning-brain
    """
    validated_mode = select_mode(mode)
    validated_adapter = _validate_adapter_name(adapter_name)
    validated_task = _normalize_required_text(task_text, "task_text")
    validated_references = _normalize_string_sequence(
        extra_references,
        "extra_references",
    )
    normalized_agent_output = _normalize_agent_output_text(agent_output)
    validated_artifact_generator_mode = validate_artifact_generator_mode(
        artifact_generator_mode
    )
    active_artifact_generator_mode = active_artifact_generator_mode_for_prompt(
        validated_artifact_generator_mode
    )
    shadow_mode_enabled = validated_artifact_generator_mode == ARTIFACT_GENERATOR_MODE_SHADOW
    resolved_artifact_filter_mode = _resolve_artifact_filter_mode(
        artifact_filter_mode,
        artifact_filter_shadow_mode=artifact_filter_shadow_mode,
    )
    validated_working_context_format = validate_working_context_format(
        working_context_format
    )
    normalized_shadow_output = _normalize_optional_agent_output_text(
        artifact_generator_shadow_output,
        "artifact_generator_shadow_output",
    )

    paths = get_benchmark_paths(repo_root)
    scenario = load_scenario(paths, scenario_id)
    prompt = build_prompt(
        paths,
        scenario,
        mode=validated_mode,
        adapter_name=validated_adapter,
        task_text=validated_task,
        extra_references=validated_references,
        artifact_generator_mode=active_artifact_generator_mode,
        working_context_format=validated_working_context_format,
    )
    shadow_prompt = None
    if shadow_mode_enabled:
        shadow_prompt = build_prompt(
            paths,
            scenario,
            mode=validated_mode,
            adapter_name=validated_adapter,
            task_text=validated_task,
            extra_references=validated_references,
            artifact_generator_mode=ARTIFACT_GENERATOR_MODE_CONSTRAINED,
            working_context_format=validated_working_context_format,
        )
    context = load_mode_context(
        paths,
        validated_mode,
        scenario_id=scenario.scenario_id,
        working_context_format=validated_working_context_format,
    )

    event_path = result_events_path(paths, validated_mode, scenario.scenario_id)
    logger = BenchmarkEventLogger(
        event_log_path=event_path,
        scenario_id=scenario.scenario_id,
        mode=validated_mode,
        auto_reset=True,
        allow_overwrite=overwrite_existing_artifacts,
    )

    logger.log_task_started()

    if validated_mode != BASELINE:
        logger.log_working_context_loaded(
            {"reference_count": _count_context_references(context)}
        )

    logger.log_reasoning_step(
        {
            "task_text": validated_task,
            "execution_phase": "started",
        }
    )

    execution_source = "manual_override" if normalized_agent_output else "openai_executor"
    token_usage = _empty_token_usage()

    try:
        executor: OpenAIExecutor | None = None
        if not normalized_agent_output:
            executor = _build_openai_executor()
            normalized_agent_output = executor.execute(
                prompt,
                timeout_seconds=OPENAI_EXECUTION_TIMEOUT_SECONDS,
            )
            token_usage = _normalize_token_usage(getattr(executor, "last_token_usage", None))

        artifact_parser_outcome, suggestions = _classify_agent_artifact_outputs(
            normalized_agent_output
        )
        shadow_telemetry = None
        if shadow_mode_enabled:
            shadow_telemetry = _evaluate_shadow_artifact_generation(
                shadow_prompt=shadow_prompt,
                shadow_output=normalized_shadow_output,
                executor=executor,
            )
        filter_telemetry = None
        if resolved_artifact_filter_mode != ARTIFACT_FILTER_MODE_OFF:
            filter_telemetry = _evaluate_artifact_filter(
                suggestions=suggestions,
                parser_outcome=artifact_parser_outcome,
                mode=resolved_artifact_filter_mode,
            )

        for suggestion in suggestions:
            logger.log_artifact_suggested(
                {
                    "artifact_id": suggestion["id"],
                    "artifact_type": suggestion["type"],
                    "artifact_candidate": dict(suggestion),
                }
            )

        completion_payload = {
            "success": True,
            "execution_source": execution_source,
            "artifact_generation": _build_artifact_generation_telemetry(
                artifact_parser_outcome,
                suggestions,
            ),
        }
        if shadow_telemetry is not None:
            completion_payload["artifact_generation_shadow"] = shadow_telemetry
        if filter_telemetry is not None:
            if resolved_artifact_filter_mode == ARTIFACT_FILTER_MODE_SHADOW:
                completion_payload["artifact_filter_shadow"] = filter_telemetry
            elif resolved_artifact_filter_mode == ARTIFACT_FILTER_MODE_SOFT:
                completion_payload["artifact_filter"] = filter_telemetry
        logger.log_task_completed(completion_payload)
    except Exception as exc:
        suggestions = []
        normalized_agent_output = normalized_agent_output if normalized_agent_output else ""
        logger.log_task_failed(
            {
                "success": False,
                "execution_source": execution_source,
                "failure_reason": str(exc),
                "failure_type": type(exc).__name__,
            }
        )

    raw_log = build_raw_log_text(
        scenario,
        mode=validated_mode,
        adapter_name=validated_adapter,
        prompt=prompt,
        task_text=validated_task,
        agent_output=normalized_agent_output,
        suggestion=suggestions[0] if suggestions else None,
    )

    log_path = result_log_path(paths, validated_mode, scenario.scenario_id)
    save_raw_log(
        log_path,
        raw_log,
        overwrite=overwrite_existing_artifacts,
    )

    return {
        "scenario": scenario,
        "mode": validated_mode,
        "prompt": prompt,
        "context": context,
        "artifact_suggestion": suggestions[0] if suggestions else None,
        "artifact_suggestions": [dict(suggestion) for suggestion in suggestions],
        "token_usage": token_usage,
        "event_log_path": event_path,
        "raw_log_path": log_path,
    }


def _count_context_references(context: Mapping[str, object]) -> int:
    count = 0
    if isinstance(context.get("active_task"), str):
        count += 1

    for field in ("tasks", "constraints", "decisions", "procedures", "open_issues"):
        value = context.get(field)
        if isinstance(value, list):
            count += len(value)

    return count


def _empty_token_usage() -> dict[str, int | None]:
    return {
        "prompt_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }


def _normalize_token_usage(value: object) -> dict[str, int | None]:
    if not isinstance(value, Mapping):
        return _empty_token_usage()

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


def _build_openai_executor() -> OpenAIExecutor:
    api_key = _require_env_var("OPENAI_API_KEY")
    model = resolve_openai_model()

    config = ExecutionConfig(model=model)
    return OpenAIExecutor(
        config=config,
        api_key=api_key,
    )


def resolve_openai_model() -> str:
    return _read_optional_env_var("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL


def get_benchmark_agent_metadata(
    *,
    adapter_name: str = DEFAULT_ADAPTER_NAME,
) -> dict[str, str]:
    validated_adapter = _validate_adapter_name(adapter_name)
    return {
        "adapter": validated_adapter,
        "full_agent_name": DEFAULT_FULL_AGENT_NAME,
        "agent_model": resolve_openai_model(),
    }


def _parse_agent_artifact_output_or_none(
    agent_output: str | None,
) -> dict[str, object] | None:
    try:
        return parse_agent_artifact_output(agent_output)
    except ValueError:
        return None


def _parse_agent_artifact_outputs_or_none(
    agent_output: str | None,
) -> list[dict[str, object]] | None:
    if agent_output is None or not isinstance(agent_output, str):
        return None
    payload = _extract_artifact_suggestion_payload(agent_output)
    if payload is None:
        return None
    try:
        return parse_benchmark_artifact_suggestions(payload)
    except ValueError:
        return None


def _classify_agent_artifact_output(
    agent_output: str | None,
) -> tuple[str, dict[str, object] | None]:
    if agent_output is None:
        return ARTIFACT_PARSE_MISSING, None

    if not isinstance(agent_output, str):
        return ARTIFACT_PARSE_MALFORMED, None

    payload_status, _payload = _extract_artifact_suggestion_payload_with_status(agent_output)
    if payload_status == ARTIFACT_PARSE_MISSING:
        return ARTIFACT_PARSE_MISSING, None
    if payload_status == ARTIFACT_PARSE_NONE:
        return ARTIFACT_PARSE_NONE, None

    suggestions = _parse_agent_artifact_outputs_or_none(agent_output)
    if suggestions is None:
        return ARTIFACT_PARSE_MALFORMED, None
    return ARTIFACT_PARSE_VALID, suggestions[0] if suggestions else None


def _classify_agent_artifact_outputs(
    agent_output: str | None,
) -> tuple[str, list[dict[str, object]]]:
    if agent_output is None:
        return ARTIFACT_PARSE_MISSING, []
    if not isinstance(agent_output, str):
        return ARTIFACT_PARSE_MALFORMED, []
    payload_status, _payload = _extract_artifact_suggestion_payload_with_status(agent_output)
    if payload_status == ARTIFACT_PARSE_MISSING:
        return ARTIFACT_PARSE_MISSING, []
    if payload_status == ARTIFACT_PARSE_NONE:
        return ARTIFACT_PARSE_NONE, []
    suggestions = _parse_agent_artifact_outputs_or_none(agent_output)
    if suggestions is None:
        return ARTIFACT_PARSE_MALFORMED, []
    if not suggestions:
        return ARTIFACT_PARSE_NONE, []
    return ARTIFACT_PARSE_VALID, suggestions


def _build_artifact_generation_telemetry(
    parser_outcome: str,
    suggestions: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    return build_artifact_generation_telemetry(parser_outcome, suggestions)


def _build_artifact_generation_shadow_telemetry(
    parser_outcome: str,
    suggestions: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    telemetry = _build_artifact_generation_telemetry(parser_outcome, suggestions)
    telemetry["enabled"] = True
    return telemetry


def _evaluate_shadow_artifact_generation(
    *,
    shadow_prompt: str | None,
    shadow_output: str | None,
    executor: OpenAIExecutor | None,
) -> dict[str, object]:
    try:
        resolved_shadow_output = shadow_output
        if resolved_shadow_output is None:
            if shadow_prompt is None:
                raise ValueError("shadow prompt was not built")
            shadow_executor = executor or _build_openai_executor()
            resolved_shadow_output = shadow_executor.execute(
                shadow_prompt,
                timeout_seconds=OPENAI_EXECUTION_TIMEOUT_SECONDS,
            )

        shadow_outcome, shadow_suggestions = _classify_agent_artifact_outputs(
            resolved_shadow_output
        )
        return _build_artifact_generation_shadow_telemetry(
            shadow_outcome,
            shadow_suggestions,
        )
    except Exception as exc:
        telemetry = _build_artifact_generation_shadow_telemetry(ARTIFACT_PARSE_MISSING)
        telemetry["error_type"] = type(exc).__name__
        telemetry["error_message"] = str(exc)
        return telemetry


def _evaluate_artifact_filter(
    *,
    suggestions: Sequence[Mapping[str, object]] | None = None,
    suggestion: Mapping[str, object] | None = None,
    parser_outcome: str,
    mode: str,
) -> dict[str, object]:
    if suggestions is None:
        suggestions = [suggestion] if suggestion is not None else []
    if not suggestions:
        return _build_artifact_filter_skipped(parser_outcome, mode=mode)

    items = [
        _evaluate_single_artifact_filter(suggestion, mode=mode)
        for suggestion in suggestions
    ]
    first = items[0]
    telemetry = {
        "enabled": True,
        "mode": mode,
        "status": "evaluated",
        "verdict": first["verdict"],
        "reasons": first["reasons"],
        "structural_valid": first["structural_valid"],
        "prohibited_flag": any(bool(item["prohibited_flag"]) for item in items),
        "duplicate_flag": any(bool(item["duplicate_flag"]) for item in items),
        "semantic_valid": all(bool(item["semantic_valid"]) for item in items),
        "raw_verdict": first["raw_verdict"],
        "items": items,
    }
    if len(items) > 1:
        telemetry["verdict"] = (
            "accepted" if all(item["verdict"] == "accepted" for item in items) else "rejected"
        )
        telemetry["raw_verdict"] = "MULTI"
        telemetry["reasons"] = [
            reason
            for item in items
            for reason in item["reasons"]
        ]
    return telemetry


def _evaluate_single_artifact_filter(
    suggestion: Mapping[str, object],
    *,
    mode: str,
) -> dict[str, object]:
    try:
        filter_input = _normalize_artifact_for_filter_input(suggestion)
        result = filter_artifact_suggestion(filter_input, existing_artifacts=())
    except Exception as exc:
        return {
            "artifact_id": suggestion.get("id"),
            "artifact_type": suggestion.get("type"),
            "mode": mode,
            "verdict": "rejected",
            "reasons": [str(exc)],
            "structural_valid": False,
            "prohibited_flag": False,
            "duplicate_flag": False,
            "semantic_valid": False,
            "raw_verdict": type(exc).__name__,
        }

    reason = result.reason
    return {
        "artifact_id": suggestion.get("id"),
        "artifact_type": suggestion.get("type"),
        "mode": mode,
        "verdict": "accepted" if result.verdict == ACCEPT else "rejected",
        "reasons": [reason] if reason else [],
        "structural_valid": not _is_filter_structural_rejection(reason),
        "prohibited_flag": "reasoning trace" in reason.lower(),
        "duplicate_flag": result.verdict == POSSIBLE_DUPLICATE,
        "semantic_valid": result.verdict == ACCEPT,
        "raw_verdict": result.verdict,
    }


def _build_artifact_filter_skipped(parser_outcome: str, *, mode: str) -> dict[str, object]:
    return {
        "enabled": True,
        "mode": mode,
        "status": "skipped",
        "verdict": None,
        "reasons": [],
        "structural_valid": None,
        "prohibited_flag": False,
        "duplicate_flag": False,
        "semantic_valid": None,
        "parser_outcome": parser_outcome,
    }


def _is_filter_structural_rejection(reason: str) -> bool:
    normalized_reason = reason.lower()
    structural_fragments = (
        "artifact data must be a mapping",
        "artifact id",
        "artifact type",
        "invalid artifact",
        "missing required fields",
        "unexpected artifact fields",
        "must be a string",
        "must be a list",
    )
    return any(fragment in normalized_reason for fragment in structural_fragments)


def _normalize_artifact_for_filter_input(
    suggestion: Mapping[str, object],
) -> dict[str, object]:
    artifact = dict(suggestion)
    artifact_type = artifact.get("type")

    if not isinstance(artifact_type, str):
        return artifact

    if artifact_type.endswith("Card"):
        return artifact

    summary = artifact.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return artifact

    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return artifact

    normalized_summary = summary.strip()
    normalized_id = _normalize_artifact_id_for_filter_input(
        artifact_id.strip(),
        artifact_type,
    )

    if artifact_type == "task":
        return {
            "id": normalized_id,
            "type": "TaskCard",
            "goal": normalized_summary,
            "status": "proposed",
            "context": [],
        }

    if artifact_type == "decision":
        return {
            "id": normalized_id,
            "type": "DecisionCard",
            "statement": normalized_summary,
            "reason": [FILTER_NORMALIZATION_REASON],
            "status": "proposed",
        }

    if artifact_type in {"constraint", "invariant"}:
        return {
            "id": normalized_id,
            "type": "ConstraintCard",
            "statement": normalized_summary,
            "reason": [FILTER_NORMALIZATION_REASON],
        }

    if artifact_type == "procedure":
        return {
            "id": normalized_id,
            "type": "ProcedureCard",
            "name": normalized_summary,
            "steps": [FILTER_NORMALIZATION_REASON],
        }

    return artifact


def _normalize_artifact_id_for_filter_input(artifact_id: str, artifact_type: str) -> str:
    prefix_by_type = {
        "task": "task",
        "decision": "decision",
        "constraint": "constraint",
        "invariant": "constraint",
        "procedure": "procedure",
    }
    required_prefix = prefix_by_type.get(artifact_type)
    if required_prefix is None:
        return artifact_id
    if artifact_id.startswith(f"{required_prefix}_"):
        return artifact_id
    return f"{required_prefix}_{artifact_id}"


def _resolve_artifact_filter_mode(
    value: object,
    *,
    artifact_filter_shadow_mode: object,
) -> str:
    shadow_enabled = _normalize_bool(
        artifact_filter_shadow_mode,
        "artifact_filter_shadow_mode",
    )
    validated_mode = _validate_artifact_filter_mode(value)

    if shadow_enabled and validated_mode == ARTIFACT_FILTER_MODE_OFF:
        return ARTIFACT_FILTER_MODE_SHADOW
    if shadow_enabled and validated_mode != ARTIFACT_FILTER_MODE_SHADOW:
        raise ValueError("artifact_filter_shadow_mode conflicts with artifact_filter_mode")
    return validated_mode


def _validate_artifact_filter_mode(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("artifact_filter_mode must be a string")
    cleaned = value.strip()
    if cleaned != value:
        raise ValueError("artifact_filter_mode must not contain surrounding whitespace")
    if cleaned not in ARTIFACT_FILTER_MODES:
        allowed = ", ".join(ARTIFACT_FILTER_MODES)
        raise ValueError(f"artifact_filter_mode must be one of: {allowed}")
    return cleaned


def _validate_required_benchmark_brain_files(brain_root: Path) -> None:
    required_paths = [
        brain_root / "views" / "working_context.json",
    ]

    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        joined = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"required benchmark brain files are missing: {joined}")

    invalid_paths = [path for path in required_paths if not path.is_file()]
    if invalid_paths:
        joined = ", ".join(str(path) for path in invalid_paths)
        raise ValueError(f"required benchmark brain paths must be files: {joined}")


def _require_env_var(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"required environment variable is missing: {name}")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"required environment variable is empty: {name}")

    return cleaned


def _read_optional_env_var(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"optional environment variable must not be empty when set: {name}")

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


def _normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


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


def _normalize_agent_output_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("agent_output must be a string")
    return value.strip()


def _normalize_optional_agent_output_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value.strip()


def _normalize_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _extract_artifact_suggestion_payload(agent_output: str) -> str | None:
    payload_status, payload = _extract_artifact_suggestion_payload_with_status(agent_output)
    if payload_status != _ARTIFACT_PARSE_CANDIDATE:
        return None
    return payload


def _extract_artifact_suggestion_payload_with_status(
    agent_output: str,
) -> tuple[str, str | None]:
    marker = "Artifact Suggestion:"
    marker_index = agent_output.find(marker)
    if marker_index < 0:
        return ARTIFACT_PARSE_MISSING, None

    marker_tail = agent_output[marker_index + len(marker):]
    line_break_index = _find_first_line_break_index(marker_tail)
    if line_break_index < 0:
        payload = marker_tail.strip()
    else:
        same_line_payload = marker_tail[:line_break_index].strip()
        if same_line_payload:
            payload = same_line_payload
        else:
            payload = marker_tail[line_break_index:].strip()

    if not payload:
        return ARTIFACT_PARSE_MISSING, None
    if payload.upper() == "NONE":
        return ARTIFACT_PARSE_NONE, None
    return _ARTIFACT_PARSE_CANDIDATE, payload


def _find_first_line_break_index(value: str) -> int:
    indexes = [index for index in (value.find("\n"), value.find("\r")) if index >= 0]
    if not indexes:
        return -1
    return min(indexes)


def _validate_canonical_pr_decision_suggestion(
    suggestion: Mapping[str, object],
) -> dict[str, object]:
    expected_fields = {"id", "type", "summary"}
    unexpected_fields = sorted(set(suggestion) - expected_fields)
    missing_fields = sorted(expected_fields - set(suggestion))
    if unexpected_fields:
        raise ValueError(
            "canonical PR benchmark suggestion has unexpected fields: "
            + ", ".join(unexpected_fields)
        )
    if missing_fields:
        raise ValueError(
            "canonical PR benchmark suggestion is missing fields: "
            + ", ".join(missing_fields)
        )

    artifact_id = _normalize_required_text(suggestion.get("id"), "artifact id")
    artifact_type = _normalize_required_text(suggestion.get("type"), "artifact type")
    summary = _normalize_required_text(suggestion.get("summary"), "summary")

    if artifact_type != "decision":
        raise ValueError("canonical PR benchmark suggestion must be a decision")

    return {
        "id": artifact_id,
        "type": artifact_type,
        "summary": summary,
    }


__all__ = [
    "DEFAULT_ADAPTER_NAME",
    "DEFAULT_FULL_AGENT_NAME",
    "build_prompt",
    "build_prompt_payload",
    "build_raw_log_text",
    "extract_suggestion",
    "get_benchmark_agent_metadata",
    "load_mode_context",
    "load_scenario",
    "parse_agent_artifact_output",
    "resolve_brain_root",
    "resolve_openai_model",
    "run_scenario",
    "select_mode",
    "serialize_prompt_payload",
]
