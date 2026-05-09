# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Benchmark event log utilities for Persistent Reasoning Light.

This module defines deterministic helpers for building, validating, writing,
and reading structured benchmark event logs in JSONL format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .benchmark_modes import validate_benchmark_mode
from .benchmark_paths import validate_scenario_id


ALLOWED_EVENT_TYPES = {
    "task_started",
    "task_continued",
    "reasoning_step",
    "context_loaded",
    "working_context_loaded",
    "artifact_suggested",
    "replan_unjustified",
    "lost_task_context",
    "lost_plan_context",
    "constraint_violation_attempt",
    "irrelevant_branch_adoption",
    "resolved_question_reopened",
    "knowledge_rediscovery",
    "task_completed",
    "task_failed",
}

REQUIRED_EVENT_FIELDS = {
    "event_type",
    "step_index",
    "scenario_id",
    "mode",
}

OPTIONAL_EVENT_FIELDS = {
    "timestamp",
    "payload",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_event_type(event_type: str) -> str:
    if event_type not in ALLOWED_EVENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_EVENT_TYPES))
        raise ValueError(
            f"unsupported event_type: '{event_type}'. Allowed event types: {allowed}"
        )
    return event_type


def validate_event_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("event timestamp must be a string")

    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid event timestamp: {value}") from exc

    return value


def validate_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("event payload must be a dictionary")

    try:
        json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except TypeError as exc:
        raise ValueError("event payload must be JSON-serializable") from exc

    return payload


def validate_event_record(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("event record must be a dictionary")

    missing = sorted(field for field in REQUIRED_EVENT_FIELDS if field not in event)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"event record is missing required fields: {joined}")

    unexpected = sorted(
        field
        for field in event
        if field not in REQUIRED_EVENT_FIELDS and field not in OPTIONAL_EVENT_FIELDS
    )
    if unexpected:
        joined = ", ".join(unexpected)
        raise ValueError(f"event record contains unexpected fields: {joined}")

    validate_event_type(event["event_type"])

    if not isinstance(event["step_index"], int) or event["step_index"] < 0:
        raise ValueError("event step_index must be a non-negative integer")

    validated_scenario_id = validate_scenario_id(event["scenario_id"])
    validated_mode = validate_benchmark_mode(event["mode"])

    if "payload" in event:
        validate_event_payload(event["payload"])

    if "timestamp" in event:
        validate_event_timestamp(event["timestamp"])

    validated_event = dict(event)
    validated_event["scenario_id"] = validated_scenario_id
    validated_event["mode"] = validated_mode
    return validated_event


def build_event(
    event_type: str,
    step_index: int,
    scenario_id: str,
    mode: str,
    payload: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    validated_event_type = validate_event_type(event_type)
    validated_scenario_id = validate_scenario_id(scenario_id)
    validated_mode = validate_benchmark_mode(mode)

    if step_index < 0:
        raise ValueError("step_index must be non-negative")

    event: dict[str, Any] = {
        "event_type": validated_event_type,
        "step_index": step_index,
        "scenario_id": validated_scenario_id,
        "mode": validated_mode,
    }

    if payload is not None:
        event["payload"] = validate_event_payload(payload)

    if timestamp is not None:
        event["timestamp"] = validate_event_timestamp(timestamp)

    return validate_event_record(event)


def append_event(path: Path, event: dict[str, Any]) -> None:
    validated_event = validate_event_record(event)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(validated_event, sort_keys=True, ensure_ascii=False))
        handle.write("\n")


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"event log not found: {path}")
    if not path.is_file():
        raise ValueError(f"event log path is not a file: {path}")

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSONL event at line {line_number}: {path}"
                ) from exc

            if not isinstance(event, dict):
                raise ValueError(
                    f"event must be a JSON object at line {line_number}: {path}"
                )

            validated_event = validate_event_record(event)
            events.append(validated_event)

    return events


def ensure_fresh_event_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    if not path.is_file():
        raise ValueError(f"event log path is not a file: {path}")
    raise FileExistsError(
        f"event log already exists; explicit overwrite is required: {path}"
    )


def reset_event_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file():
            raise ValueError(f"event log path is not a file: {path}")
        path.unlink()


def validate_isolated_event_log(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        raise ValueError(
            f"event log already exists and is not isolated for a fresh run: {path}"
        )


@dataclass
class BenchmarkEventLogger:
    """
    Stateful benchmark event logger for a single isolated scenario run.

    This object intentionally maintains step index state across calls.
    It is not a frozen contract container.
    """

    event_log_path: Path
    scenario_id: str
    mode: str
    auto_reset: bool = False
    allow_overwrite: bool = False
    _step_index: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.scenario_id = validate_scenario_id(self.scenario_id)
        self.mode = validate_benchmark_mode(self.mode)

        if self.auto_reset:
            if self.allow_overwrite:
                reset_event_log(self.event_log_path)
            else:
                ensure_fresh_event_log(self.event_log_path)
        else:
            validate_isolated_event_log(self.event_log_path)

    def next_step(self) -> int:
        self._step_index += 1
        return self._step_index

    def log(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        step_index: int | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        actual_step = self._step_index if step_index is None else step_index
        event = build_event(
            event_type=event_type,
            step_index=actual_step,
            scenario_id=self.scenario_id,
            mode=self.mode,
            payload=payload,
            timestamp=timestamp,
        )
        append_event(self.event_log_path, event)
        return event

    def log_next(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        step = self.next_step()
        return self.log(
            event_type=event_type,
            payload=payload,
            step_index=step,
            timestamp=timestamp,
        )

    def log_task_started(self, timestamp: str | None = None) -> dict[str, Any]:
        return self.log_next("task_started", timestamp=timestamp)

    def log_reasoning_step(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next("reasoning_step", payload=payload, timestamp=timestamp)

    def log_context_loaded(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next("context_loaded", payload=payload, timestamp=timestamp)

    def log_working_context_loaded(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next(
            "working_context_loaded",
            payload=payload,
            timestamp=timestamp,
        )

    def log_artifact_suggested(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next("artifact_suggested", payload=payload, timestamp=timestamp)

    def log_task_completed(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next("task_completed", payload=payload, timestamp=timestamp)

    def log_task_failed(
        self,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        return self.log_next("task_failed", payload=payload, timestamp=timestamp)


__all__ = [
    "ALLOWED_EVENT_TYPES",
    "BenchmarkEventLogger",
    "OPTIONAL_EVENT_FIELDS",
    "REQUIRED_EVENT_FIELDS",
    "append_event",
    "build_event",
    "ensure_fresh_event_log",
    "read_events",
    "utc_now_iso",
    "validate_event_payload",
    "validate_event_record",
    "validate_event_timestamp",
    "validate_event_type",
    "validate_isolated_event_log",
]
