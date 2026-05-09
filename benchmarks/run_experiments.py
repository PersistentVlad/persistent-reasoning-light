# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Run multi-run experimental characterization for Persistent Reasoning Light.

This entry point is intentionally thin:
- it does not own experiment logic
- it delegates to benchmarks.tools.explore_pr_sensitivity
- it shares the same storage, governance, adapter, and metric substrate as
  ordinary benchmark execution
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
REASONING_ENGINE_ROOT = REPO_ROOT / "reasoning-engine"
if str(REASONING_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(REASONING_ENGINE_ROOT))


from benchmarks.tools.explore_pr_sensitivity import (  # noqa: E402
    DEFAULT_SCENARIO_REGIONS,
    explore_pr_sensitivity,
    parse_args,
)
from benchmarks.run_benchmarks import load_profile  # noqa: E402


DEFAULT_EXPERIMENT_SCENARIO_REGIONS = DEFAULT_SCENARIO_REGIONS
DEFAULT_EXPERIMENT_PROFILE = "gemini_flash_lite_latest"


def main() -> None:
    args = parse_args()
    profile = load_profile(args.profile or DEFAULT_EXPERIMENT_PROFILE)
    outputs = explore_pr_sensitivity(
        repo_root=Path(args.repo_root),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        scenario_regions=DEFAULT_EXPERIMENT_SCENARIO_REGIONS,
        include_pr_ephemeral=profile.diagnostic_modes.pr_ephemeral,
        max_runs=args.max_runs,
        plateau_window=args.plateau_window,
        harm_window=args.harm_window,
        epsilon_score=args.epsilon_score,
        epsilon_retrieval=args.epsilon_retrieval,
    )
    print(f"saved pr sensitivity summary: {outputs['summary_path']}")
    print(f"saved pr sensitivity markdown: {outputs['markdown_path']}")


if __name__ == "__main__":
    main()
