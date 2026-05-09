# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.artifact_cards import (  # noqa: E402
    DecisionCard,
    ProcedureCard,
    TaskCard,
    artifact_from_dict,
    artifact_to_dict,
    artifact_to_json,
    normalize_artifact_dict,
)
from core.artifact_types import DECISION_CARD, PROCEDURE_CARD, TASK_CARD  # noqa: E402


TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ArtifactCardsTests(unittest.TestCase):
    def test_artifact_from_dict_applies_defaults(self) -> None:
        artifact = artifact_from_dict(
            {
                "id": "task_test_defaults",
                "type": TASK_CARD,
                "goal": "Implement a deterministic loader",
                "status": "active",
                "context": [],
            }
        )

        self.assertIsInstance(artifact, TaskCard)
        self.assertEqual(artifact.domains, ["general"])
        self.assertRegex(artifact.created_at, TIMESTAMP_PATTERN)
        self.assertEqual(artifact.updated_at, artifact.created_at)

    def test_normalize_artifact_dict_preserves_explicit_values(self) -> None:
        normalized = normalize_artifact_dict(
            {
                "id": "decision_explicit_values",
                "type": DECISION_CARD,
                "domains": ["architecture"],
                "created_at": "2026-03-08T12:34:00Z",
                "updated_at": "2026-03-09T12:34:00Z",
                "statement": "Use Git as canonical storage",
                "reason": ["It is inspectable"],
                "status": "accepted",
            }
        )

        self.assertEqual(normalized["domains"], ["architecture"])
        self.assertEqual(normalized["created_at"], "2026-03-08T12:34:00Z")
        self.assertEqual(normalized["updated_at"], "2026-03-09T12:34:00Z")

    def test_deterministic_json_serialization(self) -> None:
        artifact = DecisionCard(
            id="decision_json",
            type=DECISION_CARD,
            domains=["general"],
            created_at="2026-03-08T12:34:00Z",
            updated_at="2026-03-08T12:34:00Z",
            statement="Use JSON for artifact files",
            reason=["Stable diffs"],
            status="accepted",
        )

        expected = (
            '{\n'
            '  "created_at": "2026-03-08T12:34:00Z",\n'
            '  "domains": [\n'
            '    "general"\n'
            '  ],\n'
            '  "id": "decision_json",\n'
            '  "reason": [\n'
            '    "Stable diffs"\n'
            '  ],\n'
            '  "statement": "Use JSON for artifact files",\n'
            '  "status": "accepted",\n'
            '  "type": "DecisionCard",\n'
            '  "updated_at": "2026-03-08T12:34:00Z"\n'
            '}'
        )

        self.assertEqual(artifact_to_json(artifact), expected)
        self.assertEqual(artifact_to_json(artifact), artifact_to_json(artifact))

    def test_required_artifact_structure_is_preserved(self) -> None:
        artifact = artifact_from_dict(
            {
                "id": "procedure_add_artifact",
                "type": PROCEDURE_CARD,
                "name": "Add artifact",
                "steps": ["Validate schema", "Write JSON file"],
            }
        )

        self.assertIsInstance(artifact, ProcedureCard)
        artifact_dict = artifact_to_dict(artifact)
        self.assertEqual(
            set(artifact_dict),
            {"id", "type", "domains", "created_at", "updated_at", "name", "steps"},
        )
        self.assertEqual(artifact.steps, ["Validate schema", "Write JSON file"])


if __name__ == "__main__":
    unittest.main()
