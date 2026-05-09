# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
import shutil
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPO_ROOT = PROJECT_ROOT.parent
SCRATCH_ROOT = REPO_ROOT / "_tmp_test_view_builder"


from core.artifact_types import (  # noqa: E402
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    RELATION_BLOCKS,
    RELATION_DEPENDS_ON,
    TASK_CARD,
    WORKING_CONTEXT_FILE,
)
from core.storage import save_canonical_artifact  # noqa: E402
from core.view_builder import build_working_context, write_working_context  # noqa: E402


def make_artifact(artifact_id: str, artifact_type: str, **fields: object) -> dict[str, object]:
    artifact = {
        "id": artifact_id,
        "type": artifact_type,
        "domains": ["general"],
        "created_at": "2026-03-08T12:34:00Z",
        "updated_at": "2026-03-08T12:34:00Z",
    }
    artifact.update(fields)
    return artifact


def create_brain(root: Path) -> None:
    for relative_path in (
        "brain/tasks",
        "brain/decisions",
        "brain/constraints",
        "brain/procedures",
        "brain/issues",
        "runtime/inbox",
        "runtime/drafts",
        "relations",
        "views",
    ):
        (root / relative_path).mkdir(parents=True, exist_ok=True)


def make_scratch_dir(name: str) -> Path:
    path = SCRATCH_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class ViewBuilderTests(unittest.TestCase):
    def test_empty_brain_returns_minimal_context(self) -> None:
        brain_root = make_scratch_dir("empty_brain")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)

        context = build_working_context(brain_root)

        self.assertEqual(
            context,
            {
                "active_task": None,
                "constraints": [],
                "decisions": [],
                "open_issues": [],
            },
        )

    def test_working_context_uses_ids_only_and_deterministic_ordering(self) -> None:
        brain_root = make_scratch_dir("minimal_context")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "task_beta",
                TASK_CARD,
                goal="Second active task",
                status="active",
                context=["decision_beta"],
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "task_alpha",
                TASK_CARD,
                goal="First active task",
                status="active",
                context=["issue_alpha", "constraint_beta", "decision_beta"],
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_alpha",
                DECISION_CARD,
                statement="Decision A",
                reason=["Reason A"],
                status="accepted",
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_beta",
                DECISION_CARD,
                statement="Decision B",
                reason=["Reason B"],
                status="accepted",
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "constraint_alpha",
                CONSTRAINT_CARD,
                statement="Constraint A",
                reason=["Reason A"],
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "constraint_beta",
                CONSTRAINT_CARD,
                statement="Constraint B",
                reason=["Reason B"],
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "issue_alpha",
                ISSUE_CARD,
                question="Issue A question",
                priority="high",
            ),
        )

        (brain_root / "relations" / RELATION_DEPENDS_ON).write_text(
            '\n'.join(
                [
                    '{"from": "task_alpha", "to": "decision_alpha"}',
                    '{"from": "task_beta", "to": "decision_beta"}',
                ]
            ),
            encoding="utf-8",
        )
        (brain_root / "relations" / RELATION_BLOCKS).write_text(
            '{"from": "constraint_alpha", "to": "task_alpha"}',
            encoding="utf-8",
        )

        context = build_working_context(brain_root)

        self.assertEqual(context["active_task"], "task_alpha")
        self.assertEqual(context["decisions"], ["decision_alpha", "decision_beta"])
        self.assertEqual(context["constraints"], ["constraint_alpha", "constraint_beta"])
        self.assertEqual(context["open_issues"], ["issue_alpha"])
        self.assertTrue(all(isinstance(value, str) for value in context["decisions"]))
        self.assertEqual(set(context), {"active_task", "constraints", "decisions", "open_issues"})

    def test_write_working_context_creates_expected_file(self) -> None:
        brain_root = make_scratch_dir("write_context")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)

        output_path = write_working_context(brain_root)
        raw_value = json.loads((brain_root / WORKING_CONTEXT_FILE).read_text(encoding="utf-8"))

        self.assertEqual(output_path, brain_root / WORKING_CONTEXT_FILE)
        self.assertIsNone(raw_value["active_task"])
        self.assertEqual(raw_value["decisions"], [])


if __name__ == "__main__":
    unittest.main()
