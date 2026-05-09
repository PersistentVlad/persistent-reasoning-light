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
    export_governance_brain_state,
    initialize_brain,
    load_brain,
    persist_artifact,
    rebuild_working_context,
)
from reasoning_governance_light import evaluate_artifact


class V1EndToEndLoopTests(unittest.TestCase):
    def test_decision_artifact_flows_through_governance_storage_and_rebuild(self) -> None:
        candidate = {
            "id": "decision-1",
            "type": "decision",
            "summary": "use cached parse result",
        }

        temp_root = _test_run_root()
        runtime_root = temp_root / "runtime"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            initialize_brain(
                source=BrainRef(type="empty", path=_canonical_empty_template_root()),
                target_root=runtime_root,
            )

            brain = load_brain(root=runtime_root)
            brain_state = export_governance_brain_state(brain=brain)

            decision = evaluate_artifact(candidate, brain_state)
            self.assertEqual(decision.status, "accepted")
            self.assertEqual(decision.reason_code, "accepted")

            persist_result = persist_artifact(runtime_root=runtime_root, artifact=candidate)
            self.assertTrue(persist_result.persisted)

            rebuilt_path = rebuild_working_context(runtime_root=runtime_root)

            persisted_path = runtime_root / "brain" / "decisions" / "decision-1.json"
            self.assertTrue(persisted_path.exists())
            self.assertEqual(persist_result.artifact_path, persisted_path)
            self.assertEqual(rebuilt_path, runtime_root / "views" / "working_context.json")

            working_context = json.loads(rebuilt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                working_context,
                {
                    "active_task": None,
                    "constraints": [],
                    "decisions": ["decision-1"],
                    "open_issues": [],
                },
            )

            updated_brain = load_brain(root=runtime_root)
            updated_brain_state = export_governance_brain_state(brain=updated_brain)
            duplicate_decision = evaluate_artifact(candidate, updated_brain_state)

            self.assertEqual(duplicate_decision.status, "duplicate")
            self.assertEqual(duplicate_decision.reason_code, "duplicate_id")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


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

