# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPO_ROOT = PROJECT_ROOT.parent
SCRATCH_ROOT = REPO_ROOT / "_tmp_test_git"


from core.git_adapter import commit_changes, get_repo_state, stage_artifact  # noqa: E402


def make_scratch_dir(name: str) -> Path:
    path = SCRATCH_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


@unittest.skipUnless(shutil.which("git"), "git executable is required")
class GitAdapterTests(unittest.TestCase):
    def test_get_repo_state_outside_repo(self) -> None:
        repo_root = make_scratch_dir("outside_repo")
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        previous_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
            state = get_repo_state()
        finally:
            os.chdir(previous_cwd)

        self.assertFalse(state.is_git_repo)
        self.assertIsNone(state.repo_root)
        self.assertFalse(state.has_uncommitted_changes)

    def test_get_repo_state_inside_repo(self) -> None:
        repo_root = make_scratch_dir("inside_repo")
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
            state = get_repo_state()
        finally:
            os.chdir(previous_cwd)

        self.assertTrue(state.is_git_repo)
        self.assertEqual(Path(state.repo_root), repo_root.resolve())
        self.assertFalse(state.has_uncommitted_changes)

    def test_stage_artifact_rejects_missing_path(self) -> None:
        with self.assertRaises(FileNotFoundError):
            stage_artifact("missing-artifact.json")

    def test_stage_artifact_marks_file_as_uncommitted(self) -> None:
        repo_root = make_scratch_dir("stage_artifact")
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        artifact_path = repo_root / "artifact.json"
        artifact_path.write_text("{}", encoding="utf-8")

        stage_artifact(artifact_path)

        previous_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
            state = get_repo_state()
        finally:
            os.chdir(previous_cwd)

        self.assertTrue(state.has_uncommitted_changes)

    def test_commit_changes_requires_non_empty_message(self) -> None:
        with self.assertRaises(ValueError):
            commit_changes(".", "   ")

    def test_commit_changes_requires_git_repository(self) -> None:
        repo_root = make_scratch_dir("commit_non_repo")
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        with self.assertRaises(ValueError):
            commit_changes(repo_root, "test commit")


if __name__ == "__main__":
    unittest.main()
