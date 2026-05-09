# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import shutil
from pathlib import Path

from .policy import forbid_existing_path, require_existing_directory
from .types import SnapshotResult


def create_snapshot(
    *,
    source_root: Path,
    snapshot_root: Path,
) -> SnapshotResult:
    """
    Create an immutable snapshot of a reasoning brain.

    No silent overwrite is allowed.
    """
    require_existing_directory(source_root, "source brain")
    forbid_existing_path(snapshot_root, "snapshot root")

    shutil.copytree(source_root, snapshot_root)

    return SnapshotResult(
        source_root=source_root,
        snapshot_root=snapshot_root,
    )