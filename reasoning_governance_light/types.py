# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AcceptanceStatus = Literal["accepted", "rejected", "duplicate", "rediscovered"]


@dataclass(frozen=True)
class AcceptanceDecision:
    """
    Structured acceptance result for a candidate reasoning artifact.

    Fields:
    - status: machine-readable acceptance classification
    - reason_code: stable machine-readable reason
    - artifact_id: candidate artifact id when available
    - duplicate_of: existing artifact id for duplicate classification
    - rediscovered_of: existing artifact id for rediscovery classification
    - notes: optional human-readable context
    """

    status: AcceptanceStatus
    reason_code: str
    artifact_id: str | None = None
    duplicate_of: str | None = None
    rediscovered_of: str | None = None
    notes: str | None = None