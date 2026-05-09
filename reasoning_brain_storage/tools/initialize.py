# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import shutil
from pathlib import Path

from .policy import ensure_reasoning_brain_root, forbid_existing_path
from .types import BrainRef, BrainState


def initialize_brain(
    *,
    source: BrainRef,
    target_root: Path,
) -> BrainState:
    """
    Initialize a reasoning brain from empty/runtime/seeded/snapshot source.

    No silent overwrite is allowed.
    """
    ensure_reasoning_brain_root(source.path)
    forbid_existing_path(target_root, "target brain root")

    shutil.copytree(source.path, target_root)
    ensure_reasoning_brain_root(target_root)

    return BrainState(
        root=target_root,
        working_context_path=target_root / "views" / "working_context.json",
    )
