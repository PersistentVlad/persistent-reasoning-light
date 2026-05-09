# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

import argparse
import json
import sys
from pathlib import Path

from core.artifact_types import SUPPORTED_ARTIFACT_TYPES
from core.storage import list_canonical_artifacts, save_runtime_artifact
from core.validation import validate_artifact_schema
from core.view_builder import write_working_context


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent Reasoning Light CLI")
    parser.add_argument(
        "--brain-root",
        default="reasoning-brain",
        help="Path to the reasoning brain root",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    load_brain = subparsers.add_parser("load-brain", help="Summarize canonical artifacts")
    load_brain.set_defaults(handler=_handle_load_brain)

    build_context = subparsers.add_parser(
        "build-context",
        help="Generate working_context.json",
    )
    build_context.set_defaults(handler=_handle_build_context)

    add_artifact = subparsers.add_parser(
        "add-artifact",
        help="Add an artifact suggestion to runtime/inbox",
    )
    artifact_input = add_artifact.add_mutually_exclusive_group(required=True)
    artifact_input.add_argument(
        "--artifact-file",
        help="Path to a JSON artifact suggestion file",
    )
    artifact_input.add_argument(
        "--artifact-json",
        help="Inline JSON artifact suggestion",
    )
    add_artifact.set_defaults(handler=_handle_add_artifact)

    validate_brain = subparsers.add_parser(
        "validate-brain",
        help="Validate canonical artifact files",
    )
    validate_brain.set_defaults(handler=_handle_validate_brain)

    return parser


def _handle_load_brain(args: argparse.Namespace) -> int:
    brain_root = _resolve_brain_root(args.brain_root)
    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        artifacts = list_canonical_artifacts(brain_root, artifact_type)
        label = artifact_type.removesuffix("Card").lower()
        print(f"{label}: {len(artifacts)}")
    return 0


def _handle_build_context(args: argparse.Namespace) -> int:
    brain_root = _resolve_brain_root(args.brain_root)
    output_path = write_working_context(brain_root)
    print(output_path)
    return 0


def _handle_add_artifact(args: argparse.Namespace) -> int:
    brain_root = _resolve_brain_root(args.brain_root)
    artifact_data = _load_artifact_input(args)
    validate_artifact_schema(artifact_data)
    output_path = save_runtime_artifact(brain_root, "inbox", artifact_data)
    print(output_path)
    return 0


def _handle_validate_brain(args: argparse.Namespace) -> int:
    brain_root = _resolve_brain_root(args.brain_root)
    total_artifacts = 0
    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        total_artifacts += len(list_canonical_artifacts(brain_root, artifact_type))
    print(f"canonical artifacts valid: {total_artifacts} artifact(s)")
    return 0


def _load_artifact_input(args: argparse.Namespace) -> dict[str, object]:
    if args.artifact_file:
        raw_text = Path(args.artifact_file).read_text(encoding="utf-8")
    else:
        raw_text = args.artifact_json

    try:
        raw_value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("artifact input must be valid JSON") from exc

    if not isinstance(raw_value, dict):
        raise ValueError("artifact input must be a JSON object")
    return dict(raw_value)


def _resolve_brain_root(value: str) -> Path:
    brain_root = Path(value)
    if not brain_root.exists():
        raise FileNotFoundError(f"reasoning brain root does not exist: {brain_root}")
    if not brain_root.is_dir():
        raise ValueError(f"reasoning brain root is not a directory: {brain_root}")
    return brain_root


if __name__ == "__main__":
    raise SystemExit(main())
