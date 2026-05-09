# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from reasoning_brain_storage.tools import (
    BrainRef,
    compare_brain_snapshots,
    create_snapshot,
    diff_brains,
    initialize_brain,
    inspect_brain_snapshot,
    persist_artifact,
    rebuild_working_context,
)


class SnapshotAuditTests(unittest.TestCase):
    def test_inspect_brain_snapshot_returns_stable_machine_readable_structure(self) -> None:
        temp_root = _test_run_root()
        runtime_root = temp_root / "runtime"
        snapshot_root = temp_root / "snapshot_a"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            _initialize_runtime(runtime_root)
            _persist_and_rebuild(
                runtime_root,
                {"id": "decision_keep", "type": "decision", "summary": "keep"},
                {"id": "constraint_only_a", "type": "constraint", "summary": "only a"},
            )
            create_snapshot(source_root=runtime_root, snapshot_root=snapshot_root)

            inspection = inspect_brain_snapshot(root=snapshot_root)

            self.assertEqual(inspection.brain_root, snapshot_root)
            self.assertEqual(
                dict(inspection.working_context),
                {
                    "active_task": None,
                    "constraints": ["constraint_only_a"],
                    "decisions": ["decision_keep"],
                    "open_issues": [],
                },
            )
            self.assertEqual(inspection.artifact_count_total, 2)
            self.assertEqual(
                dict(inspection.artifact_count_by_type),
                {
                    "task": 0,
                    "decision": 1,
                    "constraint": 1,
                    "procedure": 0,
                    "issue": 0,
                },
            )
            self.assertEqual(
                dict(inspection.artifact_ids_by_type),
                {
                    "task": (),
                    "decision": ("decision_keep",),
                    "constraint": ("constraint_only_a",),
                    "procedure": (),
                    "issue": (),
                },
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_compare_brain_snapshots_reports_context_counts_and_artifact_ids(self) -> None:
        temp_root = _test_run_root()
        runtime_a = temp_root / "runtime_a"
        runtime_b = temp_root / "runtime_b"
        snapshot_a = temp_root / "snapshot_a"
        snapshot_b = temp_root / "snapshot_b"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            _initialize_runtime(runtime_a)
            _initialize_runtime(runtime_b)

            _persist_and_rebuild(
                runtime_a,
                {"id": "decision_keep", "type": "decision", "summary": "keep"},
                {"id": "constraint_only_a", "type": "constraint", "summary": "only a"},
            )
            _persist_and_rebuild(
                runtime_b,
                {"id": "decision_keep", "type": "decision", "summary": "keep"},
                {"id": "decision_new", "type": "decision", "summary": "new"},
                {"id": "issue_new", "type": "issue", "summary": "issue"},
            )

            # These transient files differ, but snapshot comparison should ignore them.
            (runtime_a / "runtime" / "drafts" / "note_a.txt").write_text("a\n", encoding="utf-8")
            (runtime_b / "runtime" / "drafts" / "note_b.txt").write_text("b\n", encoding="utf-8")

            create_snapshot(source_root=runtime_a, snapshot_root=snapshot_a)
            create_snapshot(source_root=runtime_b, snapshot_root=snapshot_b)

            before_a = _snapshot_file_texts(snapshot_a)
            before_b = _snapshot_file_texts(snapshot_b)

            comparison = compare_brain_snapshots(
                snapshot_a_root=snapshot_a,
                snapshot_b_root=snapshot_b,
            )

            self.assertEqual(comparison.snapshot_a_root, snapshot_a)
            self.assertEqual(comparison.snapshot_b_root, snapshot_b)
            self.assertFalse(comparison.working_context_diff.active_task_changed)
            self.assertEqual(comparison.working_context_diff.constraints_added, ())
            self.assertEqual(
                comparison.working_context_diff.constraints_removed,
                ("constraint_only_a",),
            )
            self.assertEqual(
                comparison.working_context_diff.decisions_added,
                ("decision_new",),
            )
            self.assertEqual(comparison.working_context_diff.decisions_removed, ())
            self.assertEqual(
                comparison.working_context_diff.open_issues_added,
                ("issue_new",),
            )
            self.assertEqual(comparison.working_context_diff.open_issues_removed, ())

            self.assertEqual(comparison.artifact_count_total.a, 2)
            self.assertEqual(comparison.artifact_count_total.b, 3)
            self.assertEqual(comparison.artifact_count_total.delta, 1)

            self.assertEqual(comparison.artifact_count_by_type["decision"].a, 1)
            self.assertEqual(comparison.artifact_count_by_type["decision"].b, 2)
            self.assertEqual(comparison.artifact_count_by_type["decision"].delta, 1)
            self.assertEqual(comparison.artifact_count_by_type["constraint"].a, 1)
            self.assertEqual(comparison.artifact_count_by_type["constraint"].b, 0)
            self.assertEqual(comparison.artifact_count_by_type["constraint"].delta, -1)
            self.assertEqual(comparison.artifact_count_by_type["issue"].a, 0)
            self.assertEqual(comparison.artifact_count_by_type["issue"].b, 1)
            self.assertEqual(comparison.artifact_count_by_type["issue"].delta, 1)

            self.assertEqual(
                comparison.artifact_ids["added"],
                ("decision_new", "issue_new"),
            )
            self.assertEqual(
                comparison.artifact_ids["removed"],
                ("constraint_only_a",),
            )
            self.assertEqual(
                comparison.artifact_ids["shared"],
                ("decision_keep",),
            )
            self.assertEqual(
                comparison.artifact_ids["mismatched"],
                (),
            )
            self.assertEqual(
                comparison.artifact_ids_by_type["decision"]["shared"],
                ("decision_keep",),
            )
            self.assertEqual(
                comparison.artifact_ids_by_type["decision"]["added"],
                ("decision_new",),
            )
            self.assertEqual(
                comparison.artifact_ids_by_type["constraint"]["removed"],
                ("constraint_only_a",),
            )
            self.assertEqual(
                comparison.working_context_intersection.decisions_shared,
                ("decision_keep",),
            )
            self.assertEqual(
                comparison.working_context_intersection.constraints_shared,
                (),
            )
            self.assertEqual(
                comparison.working_context_intersection.open_issues_shared,
                (),
            )
            self.assertEqual(comparison.brain_diff_summary.added_count, 2)
            self.assertEqual(comparison.brain_diff_summary.removed_count, 1)
            self.assertEqual(comparison.brain_diff_summary.duplicate_candidates_count, 0)
            self.assertEqual(
                comparison.brain_diff_summary.contradiction_candidates_count,
                0,
            )

            self.assertEqual(before_a, _snapshot_file_texts(snapshot_a))
            self.assertEqual(before_b, _snapshot_file_texts(snapshot_b))

            diff_summary = diff_brains(brain_a_root=snapshot_a, brain_b_root=snapshot_b)
            self.assertEqual(diff_summary.added_count, 2)
            self.assertEqual(diff_summary.removed_count, 1)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_compare_brain_snapshots_detects_same_id_payload_mismatch(self) -> None:
        temp_root = _test_run_root()
        runtime_a = temp_root / "runtime_a"
        runtime_b = temp_root / "runtime_b"
        snapshot_a = temp_root / "snapshot_a"
        snapshot_b = temp_root / "snapshot_b"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            _initialize_runtime(runtime_a)
            _initialize_runtime(runtime_b)

            _persist_and_rebuild(
                runtime_a,
                {"id": "decision_same_id", "type": "decision", "summary": "alpha"},
            )
            _persist_and_rebuild(
                runtime_b,
                {"id": "decision_same_id", "type": "decision", "summary": "beta"},
            )

            create_snapshot(source_root=runtime_a, snapshot_root=snapshot_a)
            create_snapshot(source_root=runtime_b, snapshot_root=snapshot_b)

            comparison = compare_brain_snapshots(
                snapshot_a_root=snapshot_a,
                snapshot_b_root=snapshot_b,
            )

            self.assertEqual(comparison.artifact_ids["shared"], ())
            self.assertEqual(comparison.artifact_ids["mismatched"], ("decision_same_id",))
            self.assertEqual(
                comparison.artifact_ids_by_type["decision"]["mismatched"],
                ("decision_same_id",),
            )
            self.assertEqual(
                comparison.working_context_intersection.decisions_shared,
                (),
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


def _initialize_runtime(runtime_root: Path) -> None:
    initialize_brain(
        source=BrainRef(type="empty", path=_canonical_empty_template_root()),
        target_root=runtime_root,
    )


def _persist_and_rebuild(runtime_root: Path, *artifacts: dict[str, object]) -> None:
    for artifact in artifacts:
        persist_artifact(runtime_root=runtime_root, artifact=artifact)
    rebuild_working_context(runtime_root=runtime_root)


def _snapshot_file_texts(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return snapshot


def _canonical_empty_template_root() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "reasoning_brain_storage" / "templates" / "empty"


def _test_temp_root() -> str:
    temp_root = Path(__file__).resolve().parent / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return str(temp_root)


def _test_run_root() -> Path:
    return Path(_test_temp_root()) / f"run_{uuid4().hex}"


if __name__ == "__main__":
    unittest.main()
