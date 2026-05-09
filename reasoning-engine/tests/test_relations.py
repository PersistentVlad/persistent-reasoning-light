# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import shutil
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPO_ROOT = PROJECT_ROOT.parent
SCRATCH_ROOT = REPO_ROOT / "_tmp_test_relations"


from core.artifact_types import (  # noqa: E402
    CONSTRAINT_CARD,
    DECISION_CARD,
    RELATION_BLOCKS,
    RELATION_DEPENDS_ON,
    TASK_CARD,
)
from core.relations import load_relation_file, resolve_relation_path  # noqa: E402
from core.storage import save_canonical_artifact  # noqa: E402


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


class RelationsTests(unittest.TestCase):
    def test_load_relation_file_orders_edges_and_skips_blank_lines(self) -> None:
        brain_root = make_scratch_dir("ordered_relations")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact("task_beta", TASK_CARD, goal="B task goal", status="active", context=[]),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact("task_alpha", TASK_CARD, goal="A task goal", status="active", context=[]),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_beta",
                DECISION_CARD,
                statement="Decision beta",
                reason=["B reason"],
                status="accepted",
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_alpha",
                DECISION_CARD,
                statement="Decision alpha",
                reason=["A reason"],
                status="accepted",
            ),
        )
        relation_path = brain_root / "relations" / RELATION_DEPENDS_ON
        relation_path.write_text(
            '\n'.join(
                [
                    '{"from": "task_beta", "to": "decision_beta"}',
                    "",
                    '{"from": "task_alpha", "to": "decision_alpha"}',
                ]
            ),
            encoding="utf-8",
        )

        edges = load_relation_file(brain_root, RELATION_DEPENDS_ON)
        self.assertEqual(
            [(edge.from_id, edge.to_id) for edge in edges],
            [("task_alpha", "decision_alpha"), ("task_beta", "decision_beta")],
        )

    def test_supported_relation_files_only(self) -> None:
        brain_root = make_scratch_dir("unsupported_relation")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        with self.assertRaises(ValueError):
            resolve_relation_path(brain_root, "unsupported.jsonl")

    def test_self_edge_relation_is_rejected(self) -> None:
        brain_root = make_scratch_dir("self_edge")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact("task_self", TASK_CARD, goal="Self task goal", status="active", context=[]),
        )
        relation_path = brain_root / "relations" / RELATION_DEPENDS_ON
        relation_path.write_text(
            '{"from": "task_self", "to": "task_self"}',
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            load_relation_file(brain_root, RELATION_DEPENDS_ON)

    def test_dangling_relation_reference_is_rejected(self) -> None:
        brain_root = make_scratch_dir("dangling_relation")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact("task_exists", TASK_CARD, goal="Existing task", status="active", context=[]),
        )
        relation_path = brain_root / "relations" / RELATION_DEPENDS_ON
        relation_path.write_text(
            '{"from": "task_exists", "to": "decision_missing"}',
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            load_relation_file(brain_root, RELATION_DEPENDS_ON)

    def test_depends_on_semantics_are_enforced(self) -> None:
        brain_root = make_scratch_dir("depends_on_semantics")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_origin",
                DECISION_CARD,
                statement="Origin decision",
                reason=["Reason origin"],
                status="accepted",
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact("task_target", TASK_CARD, goal="Target task", status="active", context=[]),
        )
        relation_path = brain_root / "relations" / RELATION_DEPENDS_ON
        relation_path.write_text(
            '{"from": "decision_origin", "to": "task_target"}',
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            load_relation_file(brain_root, RELATION_DEPENDS_ON)

    def test_blocks_semantics_are_enforced(self) -> None:
        brain_root = make_scratch_dir("blocks_semantics")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "constraint_safety",
                CONSTRAINT_CARD,
                statement="Do not overwrite",
                reason=["Safety reason"],
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact("task_build", TASK_CARD, goal="Build task", status="active", context=[]),
        )
        relation_path = brain_root / "relations" / RELATION_BLOCKS
        relation_path.write_text(
            '{"from": "constraint_safety", "to": "task_build"}',
            encoding="utf-8",
        )

        edges = load_relation_file(brain_root, RELATION_BLOCKS)
        self.assertEqual([(edge.from_id, edge.to_id) for edge in edges], [("constraint_safety", "task_build")])


if __name__ == "__main__":
    unittest.main()
