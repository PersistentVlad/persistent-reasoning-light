# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import shutil
from pathlib import Path

from .initialize import initialize_brain
from .policy import ensure_reasoning_brain_root
from .types import BrainRef, BrainState


def prepare_runtime_from_source(
    *,
    source: BrainRef,
    runtime_root: Path,
) -> BrainState:
    """
    Recreate runtime brain from an explicit validated source brain.

    Existing runtime root is removed explicitly before initialization.
    """
    ensure_reasoning_brain_root(source.path)

    if runtime_root.exists():
        ensure_reasoning_brain_root(runtime_root)
        shutil.rmtree(runtime_root)

    return initialize_brain(
        source=source,
        target_root=runtime_root,
    )


def reset_to_empty(
    *,
    empty_template_root: Path,
    runtime_root: Path,
) -> BrainState:
    """
    Reset runtime brain to empty template.

    Existing runtime root is removed explicitly.
    """
    return prepare_runtime_from_source(
        source=BrainRef(type="empty", path=empty_template_root),
        runtime_root=runtime_root,
    )
