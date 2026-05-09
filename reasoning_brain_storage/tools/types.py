# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, TypedDict


BrainRefType = Literal["empty", "runtime", "seeded", "snapshot"]
BrainOutMode = Literal["continue", "snapshot", "empty"]


@dataclass(frozen=True)
class BrainRef:
    type: BrainRefType
    path: Path


@dataclass(frozen=True)
class BrainState:
    root: Path
    working_context_path: Path


class GovernanceBrainState(TypedDict):
    """
    Read-only governance-facing snapshot exported from storage.

    This is the minimal v1 shape required by reasoning_governance_light.
    """

    artifacts_by_id: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class PersistArtifactResult:
    """
    Storage-layer persistence result.

    This result does NOT express acceptance/rejection semantics.
    Acceptance belongs to reasoning_governance_light.

    Fields:
    - persisted: whether storage write succeeded
    - storage_reason: machine-readable storage outcome
    - artifact_path: path of persisted artifact when successful
    - conflict_path: path that caused a storage-level conflict, if any
    """

    persisted: bool
    storage_reason: str
    artifact_path: Path | None = None
    conflict_path: Path | None = None


@dataclass(frozen=True)
class SnapshotResult:
    source_root: Path
    snapshot_root: Path


@dataclass(frozen=True)
class BrainDiffSummary:
    added_count: int
    removed_count: int
    duplicate_candidates_count: int
    contradiction_candidates_count: int


@dataclass(frozen=True)
class ArtifactCountDelta:
    a: int
    b: int
    delta: int


@dataclass(frozen=True)
class WorkingContextDiff:
    active_task_a: str | None
    active_task_b: str | None
    active_task_changed: bool
    constraints_added: tuple[str, ...]
    constraints_removed: tuple[str, ...]
    decisions_added: tuple[str, ...]
    decisions_removed: tuple[str, ...]
    open_issues_added: tuple[str, ...]
    open_issues_removed: tuple[str, ...]


@dataclass(frozen=True)
class WorkingContextIntersection:
    active_task_shared: str | None
    constraints_shared: tuple[str, ...]
    decisions_shared: tuple[str, ...]
    open_issues_shared: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotInspectionResult:
    brain_root: Path
    working_context: Mapping[str, object]
    artifact_count_total: int
    artifact_count_by_type: Mapping[str, int]
    artifact_ids_by_type: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class SnapshotComparisonResult:
    snapshot_a_root: Path
    snapshot_b_root: Path
    working_context_diff: WorkingContextDiff
    working_context_intersection: WorkingContextIntersection
    artifact_count_total: ArtifactCountDelta
    artifact_count_by_type: Mapping[str, ArtifactCountDelta]
    artifact_ids: Mapping[str, tuple[str, ...]]
    artifact_ids_by_type: Mapping[str, Mapping[str, tuple[str, ...]]]
    brain_diff_summary: BrainDiffSummary
