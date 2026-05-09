# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoState:
    is_git_repo: bool
    repo_root: str | None
    branch: str | None
    has_uncommitted_changes: bool


def stage_artifact(path: Path | str) -> None:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise FileNotFoundError(f"artifact path does not exist: {artifact_path}")
    if not artifact_path.is_file():
        raise ValueError(f"artifact path is not a file: {artifact_path}")

    repo_root = _get_repo_root_for_path(artifact_path.parent)
    try:
        relative_path = artifact_path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact path is outside the Git repository: {artifact_path}") from exc

    _run_git_command(repo_root, ["add", "--", str(relative_path)])


def commit_changes(repo_path: Path | str, message: str) -> None:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("commit message must not be empty")

    repo_root = _get_repo_root_for_path(Path(repo_path))
    _run_git_command(repo_root, ["commit", "-m", message.strip()])


def get_repo_state() -> RepoState:
    repo_root = _try_get_repo_root(Path.cwd())
    if repo_root is None:
        return RepoState(
            is_git_repo=False,
            repo_root=None,
            branch=None,
            has_uncommitted_changes=False,
        )

    branch = _run_git_command(
        repo_root,
        ["branch", "--show-current"],
    ).stdout.strip()
    status_output = _run_git_command(
        repo_root,
        ["status", "--porcelain"],
    ).stdout
    return RepoState(
        is_git_repo=True,
        repo_root=str(repo_root),
        branch=branch or None,
        has_uncommitted_changes=bool(status_output.strip()),
    )


def _get_repo_root_for_path(path: Path) -> Path:
    repo_root = _try_get_repo_root(path)
    if repo_root is None:
        raise ValueError(f"not a Git repository: {path}")
    return repo_root


def _try_get_repo_root(path: Path) -> Path | None:
    result = _run_git_command(
        path,
        ["rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _run_git_command(
    cwd: Path,
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(cwd), *args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git executable was not found") from exc

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result


__all__ = [
    "RepoState",
    "commit_changes",
    "get_repo_state",
    "stage_artifact",
]
