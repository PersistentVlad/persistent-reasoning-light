# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmark_adapters.common.benchmark_paths import get_benchmark_paths, result_events_path
from benchmark_adapters.common.event_log_utils import read_events
from reasoning_brain_storage.tools import (
    export_governance_brain_state,
    load_brain,
    persist_artifact,
    rebuild_working_context,
)
from reasoning_governance_light import evaluate_artifact


HARVEST_REPORT_FILENAME = "post_run_artifact_harvest.json"


def run_post_run_artifact_harvest(
    *,
    repo_root: Path,
    run_id: str,
    scenario_ids: Sequence[str],
    source_modes: Sequence[str],
    enabled: bool,
    runtime_available: bool,
    skip_reason: str | None = None,
) -> Path:
    paths = get_benchmark_paths(repo_root)
    report_path = paths.reports_root / run_id / HARVEST_REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_post_run_artifact_harvest_report(
        repo_root=repo_root,
        scenario_ids=scenario_ids,
        source_modes=source_modes,
        enabled=enabled,
        runtime_available=runtime_available,
        skip_reason=skip_reason,
    )

    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    return report_path


def build_post_run_artifact_harvest_report(
    *,
    repo_root: Path,
    scenario_ids: Sequence[str],
    source_modes: Sequence[str],
    enabled: bool,
    runtime_available: bool,
    skip_reason: str | None = None,
) -> dict[str, Any]:
    normalized_scenarios = tuple(str(item) for item in scenario_ids)
    normalized_modes = tuple(str(item) for item in source_modes)

    base_report = {
        "enabled": enabled,
        "source_modes": list(normalized_modes),
        "target": "runtime",
        "skip_reason": skip_reason,
        "candidates_seen": 0,
        "accepted": 0,
        "duplicates": 0,
        "rediscovered": 0,
        "rejected": 0,
        "invalid": 0,
        "persisted_count": 0,
        "runtime_updated": False,
        "items": [],
    }

    if not enabled:
        base_report["skip_reason"] = skip_reason or "disabled"
        return base_report

    if not runtime_available:
        base_report["skip_reason"] = skip_reason or "runtime_unavailable_after_lifecycle"
        return base_report

    paths = get_benchmark_paths(repo_root)
    harvested_items: list[dict[str, Any]] = []
    persisted_count = 0

    for mode in normalized_modes:
        for scenario_id in normalized_scenarios:
            events_path = result_events_path(paths, mode, scenario_id)
            if not events_path.exists():
                continue

            for event in read_events(events_path):
                if event.get("event_type") != "artifact_suggested":
                    continue

                item = _build_harvest_item_from_event(event)
                if item["status"] == "invalid":
                    harvested_items.append(item)
                    continue

                candidate = item.pop("_candidate")
                candidate = _normalize_candidate_id_for_scenario(candidate, item.get("scenario_id"))
                normalized_artifact_id = candidate.get("id")
                original_artifact_id = item.get("artifact_id")
                if isinstance(normalized_artifact_id, str):
                    item["artifact_id"] = normalized_artifact_id
                    if (
                        isinstance(original_artifact_id, str)
                        and original_artifact_id != normalized_artifact_id
                    ):
                        item["original_artifact_id"] = original_artifact_id
                try:
                    brain = load_brain(root=paths.runtime_brain_root)
                    brain_state = export_governance_brain_state(brain=brain)
                    decision = evaluate_artifact(candidate, brain_state)
                except Exception as exc:
                    item["status"] = "invalid"
                    item["reason_code"] = f"governance_error:{type(exc).__name__}"
                    item["duplicate_of"] = None
                    item["rediscovered_of"] = None
                    harvested_items.append(item)
                    continue

                item["status"] = decision.status
                item["reason_code"] = decision.reason_code
                item["duplicate_of"] = decision.duplicate_of
                item["rediscovered_of"] = decision.rediscovered_of

                if decision.status == "accepted":
                    try:
                        persist_artifact(
                            runtime_root=paths.runtime_brain_root,
                            artifact=candidate,
                        )
                    except Exception as exc:
                        item["status"] = "invalid"
                        item["reason_code"] = f"storage_error:{type(exc).__name__}"
                        item["duplicate_of"] = None
                        item["rediscovered_of"] = None
                        harvested_items.append(item)
                        continue
                    persisted_count += 1

                harvested_items.append(item)

    if persisted_count > 0:
        rebuild_working_context(runtime_root=paths.runtime_brain_root)

    report = dict(base_report)
    report["items"] = harvested_items
    report["candidates_seen"] = len(harvested_items)
    report["accepted"] = _count_items_with_status(harvested_items, "accepted")
    report["duplicates"] = _count_items_with_status(harvested_items, "duplicate")
    report["rediscovered"] = _count_items_with_status(harvested_items, "rediscovered")
    report["rejected"] = _count_items_with_status(harvested_items, "rejected")
    report["invalid"] = _count_items_with_status(harvested_items, "invalid")
    report["persisted_count"] = persisted_count
    report["runtime_updated"] = persisted_count > 0
    return report


def _build_harvest_item_from_event(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    artifact_candidate = (
        payload.get("artifact_candidate")
        if isinstance(payload, Mapping)
        else None
    )
    artifact_id = None
    artifact_type = None
    if isinstance(payload, Mapping):
        if isinstance(payload.get("artifact_id"), str):
            artifact_id = payload.get("artifact_id")
        if isinstance(payload.get("artifact_type"), str):
            artifact_type = payload.get("artifact_type")

    if not isinstance(artifact_candidate, Mapping):
        return {
            "scenario_id": event.get("scenario_id"),
            "mode": event.get("mode"),
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "status": "invalid",
            "reason_code": "missing_artifact_candidate",
            "duplicate_of": None,
            "rediscovered_of": None,
        }

    candidate_dict = dict(artifact_candidate)
    if isinstance(candidate_dict.get("id"), str):
        artifact_id = candidate_dict["id"]
    if isinstance(candidate_dict.get("type"), str):
        artifact_type = candidate_dict["type"]

    return {
        "scenario_id": event.get("scenario_id"),
        "mode": event.get("mode"),
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "status": "pending",
        "reason_code": "pending_governance",
        "duplicate_of": None,
        "rediscovered_of": None,
        "_candidate": candidate_dict,
    }


def _normalize_candidate_id_for_scenario(
    candidate: Mapping[str, Any],
    scenario_id: object,
) -> dict[str, Any]:
    candidate_dict = dict(candidate)
    artifact_id = candidate_dict.get("id")
    scenario_prefix = _scenario_prefix(scenario_id)
    if not isinstance(artifact_id, str) or scenario_prefix is None:
        return candidate_dict

    if artifact_id.startswith(f"{scenario_prefix}_"):
        return candidate_dict

    candidate_dict["id"] = f"{scenario_prefix}_{artifact_id}"
    return candidate_dict


def _scenario_prefix(scenario_id: object) -> str | None:
    if not isinstance(scenario_id, str):
        return None
    parts = scenario_id.split("_", 2)
    if len(parts) < 2 or parts[0] != "sc" or not parts[1]:
        return None
    return f"{parts[0]}_{parts[1]}"


def _count_items_with_status(items: Sequence[Mapping[str, Any]], status: str) -> int:
    return sum(1 for item in items if item.get("status") == status)


__all__ = [
    "HARVEST_REPORT_FILENAME",
    "build_post_run_artifact_harvest_report",
    "run_post_run_artifact_harvest",
]
