# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Compute benchmark result metrics from structured benchmark event logs.

This tool derives result.json artifacts from *.events.jsonl files only.
It must not depend on adapter-specific hidden state or execution internals.

Some metrics may be computed directly from event payloads, while others may use
explicit fallback or placeholder derivation when the event stream does not
contain richer benchmark signals.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.event_log_utils import read_events
from benchmark_adapters.common.result_utils import (
    build_result_json,
    save_result_json,
    validate_adapter_name,
)


# This tool intentionally derives metrics from observable event streams only.
# It must not query adapter-specific internal state or runtime-only hidden signals.


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute benchmark result metrics from .events.jsonl files."
    )
    parser.add_argument(
        "--events",
        required=True,
        help="Path to <scenario_id>.events.jsonl",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to <scenario_id>.result.json",
    )
    parser.add_argument(
        "--adapter-name",
        required=True,
        help="Adapter name to include in result metadata",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional explicit result timestamp in UTC ISO format",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing result output file.",
    )
    return parser.parse_args()


def load_events(path: Path) -> list[dict[str, Any]]:
    return read_events(path)


def compute_result_from_events(
    events: list[dict[str, Any]],
    *,
    adapter_name: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """
    Compute a benchmark result artifact from a validated event stream.

    This helper treats step_index as the primary deterministic completion anchor.
    It does not derive completion steps from raw event count.

    Required event-level identity fields:
    - scenario_id
    - mode
    - event_type
    - step_index

    Some benchmark metrics additionally depend on optional payload fields such as:
    - task_text
    - reference_count
    - files_read
    - raw_tokens
    - curated_tokens
    - relevant_tokens
    - total_retrieved_tokens
    - tokens_read_per_query

    When optional payload fields are absent, this helper uses explicit fallback
    values or scaffold derivation rather than adapter-specific hidden logic.

    Timing metrics such as:
    - time_to_context_ms
    - execution_time_ms

    are derived only when compatible event timestamps are present.
    If timestamps are absent, these metrics fall back to 0.
    """
    if not events:
        raise ValueError("events list must not be empty")

    validated_adapter = validate_adapter_name(adapter_name)

    scenario_id = _extract_single_value(events, "scenario_id")
    mode = _extract_single_value(events, "mode")

    max_step_index = max(event["step_index"] for event in events)
    steps_to_completion = max_step_index

    reasoning_steps = _count_event_type(events, "reasoning_step")
    replanning_events = _count_event_type(events, "replan_unjustified")
    lost_task_context = _count_event_type(events, "lost_task_context")
    lost_plan_context = _count_event_type(events, "lost_plan_context")
    context_loss_events = lost_task_context + lost_plan_context
    rediscovery_events = _count_event_type(events, "knowledge_rediscovery")
    artifact_suggestions = _count_event_type(events, "artifact_suggested")
    constraint_violations = _count_event_type(events, "constraint_violation_attempt")
    irrelevant_branch_events = _count_event_type(events, "irrelevant_branch_adoption")

    completed = _count_event_type(events, "task_completed")
    failed = _count_event_type(events, "task_failed")

    if completed and failed:
        raise ValueError("event stream must not contain both task_completed and task_failed")

    task_success = completed > 0

    explicit_tokens_read = _extract_latest_payload_int(
        events,
        "context_loaded",
        "tokens_read_per_query",
    )
    task_text = _extract_latest_payload_string(events, "reasoning_step", "task_text") or ""

    # Fallback proxy: if no explicit token metric is present in event payloads,
    # use task text word count as a simple scaffold estimate.
    if explicit_tokens_read > 0:
        tokens_read_per_query = explicit_tokens_read
    else:
        tokens_read_per_query = len(task_text.split())

    reference_count = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "reference_count",
    )
    files_read_per_query = _extract_latest_payload_int(
        events,
        "context_loaded",
        "files_read",
    )
    time_to_context_ms = _compute_time_to_context_ms(events)
    execution_time_ms = _compute_execution_time_ms(events)

    reasoning_step_denominator = max(reasoning_steps, 1)
    context_reference_denominator = max(reference_count, 1)
    mutation_denominator = max(artifact_suggestions + constraint_violations, 1)

    reasoning_drift_rate = _safe_ratio(
        replanning_events + irrelevant_branch_events,
        reasoning_step_denominator,
    )
    plan_retention_rate = _clamp_0_1(
        1.0 - _safe_ratio(replanning_events, reasoning_step_denominator)
    )
    rediscovery_rate = _safe_ratio(rediscovery_events, reasoning_step_denominator)
    knowledge_retention_rate = _clamp_0_1(
        1.0 - _safe_ratio(rediscovery_events, context_reference_denominator)
    )
    context_utilization_rate = _compute_context_utilization_rate(reference_count)
    reuse_rate = _compute_reuse_rate(
        reference_count=reference_count,
        artifact_suggestions=artifact_suggestions,
    )
    context_growth_rate = _compute_context_growth_rate(events)
    token_efficiency = 1.0 if task_success else 0.0
    token_reduction_ratio = _compute_token_reduction_ratio(events)
    memory_compression_ratio = _compute_memory_compression_ratio(events)
    retrieval_precision = _compute_retrieval_precision(events, reference_count)
    structural_integrity_score = _clamp_0_1(
        1.0
        - _safe_ratio(
            constraint_violations + irrelevant_branch_events,
            reasoning_step_denominator,
        )
    )
    controlled_mutations_ratio = _safe_ratio(artifact_suggestions, mutation_denominator)

    result = build_result_json(
        scenario_id=scenario_id,
        adapter=validated_adapter,
        mode=mode,
        reasoning_drift_rate=reasoning_drift_rate,
        replanning_events=replanning_events,
        context_loss_events=context_loss_events,
        plan_retention_rate=plan_retention_rate,
        rediscovery_rate=rediscovery_rate,
        knowledge_retention_rate=knowledge_retention_rate,
        context_utilization_rate=context_utilization_rate,
        reuse_rate=reuse_rate,
        context_growth_rate=context_growth_rate,
        token_efficiency=token_efficiency,
        token_reduction_ratio=token_reduction_ratio,
        memory_compression_ratio=memory_compression_ratio,
        retrieval_precision=retrieval_precision,
        files_read_per_query=files_read_per_query,
        tokens_read_per_query=tokens_read_per_query,
        time_to_context_ms=time_to_context_ms,
        structural_integrity_score=structural_integrity_score,
        controlled_mutations_ratio=controlled_mutations_ratio,
        artifact_suggested_count=artifact_suggestions,
        execution_time_ms=execution_time_ms,
        steps_to_completion=steps_to_completion,
        task_success=task_success,
        timestamp=timestamp,
    )
    return result


def save_result(path: Path, result: dict[str, Any], *, overwrite: bool = False) -> None:
    save_result_json(path, result, overwrite=overwrite)


def derive_result_artifact(
    events_path: Path,
    *,
    output_path: Path,
    adapter_name: str,
    timestamp: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Canonical event-derivation path for benchmark result.json artifacts.

    This helper is the boundary between execution artifacts and derived result
    artifacts: it loads *.events.jsonl, computes benchmark metrics from events
    only, and writes the canonical *.result.json output.
    """
    events = load_events(events_path)
    result = compute_result_from_events(
        events,
        adapter_name=adapter_name,
        timestamp=timestamp,
    )
    save_result(output_path, result, overwrite=overwrite)
    return result


def _extract_single_value(events: list[dict[str, Any]], key: str) -> str:
    missing_indexes = [
        index
        for index, event in enumerate(events, start=1)
        if key not in event
    ]
    if missing_indexes:
        joined = ", ".join(str(index) for index in missing_indexes)
        raise ValueError(f"event field '{key}' is missing in event(s): {joined}")

    values = {event[key] for event in events}
    if len(values) != 1:
        raise ValueError(f"expected a single shared '{key}' across all events")

    value = next(iter(values))
    if not isinstance(value, str):
        raise ValueError(f"event field '{key}' must be a string")

    return value


def _count_event_type(events: list[dict[str, Any]], event_type: str) -> int:
    return sum(1 for event in events if event["event_type"] == event_type)


def _extract_latest_payload_string(
    events: list[dict[str, Any]],
    event_type: str,
    payload_key: str,
) -> str | None:
    for event in reversed(events):
        if event["event_type"] != event_type:
            continue

        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        value = payload.get(payload_key)
        if isinstance(value, str):
            return value

    return None


def _extract_latest_payload_int(
    events: list[dict[str, Any]],
    event_type: str,
    payload_key: str,
) -> int:
    for event in reversed(events):
        if event["event_type"] != event_type:
            continue

        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        value = payload.get(payload_key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if value is not None:
            raise ValueError(
                f"payload field '{payload_key}' for event_type '{event_type}' must be an integer"
            )

    return 0


def _compute_time_to_context_ms(events: list[dict[str, Any]]) -> int:
    start_ts = _extract_first_timestamp_for_event_type(events, "task_started")
    context_ts = _extract_first_timestamp_for_event_type(events, "working_context_loaded")

    if start_ts is None or context_ts is None:
        return 0

    delta = context_ts - start_ts
    return max(int(delta.total_seconds() * 1000), 0)


def _compute_execution_time_ms(events: list[dict[str, Any]]) -> int:
    start_ts = _extract_first_timestamp_for_event_type(events, "task_started")
    end_ts = (
        _extract_first_timestamp_for_event_type(events, "task_completed")
        or _extract_first_timestamp_for_event_type(events, "task_failed")
    )

    if start_ts is None or end_ts is None:
        return 0

    delta = end_ts - start_ts
    return max(int(delta.total_seconds() * 1000), 0)


def _extract_first_timestamp_for_event_type(
    events: list[dict[str, Any]],
    event_type: str,
) -> datetime | None:
    for event in events:
        if event["event_type"] != event_type:
            continue

        raw_timestamp = event.get("timestamp")
        if not isinstance(raw_timestamp, str):
            continue

        return datetime.strptime(raw_timestamp, "%Y-%m-%dT%H:%M:%SZ")

    return None


def _compute_context_growth_rate(events: list[dict[str, Any]]) -> float:
    initial_context_size = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "reference_count",
    )
    additional_artifacts = _count_event_type(events, "artifact_suggested")
    reasoning_steps = max(_count_event_type(events, "reasoning_step"), 1)

    return _round_metric(
        _safe_ratio(
            additional_artifacts,
            max(initial_context_size, reasoning_steps, 1),
        )
    )


def _compute_context_utilization_rate(reference_count: int) -> float:
    if reference_count <= 0:
        return 0.0
    return 1.0


def _compute_reuse_rate(
    *,
    reference_count: int,
    artifact_suggestions: int,
) -> float:
    return _round_metric(
        _safe_ratio(
            reference_count,
            max(reference_count + artifact_suggestions, 1),
        )
    )


def _compute_token_reduction_ratio(events: list[dict[str, Any]]) -> float:
    raw_tokens = _extract_latest_payload_int(events, "context_loaded", "raw_tokens")
    curated_tokens = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "curated_tokens",
    )

    if raw_tokens <= 0 or curated_tokens < 0 or curated_tokens > raw_tokens:
        return 0.0

    return _round_metric(1.0 - (curated_tokens / raw_tokens))


def _compute_memory_compression_ratio(events: list[dict[str, Any]]) -> float:
    raw_tokens = _extract_latest_payload_int(events, "context_loaded", "raw_tokens")
    curated_tokens = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "curated_tokens",
    )

    if raw_tokens <= 0 or curated_tokens <= 0:
        return 1.0

    return _round_metric(raw_tokens / curated_tokens)


def _compute_retrieval_precision(events: list[dict[str, Any]], reference_count: int) -> float:
    relevant_tokens = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "relevant_tokens",
    )
    total_retrieved_tokens = _extract_latest_payload_int(
        events,
        "working_context_loaded",
        "total_retrieved_tokens",
    )

    if total_retrieved_tokens > 0:
        return _round_metric(_safe_ratio(relevant_tokens, total_retrieved_tokens))

    if reference_count > 0:
        return 1.0

    return 0.0


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _clamp_0_1(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_metric(value: float) -> float:
    return round(value, 6)


def main() -> None:
    args = parse_args()

    events_path = Path(args.events)
    output_path = Path(args.output)

    derive_result_artifact(
        events_path,
        output_path=output_path,
        adapter_name=args.adapter_name,
        timestamp=args.timestamp,
        overwrite=args.overwrite,
    )

    print(f"saved benchmark result json: {output_path}")


if __name__ == "__main__":
    main()
