# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from reasoning_brain_storage import run_brain_compare
from reasoning_brain_storage.tools import (
    BrainRef,
    create_snapshot,
    initialize_brain,
    persist_artifact,
    rebuild_working_context,
)


class BrainCompareEntrypointTests(unittest.TestCase):
    def test_inspect_mode_writes_machine_readable_and_markdown_outputs(self) -> None:
        temp_root = _test_run_root()
        runtime_root = temp_root / "runtime"
        snapshot_root = temp_root / "snapshot_a"
        output_root = temp_root / "compare_reports"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            _initialize_runtime(runtime_root)
            _persist_and_rebuild(
                runtime_root,
                {"id": "decision_keep", "type": "decision", "summary": "keep"},
            )
            create_snapshot(source_root=runtime_root, snapshot_root=snapshot_root)
            before_snapshot = _file_texts(snapshot_root)

            run_brain_compare.main(
                [
                    "inspect",
                    "--brain",
                    str(snapshot_root),
                    "--label",
                    "inspect_probe",
                    "--output-root",
                    str(output_root),
                ]
            )

            report_dirs = [path for path in output_root.iterdir() if path.is_dir()]
            self.assertEqual(len(report_dirs), 1)
            report_root = report_dirs[0]
            inspection_json = report_root / "inspection_summary.json"
            inspection_md = report_root / "inspection.md"
            self.assertTrue(inspection_json.is_file())
            self.assertTrue(inspection_md.is_file())

            payload = _load_json(inspection_json)
            self.assertEqual(payload["brain_root"], str(snapshot_root))
            self.assertEqual(payload["artifact_count_total"], 1)
            self.assertEqual(payload["artifact_count_by_type"]["decision"], 1)
            self.assertIn("Brain Inspection", inspection_md.read_text(encoding="utf-8"))
            self.assertEqual(before_snapshot, _file_texts(snapshot_root))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_compare_mode_writes_expected_outputs_and_remains_read_only(self) -> None:
        temp_root = _test_run_root()
        runtime_a = temp_root / "runtime_a"
        runtime_b = temp_root / "runtime_b"
        snapshot_a = temp_root / "snapshot_a"
        snapshot_b = temp_root / "snapshot_b"
        output_root = temp_root / "compare_reports"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            _initialize_runtime(runtime_a)
            _initialize_runtime(runtime_b)
            _persist_and_rebuild(
                runtime_a,
                {"id": "decision_shared", "type": "decision", "summary": "same"},
                {"id": "decision_mismatch", "type": "decision", "summary": "alpha"},
                {"id": "constraint_removed", "type": "constraint", "summary": "remove"},
            )
            _persist_and_rebuild(
                runtime_b,
                {"id": "decision_shared", "type": "decision", "summary": "same"},
                {"id": "decision_mismatch", "type": "decision", "summary": "beta"},
                {"id": "issue_added", "type": "issue", "summary": "add"},
            )
            create_snapshot(source_root=runtime_a, snapshot_root=snapshot_a)
            create_snapshot(source_root=runtime_b, snapshot_root=snapshot_b)
            before_a = _file_texts(snapshot_a)
            before_b = _file_texts(snapshot_b)

            run_brain_compare.main(
                [
                    "compare",
                    "--brain-a",
                    str(snapshot_a),
                    "--brain-b",
                    str(snapshot_b),
                    "--label",
                    "cmp_probe",
                    "--output-root",
                    str(output_root),
                ]
            )

            report_dirs = [path for path in output_root.iterdir() if path.is_dir()]
            self.assertEqual(len(report_dirs), 1)
            report_root = report_dirs[0]

            expected_files = {
                "comparison_summary.json",
                "diff.json",
                "intersect.json",
                "diff.md",
                "intersect.md",
            }
            self.assertEqual({path.name for path in report_root.iterdir()}, expected_files)

            summary = _load_json(report_root / "comparison_summary.json")
            diff_payload = _load_json(report_root / "diff.json")
            intersect_payload = _load_json(report_root / "intersect.json")
            diff_md = (report_root / "diff.md").read_text(encoding="utf-8")
            intersect_md = (report_root / "intersect.md").read_text(encoding="utf-8")

            self.assertEqual(summary["brain_a_root"], str(snapshot_a))
            self.assertEqual(summary["brain_b_root"], str(snapshot_b))
            self.assertEqual(summary["artifact_count_total"]["shared"], 1)
            self.assertEqual(summary["artifact_count_total"]["added"], 1)
            self.assertEqual(summary["artifact_count_total"]["removed"], 1)
            self.assertEqual(summary["artifact_count_total"]["mismatched"], 1)
            self.assertIn("structural placeholders", summary["notes"][0])

            self.assertEqual(diff_payload["artifact_ids"]["added"], ["issue_added"])
            self.assertEqual(diff_payload["artifact_ids"]["removed"], ["constraint_removed"])
            self.assertEqual(diff_payload["artifact_ids"]["mismatched"], ["decision_mismatch"])
            self.assertEqual(
                diff_payload["artifacts_by_type"]["decision"]["mismatched"],
                ["decision_mismatch"],
            )
            self.assertEqual(
                diff_payload["working_context_diff"]["decisions_removed"],
                [],
            )
            self.assertEqual(
                diff_payload["working_context_diff"]["open_issues_added"],
                ["issue_added"],
            )

            self.assertEqual(intersect_payload["artifact_ids"]["shared"], ["decision_shared"])
            self.assertEqual(
                intersect_payload["artifacts_by_type"]["decision"]["shared"],
                ["decision_shared"],
            )
            self.assertEqual(
                intersect_payload["working_context_intersection"]["decisions_shared"],
                ["decision_shared"],
            )
            self.assertIn("Brain Diff", diff_md)
            self.assertIn("Brain Intersection", intersect_md)
            self.assertNotIn("union", diff_md.lower())
            self.assertNotIn("merge", intersect_md.lower())
            self.assertEqual(before_a, _file_texts(snapshot_a))
            self.assertEqual(before_b, _file_texts(snapshot_b))
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


def _canonical_empty_template_root() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "reasoning_brain_storage" / "templates" / "empty"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_texts(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
    return snapshot


def _test_temp_root() -> str:
    temp_root = Path(__file__).resolve().parent / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    return str(temp_root)


def _test_run_root() -> Path:
    return Path(_test_temp_root()) / f"run_{uuid4().hex}"


if __name__ == "__main__":
    unittest.main()
