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
SCRATCH_ROOT = REPO_ROOT / "_tmp_test_storage"


from core.artifact_types import DECISION_CARD, TASK_CARD  # noqa: E402
from core.storage import (  # noqa: E402
    list_canonical_artifacts,
    list_runtime_artifacts,
    load_canonical_artifact,
    load_runtime_artifact,
    save_canonical_artifact,
    save_runtime_artifact,
)


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


class StorageTests(unittest.TestCase):
    def test_save_and_load_canonical_artifact(self) -> None:
        brain_root = make_scratch_dir("save_load_canonical")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        artifact = make_artifact(
            "decision_use_git",
            DECISION_CARD,
            statement="Use Git as canonical storage",
            reason=["History is inspectable"],
            status="accepted",
        )

        saved_path = save_canonical_artifact(brain_root, artifact)
        loaded = load_canonical_artifact(brain_root, DECISION_CARD, "decision_use_git")

        self.assertEqual(saved_path.name, "decision_use_git.json")
        self.assertEqual(loaded.id, "decision_use_git")
        self.assertEqual(loaded.statement, "Use Git as canonical storage")

    def test_save_and_load_runtime_artifacts_for_inbox_and_drafts(self) -> None:
        brain_root = make_scratch_dir("save_load_runtime")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        inbox_artifact = make_artifact(
            "task_runtime_inbox",
            TASK_CARD,
            goal="Track the current task",
            status="active",
            context=[],
        )
        drafts_artifact = make_artifact(
            "task_runtime_draft",
            TASK_CARD,
            goal="Track the draft task",
            status="active",
            context=[],
        )

        inbox_path = save_runtime_artifact(brain_root, "inbox", inbox_artifact)
        drafts_path = save_runtime_artifact(brain_root, "drafts", drafts_artifact)
        loaded_inbox = load_runtime_artifact(brain_root, "inbox", "task_runtime_inbox")
        loaded_drafts = load_runtime_artifact(brain_root, "drafts", "task_runtime_draft")

        self.assertEqual(inbox_path.parent.name, "inbox")
        self.assertEqual(drafts_path.parent.name, "drafts")
        self.assertEqual(loaded_inbox["id"], "task_runtime_inbox")
        self.assertEqual(loaded_drafts["id"], "task_runtime_draft")

    def test_duplicate_canonical_artifact_is_rejected(self) -> None:
        brain_root = make_scratch_dir("duplicate_canonical")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        artifact = make_artifact(
            "decision_duplicate",
            DECISION_CARD,
            statement="Use deterministic ordering",
            reason=["Stable output"],
            status="accepted",
        )

        save_canonical_artifact(brain_root, artifact)
        with self.assertRaises(FileExistsError):
            save_canonical_artifact(brain_root, artifact)

    def test_canonical_artifact_listing_is_deterministic(self) -> None:
        brain_root = make_scratch_dir("deterministic_listing")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_beta",
                DECISION_CARD,
                statement="B decision",
                reason=["B"],
                status="accepted",
            ),
        )
        save_canonical_artifact(
            brain_root,
            make_artifact(
                "decision_alpha",
                DECISION_CARD,
                statement="A decision",
                reason=["A"],
                status="accepted",
            ),
        )

        artifacts = list_canonical_artifacts(brain_root, DECISION_CARD)
        self.assertEqual([artifact.id for artifact in artifacts], ["decision_alpha", "decision_beta"])

    def test_filename_must_match_artifact_id(self) -> None:
        brain_root = make_scratch_dir("filename_mismatch")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        artifact_path = brain_root / "brain" / "decisions" / "wrong_name.json"
        artifact_path.write_text(
            json.dumps(
                make_artifact(
                    "decision_real_id",
                    DECISION_CARD,
                    statement="Mismatch filename",
                    reason=["Testing"],
                    status="accepted",
                ),
                sort_keys=True,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            list_canonical_artifacts(brain_root, DECISION_CARD)

    def test_invalid_brain_root_raises_explicit_error(self) -> None:
        missing_root = SCRATCH_ROOT / "missing_brain_root"
        artifact = make_artifact(
            "task_missing_root",
            TASK_CARD,
            goal="Fail explicitly",
            status="active",
            context=[],
        )

        with self.assertRaises(FileNotFoundError):
            save_canonical_artifact(missing_root, artifact)

    def test_runtime_listing_is_deterministic(self) -> None:
        brain_root = make_scratch_dir("runtime_listing")
        self.addCleanup(lambda: shutil.rmtree(brain_root, ignore_errors=True))
        create_brain(brain_root)
        save_runtime_artifact(
            brain_root,
            "inbox",
            make_artifact(
                "task_zeta",
                TASK_CARD,
                goal="Z task",
                status="active",
                context=[],
            ),
        )
        save_runtime_artifact(
            brain_root,
            "inbox",
            make_artifact(
                "task_alpha",
                TASK_CARD,
                goal="A task",
                status="active",
                context=[],
            ),
        )

        artifacts = list_runtime_artifacts(brain_root, "inbox")
        self.assertEqual([artifact["id"] for artifact in artifacts], ["task_alpha", "task_zeta"])


if __name__ == "__main__":
    unittest.main()
