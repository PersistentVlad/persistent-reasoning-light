# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Mapping

from core.artifact_types import (
    CONSTRAINT_CARD,
    DECISION_CARD,
    ISSUE_CARD,
    PROCEDURE_CARD,
    TASK_CARD,
    ensure_supported_artifact_type,
)


DEFAULT_DOMAINS = ["general"]


@dataclass(kw_only=True)
class BaseArtifact:
    id: str
    type: str
    domains: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass(kw_only=True)
class TaskCard(BaseArtifact):
    goal: str
    status: str
    context: list[str]


@dataclass(kw_only=True)
class DecisionCard(BaseArtifact):
    statement: str
    reason: list[str]
    status: str


@dataclass(kw_only=True)
class ConstraintCard(BaseArtifact):
    statement: str
    reason: list[str]


@dataclass(kw_only=True)
class ProcedureCard(BaseArtifact):
    name: str
    steps: list[str]


@dataclass(kw_only=True)
class IssueCard(BaseArtifact):
    question: str
    priority: str


ARTIFACT_CLASS_BY_TYPE = {
    TASK_CARD: TaskCard,
    DECISION_CARD: DecisionCard,
    CONSTRAINT_CARD: ConstraintCard,
    PROCEDURE_CARD: ProcedureCard,
    ISSUE_CARD: IssueCard,
}

ArtifactCard = TaskCard | DecisionCard | ConstraintCard | ProcedureCard | IssueCard


def utc_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_artifact_dict(data: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(data, Mapping):
        raise ValueError("artifact data must be a mapping")

    normalized = dict(data)

    artifact_type = normalized.get("type")
    if not isinstance(artifact_type, str):
        raise ValueError("artifact type must be a string")
    ensure_supported_artifact_type(artifact_type)

    if "domains" not in normalized or normalized["domains"] is None:
        normalized["domains"] = list(DEFAULT_DOMAINS)
    elif isinstance(normalized["domains"], list):
        normalized["domains"] = list(normalized["domains"])

    if "created_at" not in normalized or normalized["created_at"] is None:
        normalized["created_at"] = utc_timestamp()

    if "updated_at" not in normalized or normalized["updated_at"] is None:
        normalized["updated_at"] = normalized["created_at"]

    return normalized


def artifact_from_dict(data: Mapping[str, object]) -> ArtifactCard:
    normalized = normalize_artifact_dict(data)
    artifact_type = ensure_supported_artifact_type(normalized["type"])
    artifact_class = ARTIFACT_CLASS_BY_TYPE[artifact_type]
    return artifact_class(**normalized)


def artifact_to_dict(artifact: ArtifactCard) -> dict[str, object]:
    return asdict(artifact)


def artifact_to_json(artifact: ArtifactCard) -> str:
    data = artifact_to_dict(artifact)
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)


__all__ = [
    "ArtifactCard",
    "ARTIFACT_CLASS_BY_TYPE",
    "BaseArtifact",
    "CONSTRAINT_CARD",
    "ConstraintCard",
    "DECISION_CARD",
    "DEFAULT_DOMAINS",
    "DecisionCard",
    "ISSUE_CARD",
    "IssueCard",
    "PROCEDURE_CARD",
    "ProcedureCard",
    "TASK_CARD",
    "TaskCard",
    "artifact_from_dict",
    "artifact_to_dict",
    "artifact_to_json",
    "normalize_artifact_dict",
    "utc_timestamp",
]
