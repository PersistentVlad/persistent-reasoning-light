# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import json
from pathlib import Path

from .policy import BRAIN_DIRECTORY_NAME, ensure_reasoning_brain_root


def rebuild_working_context(*, runtime_root: Path) -> Path:
    """
    Rebuild working_context.json from current runtime brain contents.

    v1:
    - deterministic, simple rebuild
    - can be upgraded later with richer selection logic
    """
    ensure_reasoning_brain_root(runtime_root)

    views_dir = runtime_root / "views"

    working_context_path = views_dir / "working_context.json"
    artifact_root = runtime_root / BRAIN_DIRECTORY_NAME

    payload = {
        "active_task": None,
        "tasks": [],
        "constraints": [],
        "decisions": [],
        "procedures": [],
        "open_issues": [],
    }

    for section_name, folder_name in (
        ("tasks", "tasks"),
        ("constraints", "constraints"),
        ("decisions", "decisions"),
        ("procedures", "procedures"),
        ("open_issues", "issues"),
    ):
        folder = artifact_root / folder_name
        payload[section_name] = sorted(
            item.stem
            for item in folder.glob("*.json")
            if item.is_file()
        )

    working_context_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return working_context_path
