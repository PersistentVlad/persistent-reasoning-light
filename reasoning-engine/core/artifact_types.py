# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from pathlib import Path


TASK_CARD = "TaskCard"
DECISION_CARD = "DecisionCard"
CONSTRAINT_CARD = "ConstraintCard"
PROCEDURE_CARD = "ProcedureCard"
ISSUE_CARD = "IssueCard"

SUPPORTED_ARTIFACT_TYPES = (
    TASK_CARD,
    DECISION_CARD,
    CONSTRAINT_CARD,
    PROCEDURE_CARD,
    ISSUE_CARD,
)

TYPE_TO_PREFIX = {
    TASK_CARD: "task",
    DECISION_CARD: "decision",
    CONSTRAINT_CARD: "constraint",
    PROCEDURE_CARD: "procedure",
    ISSUE_CARD: "issue",
}

PREFIX_TO_TYPE = {prefix: artifact_type for artifact_type, prefix in TYPE_TO_PREFIX.items()}

REASONING_BRAIN_ROOT = Path(".")
BRAIN_DIRECTORY = Path("brain")
RELATIONS_DIRECTORY = Path("relations")
VIEWS_DIRECTORY = Path("views")
RUNTIME_DIRECTORY = Path("runtime")
WORKING_CONTEXT_FILE = VIEWS_DIRECTORY / "working_context.json"
RUNTIME_INBOX_DIRECTORY = RUNTIME_DIRECTORY / "inbox"
RUNTIME_DRAFTS_DIRECTORY = RUNTIME_DIRECTORY / "drafts"

TYPE_TO_CANONICAL_SUBPATH = {
    TASK_CARD: Path("brain") / "tasks",
    DECISION_CARD: Path("brain") / "decisions",
    CONSTRAINT_CARD: Path("brain") / "constraints",
    PROCEDURE_CARD: Path("brain") / "procedures",
    ISSUE_CARD: Path("brain") / "issues",
}

RELATION_DEPENDS_ON = "depends_on.jsonl"
RELATION_BLOCKS = "blocks.jsonl"

SUPPORTED_RELATION_FILES = (
    RELATION_DEPENDS_ON,
    RELATION_BLOCKS,
)


def ensure_supported_artifact_type(artifact_type: str) -> str:
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ValueError(f"invalid artifact type: {artifact_type}")
    return artifact_type


def ensure_supported_prefix(prefix: str) -> str:
    if prefix not in PREFIX_TO_TYPE:
        raise ValueError(f"invalid artifact prefix: {prefix}")
    return prefix


def get_prefix_for_artifact_type(artifact_type: str) -> str:
    artifact_type = ensure_supported_artifact_type(artifact_type)
    return TYPE_TO_PREFIX[artifact_type]


def get_artifact_type_for_prefix(prefix: str) -> str:
    prefix = ensure_supported_prefix(prefix)
    return PREFIX_TO_TYPE[prefix]


def get_directory_for_artifact_type(artifact_type: str) -> Path:
    artifact_type = ensure_supported_artifact_type(artifact_type)
    return TYPE_TO_CANONICAL_SUBPATH[artifact_type]


__all__ = [
    "BRAIN_DIRECTORY",
    "CONSTRAINT_CARD",
    "DECISION_CARD",
    "ISSUE_CARD",
    "PROCEDURE_CARD",
    "REASONING_BRAIN_ROOT",
    "RELATION_BLOCKS",
    "RELATION_DEPENDS_ON",
    "RELATIONS_DIRECTORY",
    "RUNTIME_DIRECTORY",
    "RUNTIME_DRAFTS_DIRECTORY",
    "RUNTIME_INBOX_DIRECTORY",
    "SUPPORTED_ARTIFACT_TYPES",
    "SUPPORTED_RELATION_FILES",
    "TASK_CARD",
    "TYPE_TO_CANONICAL_SUBPATH",
    "TYPE_TO_PREFIX",
    "VIEWS_DIRECTORY",
    "WORKING_CONTEXT_FILE",
    "PREFIX_TO_TYPE",
    "ensure_supported_artifact_type",
    "ensure_supported_prefix",
    "get_artifact_type_for_prefix",
    "get_directory_for_artifact_type",
    "get_prefix_for_artifact_type",
]
