# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

from types import MappingProxyType
from pathlib import Path
from typing import Mapping

from .errors import BrainValidationError
from .load import export_governance_brain_state, load_benchmark_visible_working_context, load_brain
from .policy import CANONICAL_ARTIFACT_DIRECTORY_BY_TYPE
from .types import (
    ArtifactCountDelta,
    BrainDiffSummary,
    SnapshotComparisonResult,
    SnapshotInspectionResult,
    WorkingContextDiff,
    WorkingContextIntersection,
)


def diff_brains(
    *,
    brain_a_root: Path,
    brain_b_root: Path,
) -> BrainDiffSummary:
    """
    Compare two reasoning brains structurally.

    v1:
    - compare canonical persisted artifact ids only
    - duplicate / contradiction counts remain structural placeholders
    """
    inspection_a = inspect_brain_snapshot(root=brain_a_root)
    inspection_b = inspect_brain_snapshot(root=brain_b_root)

    artifact_ids_a = _all_artifact_ids(inspection_a.artifact_ids_by_type)
    artifact_ids_b = _all_artifact_ids(inspection_b.artifact_ids_by_type)
    added = artifact_ids_b - artifact_ids_a
    removed = artifact_ids_a - artifact_ids_b

    return BrainDiffSummary(
        added_count=len(added),
        removed_count=len(removed),
        duplicate_candidates_count=0,
        contradiction_candidates_count=0,
    )


def inspect_brain_snapshot(*, root: Path) -> SnapshotInspectionResult:
    """
    Inspect a snapshot or other canonical brain root using persisted artifacts and
    benchmark-visible working_context only.
    """
    brain = load_brain(root=root)
    working_context = load_benchmark_visible_working_context(root=root)
    governance_state = export_governance_brain_state(brain=brain)
    artifact_summary = _summarize_artifacts(governance_state["artifacts_by_id"])

    return SnapshotInspectionResult(
        brain_root=root,
        working_context=MappingProxyType(dict(working_context)),
        artifact_count_total=sum(artifact_summary["artifact_count_by_type"].values()),
        artifact_count_by_type=MappingProxyType(
            dict(artifact_summary["artifact_count_by_type"])
        ),
        artifact_ids_by_type=MappingProxyType(
            dict(artifact_summary["artifact_ids_by_type"])
        ),
    )


def compare_brain_snapshots(
    *,
    snapshot_a_root: Path,
    snapshot_b_root: Path,
) -> SnapshotComparisonResult:
    """
    Compare two snapshots using canonical persisted artifacts and benchmark-visible
    working_context only.
    """
    inspection_a = inspect_brain_snapshot(root=snapshot_a_root)
    inspection_b = inspect_brain_snapshot(root=snapshot_b_root)
    artifacts_a = _load_artifacts_by_id(snapshot_a_root)
    artifacts_b = _load_artifacts_by_id(snapshot_b_root)
    brain_diff_summary = diff_brains(
        brain_a_root=snapshot_a_root,
        brain_b_root=snapshot_b_root,
    )

    added_ids, removed_ids, shared_ids, mismatched_ids = _classify_artifact_ids(
        artifacts_a,
        artifacts_b,
    )

    return SnapshotComparisonResult(
        snapshot_a_root=snapshot_a_root,
        snapshot_b_root=snapshot_b_root,
        working_context_diff=_compare_working_context(
            inspection_a.working_context,
            inspection_b.working_context,
        ),
        working_context_intersection=_intersect_working_context(
            inspection_a.working_context,
            inspection_b.working_context,
            shared_ids=shared_ids,
        ),
        artifact_count_total=ArtifactCountDelta(
            a=inspection_a.artifact_count_total,
            b=inspection_b.artifact_count_total,
            delta=inspection_b.artifact_count_total - inspection_a.artifact_count_total,
        ),
        artifact_count_by_type=MappingProxyType(
            {
                artifact_type: ArtifactCountDelta(
                    a=inspection_a.artifact_count_by_type[artifact_type],
                    b=inspection_b.artifact_count_by_type[artifact_type],
                    delta=(
                        inspection_b.artifact_count_by_type[artifact_type]
                        - inspection_a.artifact_count_by_type[artifact_type]
                    ),
                )
                for artifact_type in _canonical_artifact_types()
            }
        ),
        artifact_ids=MappingProxyType(
            {
                "added": added_ids,
                "removed": removed_ids,
                "shared": shared_ids,
                "mismatched": mismatched_ids,
            }
        ),
        artifact_ids_by_type=MappingProxyType(
            _build_artifact_ids_by_type(
                artifacts_a=artifacts_a,
                artifacts_b=artifacts_b,
                added_ids=added_ids,
                removed_ids=removed_ids,
                shared_ids=shared_ids,
                mismatched_ids=mismatched_ids,
            )
        ),
        brain_diff_summary=brain_diff_summary,
    )


def _compare_working_context(
    context_a: Mapping[str, object],
    context_b: Mapping[str, object],
) -> WorkingContextDiff:
    active_task_a = _optional_string(context_a.get("active_task"))
    active_task_b = _optional_string(context_b.get("active_task"))
    return WorkingContextDiff(
        active_task_a=active_task_a,
        active_task_b=active_task_b,
        active_task_changed=active_task_a != active_task_b,
        constraints_added=_sorted_added(context_a, context_b, "constraints"),
        constraints_removed=_sorted_removed(context_a, context_b, "constraints"),
        decisions_added=_sorted_added(context_a, context_b, "decisions"),
        decisions_removed=_sorted_removed(context_a, context_b, "decisions"),
        open_issues_added=_sorted_added(context_a, context_b, "open_issues"),
        open_issues_removed=_sorted_removed(context_a, context_b, "open_issues"),
    )


def _intersect_working_context(
    context_a: Mapping[str, object],
    context_b: Mapping[str, object],
    *,
    shared_ids: tuple[str, ...],
) -> WorkingContextIntersection:
    active_task_a = _optional_string(context_a.get("active_task"))
    active_task_b = _optional_string(context_b.get("active_task"))
    shared_id_set = set(shared_ids)
    return WorkingContextIntersection(
        active_task_shared=active_task_a if active_task_a == active_task_b else None,
        constraints_shared=_sorted_intersection(
            context_a,
            context_b,
            "constraints",
            shared_id_set=shared_id_set,
        ),
        decisions_shared=_sorted_intersection(
            context_a,
            context_b,
            "decisions",
            shared_id_set=shared_id_set,
        ),
        open_issues_shared=_sorted_intersection(
            context_a,
            context_b,
            "open_issues",
            shared_id_set=shared_id_set,
        ),
    )


def _summarize_artifacts(
    artifacts_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    ids_by_type: dict[str, list[str]] = {
        artifact_type: [] for artifact_type in _canonical_artifact_types()
    }

    for artifact_id, artifact in artifacts_by_id.items():
        artifact_type = artifact.get("type")
        if not isinstance(artifact_type, str):
            raise BrainValidationError(
                f"persisted artifact '{artifact_id}' must contain a string type"
            )
        cleaned_type = artifact_type.strip()
        if cleaned_type not in ids_by_type:
            supported = ", ".join(_canonical_artifact_types())
            raise BrainValidationError(
                f"unsupported persisted artifact type '{cleaned_type}' for '{artifact_id}'. "
                f"Supported: {supported}"
            )
        ids_by_type[cleaned_type].append(artifact_id)

    frozen_ids_by_type = {
        artifact_type: tuple(sorted(ids))
        for artifact_type, ids in ids_by_type.items()
    }
    count_by_type = {
        artifact_type: len(ids)
        for artifact_type, ids in frozen_ids_by_type.items()
    }

    return {
        "artifact_ids_by_type": frozen_ids_by_type,
        "artifact_count_by_type": count_by_type,
    }


def _canonical_artifact_types() -> tuple[str, ...]:
    return tuple(CANONICAL_ARTIFACT_DIRECTORY_BY_TYPE.keys())


def _load_artifacts_by_id(root: Path) -> Mapping[str, Mapping[str, object]]:
    brain = load_brain(root=root)
    return export_governance_brain_state(brain=brain)["artifacts_by_id"]


def _classify_artifact_ids(
    artifacts_a: Mapping[str, Mapping[str, object]],
    artifacts_b: Mapping[str, Mapping[str, object]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    ids_a = set(artifacts_a.keys())
    ids_b = set(artifacts_b.keys())
    shared_exact = {
        artifact_id
        for artifact_id in ids_a & ids_b
        if artifacts_a[artifact_id] == artifacts_b[artifact_id]
    }
    mismatched = {
        artifact_id
        for artifact_id in ids_a & ids_b
        if artifacts_a[artifact_id] != artifacts_b[artifact_id]
    }
    added = ids_b - ids_a
    removed = ids_a - ids_b
    return (
        tuple(sorted(added)),
        tuple(sorted(removed)),
        tuple(sorted(shared_exact)),
        tuple(sorted(mismatched)),
    )


def _build_artifact_ids_by_type(
    *,
    artifacts_a: Mapping[str, Mapping[str, object]],
    artifacts_b: Mapping[str, Mapping[str, object]],
    added_ids: tuple[str, ...],
    removed_ids: tuple[str, ...],
    shared_ids: tuple[str, ...],
    mismatched_ids: tuple[str, ...],
) -> dict[str, Mapping[str, tuple[str, ...]]]:
    artifact_ids_by_type: dict[str, dict[str, list[str]]] = {
        artifact_type: {
            "shared": [],
            "added": [],
            "removed": [],
            "mismatched": [],
        }
        for artifact_type in _canonical_artifact_types()
    }

    for artifact_id in shared_ids:
        artifact_type = _artifact_type_for_bucket(
            artifacts_a=artifacts_a,
            artifacts_b=artifacts_b,
            artifact_id=artifact_id,
        )
        artifact_ids_by_type[artifact_type]["shared"].append(artifact_id)

    for artifact_id in added_ids:
        artifact_type = _required_artifact_type(artifacts_b[artifact_id], artifact_id)
        artifact_ids_by_type[artifact_type]["added"].append(artifact_id)

    for artifact_id in removed_ids:
        artifact_type = _required_artifact_type(artifacts_a[artifact_id], artifact_id)
        artifact_ids_by_type[artifact_type]["removed"].append(artifact_id)

    for artifact_id in mismatched_ids:
        for artifact_type in _mismatch_bucket_types(
            artifacts_a=artifacts_a,
            artifacts_b=artifacts_b,
            artifact_id=artifact_id,
        ):
            artifact_ids_by_type[artifact_type]["mismatched"].append(artifact_id)

    return {
        artifact_type: MappingProxyType(
            {
                bucket: tuple(sorted(ids))
                for bucket, ids in buckets.items()
            }
        )
        for artifact_type, buckets in artifact_ids_by_type.items()
    }


def _all_artifact_ids(
    artifact_ids_by_type: Mapping[str, tuple[str, ...]],
) -> set[str]:
    artifact_ids: set[str] = set()
    for ids in artifact_ids_by_type.values():
        artifact_ids.update(ids)
    return artifact_ids


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BrainValidationError("working_context active_task must be a string or null")
    return value


def _artifact_type_for_bucket(
    *,
    artifacts_a: Mapping[str, Mapping[str, object]],
    artifacts_b: Mapping[str, Mapping[str, object]],
    artifact_id: str,
) -> str:
    type_a = _required_artifact_type(artifacts_a[artifact_id], artifact_id)
    type_b = _required_artifact_type(artifacts_b[artifact_id], artifact_id)
    if type_a != type_b:
        raise BrainValidationError(
            f"shared artifact '{artifact_id}' has inconsistent types across brains: "
            f"{type_a} != {type_b}"
        )
    return type_a


def _mismatch_bucket_types(
    *,
    artifacts_a: Mapping[str, Mapping[str, object]],
    artifacts_b: Mapping[str, Mapping[str, object]],
    artifact_id: str,
) -> tuple[str, ...]:
    type_a = _required_artifact_type(artifacts_a[artifact_id], artifact_id)
    type_b = _required_artifact_type(artifacts_b[artifact_id], artifact_id)
    return tuple(sorted({type_a, type_b}))


def _required_artifact_type(
    artifact: Mapping[str, object],
    artifact_id: str,
) -> str:
    artifact_type = artifact.get("type")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        raise BrainValidationError(
            f"persisted artifact '{artifact_id}' must contain a non-empty string type"
        )
    cleaned_type = artifact_type.strip()
    if cleaned_type not in _canonical_artifact_types():
        supported = ", ".join(_canonical_artifact_types())
        raise BrainValidationError(
            f"unsupported persisted artifact type '{cleaned_type}' for '{artifact_id}'. "
            f"Supported: {supported}"
        )
    return cleaned_type


def _sorted_added(
    context_a: Mapping[str, object],
    context_b: Mapping[str, object],
    field_name: str,
) -> tuple[str, ...]:
    return tuple(sorted(_string_set(context_b, field_name) - _string_set(context_a, field_name)))


def _sorted_removed(
    context_a: Mapping[str, object],
    context_b: Mapping[str, object],
    field_name: str,
) -> tuple[str, ...]:
    return tuple(sorted(_string_set(context_a, field_name) - _string_set(context_b, field_name)))


def _sorted_intersection(
    context_a: Mapping[str, object],
    context_b: Mapping[str, object],
    field_name: str,
    *,
    shared_id_set: set[str] | None = None,
) -> tuple[str, ...]:
    intersection = _string_set(context_a, field_name) & _string_set(context_b, field_name)
    if shared_id_set is not None:
        intersection &= shared_id_set
    return tuple(sorted(intersection))


def _string_set(context: Mapping[str, object], field_name: str) -> set[str]:
    value = context.get(field_name)
    if not isinstance(value, list):
        raise BrainValidationError(f"working_context field '{field_name}' must be a list")
    normalized: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise BrainValidationError(
                f"working_context field '{field_name}' must contain only strings"
            )
        normalized.add(item)
    return normalized
