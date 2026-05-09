# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.benchmark_modes import BASELINE, PR_EPHEMERAL, PR_LIGHT_BRAIN
from benchmark_adapters.common.benchmark_paths import get_benchmark_paths
from benchmark_adapters.common.result_utils import validate_adapter_name
from benchmark_adapters.common.scenario_utils import load_benchmark_scenario
from benchmark_adapters.gemini import adapter as gemini_adapter
from benchmarks.tools.compare_results import build_comparison
from benchmarks.tools.compute_metrics_from_events import compute_result_from_events, load_events
from reasoning_brain_storage.tools import (
    compare_brain_snapshots,
    create_snapshot,
    export_governance_brain_state,
    inspect_brain_snapshot,
    load_benchmark_visible_working_context,
    load_brain,
    reset_to_empty,
)


DEFAULT_BACKEND = "gemini"
DEFAULT_MAX_RUNS = 5
DEFAULT_PLATEAU_WINDOW = 2
DEFAULT_HARM_WINDOW = 1
DEFAULT_EPSILON_SCORE = 0.05
DEFAULT_EPSILON_RETRIEVAL = 0.05
DEFAULT_SCENARIO_REGIONS: dict[str, list[str]] = {
    "strong_gain": ["sc_0_interrupt_compress_continue"],
    "neutral": ["sc_7_stateless_direct_transform"],
    "risk": ["sc_06_plan_reset"],
    "stress": ["sc_99_killer_all_scenarios"],
}

ModeOutputProvider = Callable[[str, str, int], str | None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explore PR sensitivity trajectories for Gemini benchmark scenarios."
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional benchmark profile name used for diagnostic mode gating.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root to run the exploration in.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to benchmarks/reports/pr_sensitivity.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=DEFAULT_MAX_RUNS,
        help="Maximum PR_LIGHT_BRAIN runs per scenario.",
    )
    parser.add_argument(
        "--plateau-window",
        type=int,
        default=DEFAULT_PLATEAU_WINDOW,
        help="Consecutive run window required to mark plateau.",
    )
    parser.add_argument(
        "--harm-window",
        type=int,
        default=DEFAULT_HARM_WINDOW,
        help="Consecutive run window required to mark harm.",
    )
    parser.add_argument(
        "--epsilon-score",
        type=float,
        default=DEFAULT_EPSILON_SCORE,
        help="Maximum absolute score delta for plateau detection.",
    )
    parser.add_argument(
        "--epsilon-retrieval",
        type=float,
        default=DEFAULT_EPSILON_RETRIEVAL,
        help="Maximum absolute retrieval delta for plateau detection.",
    )
    return parser.parse_args()


def explore_pr_sensitivity(
    *,
    repo_root: Path,
    output_dir: Path | None = None,
    scenario_regions: Mapping[str, Sequence[str]] | None = None,
    include_pr_ephemeral: bool = False,
    max_runs: int = DEFAULT_MAX_RUNS,
    plateau_window: int = DEFAULT_PLATEAU_WINDOW,
    harm_window: int = DEFAULT_HARM_WINDOW,
    epsilon_score: float = DEFAULT_EPSILON_SCORE,
    epsilon_retrieval: float = DEFAULT_EPSILON_RETRIEVAL,
    output_provider: ModeOutputProvider | None = None,
) -> dict[str, Any]:
    if max_runs <= 0:
        raise ValueError("max_runs must be positive")
    if plateau_window <= 0:
        raise ValueError("plateau_window must be positive")
    if harm_window <= 0:
        raise ValueError("harm_window must be positive")

    validated_adapter = validate_adapter_name(DEFAULT_BACKEND)
    paths = get_benchmark_paths(repo_root)
    exploration_output_dir = (
        output_dir.resolve()
        if output_dir is not None
        else (paths.reports_root / "pr_sensitivity").resolve()
    )
    exploration_output_dir.mkdir(parents=True, exist_ok=True)

    region_map = {
        region: [scenario_id for scenario_id in scenario_ids]
        for region, scenario_ids in (scenario_regions or DEFAULT_SCENARIO_REGIONS).items()
    }

    scenario_summaries: list[dict[str, Any]] = []
    trajectory_paths: list[str] = []

    for region_name, scenario_ids in region_map.items():
        for scenario_id in scenario_ids:
            trajectory = _explore_single_scenario(
                repo_root=repo_root,
                scenario_id=scenario_id,
                hypothesis_region=region_name,
                exploration_output_dir=exploration_output_dir,
                adapter_name=validated_adapter,
                include_pr_ephemeral=include_pr_ephemeral,
                max_runs=max_runs,
                plateau_window=plateau_window,
                harm_window=harm_window,
                epsilon_score=epsilon_score,
                epsilon_retrieval=epsilon_retrieval,
                output_provider=output_provider,
            )

            trajectory_path = exploration_output_dir / f"{scenario_id}.trajectory.json"
            _write_json(trajectory_path, trajectory)
            trajectory_paths.append(str(trajectory_path))
            scenario_summaries.append(_build_scenario_summary(trajectory))

    summary = {
        "backend": validated_adapter,
        "diagnostic_modes": {
            "pr_ephemeral": include_pr_ephemeral,
        },
        "config": {
            "max_runs": max_runs,
            "plateau_window": plateau_window,
            "harm_window": harm_window,
            "epsilon_score": epsilon_score,
            "epsilon_retrieval": epsilon_retrieval,
        },
        "scenario_regions": region_map,
        "trajectory_paths": trajectory_paths,
        "scenario_summaries": scenario_summaries,
    }

    summary_path = exploration_output_dir / "classification_summary.json"
    markdown_path = exploration_output_dir / "classification_summary.md"
    _write_json(summary_path, summary)
    markdown_path.write_text(_build_summary_markdown(summary), encoding="utf-8")

    return {
        "output_dir": exploration_output_dir,
        "summary_path": summary_path,
        "markdown_path": markdown_path,
        "trajectory_paths": trajectory_paths,
        "summary": summary,
    }


def detect_plateau(
    runs: Sequence[Mapping[str, Any]],
    *,
    plateau_window: int,
    epsilon_score: float,
    epsilon_retrieval: float,
) -> bool:
    if len(runs) < plateau_window:
        return False

    window = runs[-plateau_window:]
    for run in window:
        score_delta = run.get("score_delta")
        retrieval_delta = run.get("retrieval_delta")
        non_persisted = run.get("non_persisted_suggestion_count")
        persisted_delta = run.get("persisted_artifact_delta")

        if not isinstance(score_delta, (int, float)):
            return False
        if not isinstance(retrieval_delta, (int, float)):
            return False
        if abs(float(score_delta)) >= epsilon_score:
            return False
        if abs(float(retrieval_delta)) >= epsilon_retrieval:
            return False
        if not isinstance(non_persisted, int) or not isinstance(persisted_delta, int):
            return False
        if non_persisted < persisted_delta:
            return False

    return True


def detect_harm(
    runs: Sequence[Mapping[str, Any]],
    *,
    harm_window: int,
) -> bool:
    if len(runs) < harm_window:
        return False

    window = runs[-harm_window:]
    return all(_run_shows_harm(run) for run in window)


def _explore_single_scenario(
    *,
    repo_root: Path,
    scenario_id: str,
    hypothesis_region: str,
    exploration_output_dir: Path,
    adapter_name: str,
    include_pr_ephemeral: bool,
    max_runs: int,
    plateau_window: int,
    harm_window: int,
    epsilon_score: float,
    epsilon_retrieval: float,
    output_provider: ModeOutputProvider | None,
) -> dict[str, Any]:
    paths = get_benchmark_paths(repo_root)
    scenario_snapshot_dir = (
        exploration_output_dir / "_s" / _snapshot_series_key(scenario_id)
    )
    scenario_snapshot_dir.mkdir(parents=True, exist_ok=True)
    scenario = load_benchmark_scenario(paths, scenario_id)
    task_text = _build_task_text(scenario.config)

    reset_to_empty(
        empty_template_root=paths.empty_brain_root,
        runtime_root=paths.runtime_brain_root,
    )

    baseline_run = _run_single_mode(
        repo_root=repo_root,
        scenario_id=scenario_id,
        mode=BASELINE,
        task_text=task_text,
        adapter_name=adapter_name,
        run_index=1,
        output_provider=output_provider,
    )
    pr_ephemeral_run = (
        _run_single_mode(
            repo_root=repo_root,
            scenario_id=scenario_id,
            mode=PR_EPHEMERAL,
            task_text=task_text,
            adapter_name=adapter_name,
            run_index=1,
            output_provider=output_provider,
        )
        if include_pr_ephemeral
        else None
    )

    reset_to_empty(
        empty_template_root=paths.empty_brain_root,
        runtime_root=paths.runtime_brain_root,
    )

    pr_light_brain_runs: list[dict[str, Any]] = []
    plateau_reached = False
    degradation_detected = False
    stop_reason: str | None = None
    runs_to_plateau: int | None = None
    snapshot_series: dict[str, str] = {}

    for run_index in range(1, max_runs + 1):
        current_run = _run_single_mode(
            repo_root=repo_root,
            scenario_id=scenario_id,
            mode=PR_LIGHT_BRAIN,
            task_text=task_text,
            adapter_name=adapter_name,
            run_index=run_index,
            output_provider=output_provider,
        )
        comparison = build_comparison(
            baseline_run["result"],
            pr_ephemeral_run["result"] if pr_ephemeral_run is not None else None,
            current_run["result"],
            adapter_name=adapter_name,
        )
        summary_scores = comparison["summary_scores"]
        current_score = float(summary_scores["pr_light_brain_pr_stability_score"])
        snapshot_root = scenario_snapshot_dir / f"r{run_index}"
        create_snapshot(
            source_root=paths.runtime_brain_root,
            snapshot_root=snapshot_root,
        )
        snapshot_series[str(run_index)] = str(snapshot_root)
        snapshot_inspection = inspect_brain_snapshot(root=snapshot_root)

        working_context = load_benchmark_visible_working_context(root=paths.runtime_brain_root)
        context_size = _compute_context_size(working_context)
        artifact_count_total = snapshot_inspection.artifact_count_total
        previous_run = pr_light_brain_runs[-1] if pr_light_brain_runs else None
        previous_context_size = int(previous_run["context_size"]) if previous_run else 0
        previous_artifact_count = (
            int(previous_run["artifact_count_total"])
            if previous_run
            else 0
        )
        previous_score = float(previous_run["score"]) if previous_run else current_score
        previous_retrieval = (
            float(previous_run["retrieval_precision"])
            if previous_run
            else current_run["metrics"]["retrieval_precision"]
        )
        snapshot_comparison = (
            compare_brain_snapshots(
                snapshot_a_root=Path(str(previous_run["snapshot_root"])),
                snapshot_b_root=snapshot_root,
            )
            if previous_run
            else None
        )
        compact_snapshot_comparison = (
            _compact_snapshot_comparison(snapshot_comparison)
            if snapshot_comparison is not None
            else None
        )

        persisted_artifact_delta = artifact_count_total - previous_artifact_count
        context_growth = context_size - previous_context_size
        score_delta = None if previous_run is None else round(current_score - previous_score, 6)
        retrieval_delta = (
            None
            if previous_run is None
            else round(current_run["metrics"]["retrieval_precision"] - previous_retrieval, 6)
        )
        non_persisted_suggestion_count = max(
            current_run["metrics"]["artifact_suggested_count"] - persisted_artifact_delta,
            0,
        )
        pr_efficiency = (
            None
            if score_delta is None
            else round(score_delta / max(context_growth, 1), 6)
        )

        run_record = {
            "run_index": run_index,
            "score": current_score,
            "score_delta": score_delta,
            "baseline_score": float(summary_scores["baseline_pr_stability_score"]),
            "pr_ephemeral_score": (
                float(summary_scores["pr_ephemeral_pr_stability_score"])
                if summary_scores["pr_ephemeral_pr_stability_score"] is not None
                else None
            ),
            "prompt_tokens": current_run["token_usage"]["prompt_tokens"],
            "output_tokens": current_run["token_usage"]["output_tokens"],
            "total_tokens": current_run["token_usage"]["total_tokens"],
            "retrieval_precision": current_run["metrics"]["retrieval_precision"],
            "retrieval_delta": retrieval_delta,
            "knowledge_retention_rate": current_run["metrics"]["knowledge_retention_rate"],
            "context_utilization_rate": current_run["metrics"]["context_utilization_rate"],
            "reuse_rate": current_run["metrics"]["reuse_rate"],
            "artifact_suggested_count": current_run["metrics"]["artifact_suggested_count"],
            "working_context": working_context,
            "context_size": context_size,
            "context_growth_per_run": context_growth,
            "artifact_count_total": artifact_count_total,
            "artifact_count_by_type": dict(snapshot_inspection.artifact_count_by_type),
            "persisted_artifact_delta": persisted_artifact_delta,
            "non_persisted_suggestion_count": non_persisted_suggestion_count,
            "pr_efficiency": pr_efficiency,
            "artifact_suggestion": current_run["artifact_suggestion"],
            "snapshot_root": str(snapshot_root),
            "snapshot_state_summary": {
                "artifact_count_total": snapshot_inspection.artifact_count_total,
                "artifact_count_by_type": dict(snapshot_inspection.artifact_count_by_type),
            },
            "snapshot_comparison_to_previous": compact_snapshot_comparison,
            "plateau_flag": False,
            "harm_flag": False,
        }

        pr_light_brain_runs.append(run_record)

        plateau_flag = detect_plateau(
            pr_light_brain_runs,
            plateau_window=plateau_window,
            epsilon_score=epsilon_score,
            epsilon_retrieval=epsilon_retrieval,
        )
        harm_flag = detect_harm(
            pr_light_brain_runs,
            harm_window=harm_window,
        )
        run_record["plateau_flag"] = plateau_flag
        run_record["harm_flag"] = harm_flag

        if plateau_flag:
            plateau_reached = True
            runs_to_plateau = run_index
            stop_reason = "plateau"
            break
        if harm_flag:
            degradation_detected = True
            stop_reason = "harm"
            break

    if stop_reason is None:
        stop_reason = "max_runs"

    cumulative_total_tokens = _compute_cumulative_total_tokens(pr_light_brain_runs)
    tokens_to_plateau = _compute_tokens_to_plateau(
        pr_light_brain_runs,
        plateau_reached=plateau_reached,
        runs_to_plateau=runs_to_plateau,
    )
    score_gain_per_token = _compute_score_gain_per_token(
        pr_light_brain_runs,
        cumulative_total_tokens=cumulative_total_tokens,
    )

    observed_classification = _classify_observed_trajectory(
        baseline_run=baseline_run,
        pr_ephemeral_run=pr_ephemeral_run,
        pr_light_brain_runs=pr_light_brain_runs,
        degradation_detected=degradation_detected,
    )

    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario.config["scenario_name"],
        "hypothesis_region": hypothesis_region,
        "stress_case": hypothesis_region == "stress",
        "scenario_role": "integration_stress" if hypothesis_region == "stress" else "diagnostic",
        "observed_classification": observed_classification,
        "backend": adapter_name,
        "config": {
            "max_runs": max_runs,
            "plateau_window": plateau_window,
            "harm_window": harm_window,
            "epsilon_score": epsilon_score,
            "epsilon_retrieval": epsilon_retrieval,
        },
        "reference_runs": {
            "baseline": _serialize_reference_run(baseline_run),
            "pr_ephemeral": (
                _serialize_reference_run(pr_ephemeral_run)
                if pr_ephemeral_run is not None
                else None
            ),
        },
        "snapshot_series": dict(snapshot_series),
        "pr_light_brain_runs": pr_light_brain_runs,
        "plateau_interpretation": _build_plateau_interpretation(
            pr_light_brain_runs,
            plateau_reached=plateau_reached,
        ),
        "harm_interpretation": _build_harm_interpretation(
            pr_light_brain_runs,
            degradation_detected=degradation_detected,
        ),
        "final_snapshot_delta_summary": _final_snapshot_delta_summary(pr_light_brain_runs),
        "cumulative_total_tokens": cumulative_total_tokens,
        "tokens_to_plateau": tokens_to_plateau,
        "score_gain_per_token": score_gain_per_token,
        "plateau_reached": plateau_reached,
        "runs_to_plateau": runs_to_plateau,
        "degradation_detected": degradation_detected,
        "stopped_early": stop_reason != "max_runs",
        "stop_reason": stop_reason,
    }


def _run_single_mode(
    *,
    repo_root: Path,
    scenario_id: str,
    mode: str,
    task_text: str,
    adapter_name: str,
    run_index: int,
    output_provider: ModeOutputProvider | None,
) -> dict[str, Any]:
    agent_output = output_provider(scenario_id, mode, run_index) if output_provider else None
    adapter_result = gemini_adapter.run_scenario(
        scenario_id,
        mode=mode,
        task_text=task_text,
        agent_output=agent_output,
        adapter_name=adapter_name,
        repo_root=repo_root,
        overwrite_existing_artifacts=True,
    )
    events = load_events(adapter_result["event_log_path"])
    result = compute_result_from_events(events, adapter_name=adapter_name)
    token_usage = _normalize_token_usage(adapter_result.get("token_usage"))
    return {
        "context": adapter_result["context"],
        "artifact_suggestion": adapter_result["artifact_suggestion"],
        "token_usage": token_usage,
        "result": result,
        "metrics": _extract_key_metrics(result),
    }


def _extract_key_metrics(result: Mapping[str, Any]) -> dict[str, float | int]:
    knowledge = _require_mapping(result, "knowledge_persistence")
    retrieval = _require_mapping(result, "retrieval_metrics")
    persistence = _require_mapping(result, "persistence_integrity")
    return {
        "retrieval_precision": _require_numeric(retrieval, "retrieval_precision"),
        "knowledge_retention_rate": _require_numeric(
            knowledge,
            "knowledge_retention_rate",
        ),
        "context_utilization_rate": _require_numeric(
            knowledge,
            "context_utilization_rate",
        ),
        "reuse_rate": _require_numeric(knowledge, "reuse_rate"),
        "artifact_suggested_count": int(
            _require_numeric(persistence, "artifact_suggested_count")
        ),
    }


def _serialize_reference_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context": run["context"],
        "artifact_suggestion": run["artifact_suggestion"],
        "prompt_tokens": run["token_usage"]["prompt_tokens"],
        "output_tokens": run["token_usage"]["output_tokens"],
        "total_tokens": run["token_usage"]["total_tokens"],
        "metrics": run["metrics"],
    }


def _load_runtime_inventory(runtime_root: Path) -> dict[str, Any]:
    brain = load_brain(root=runtime_root)
    state = export_governance_brain_state(brain=brain)
    artifacts_by_id = state["artifacts_by_id"]
    by_type: dict[str, int] = {}
    for artifact in artifacts_by_id.values():
        artifact_type = artifact.get("type")
        if not isinstance(artifact_type, str):
            continue
        by_type[artifact_type] = by_type.get(artifact_type, 0) + 1

    return {
        "artifact_count_total": len(artifacts_by_id),
        "artifact_count_by_type": dict(sorted(by_type.items())),
    }


def _normalize_token_usage(value: object) -> dict[str, int | None]:
    if not isinstance(value, Mapping):
        return {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "prompt_tokens": _normalize_optional_token_count(value.get("prompt_tokens")),
        "output_tokens": _normalize_optional_token_count(value.get("output_tokens")),
        "total_tokens": _normalize_optional_token_count(value.get("total_tokens")),
    }


def _normalize_optional_token_count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _compute_cumulative_total_tokens(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
) -> int | None:
    if not pr_light_brain_runs:
        return None

    totals: list[int] = []
    for run in pr_light_brain_runs:
        total_tokens = run.get("total_tokens")
        if not isinstance(total_tokens, int):
            return None
        totals.append(total_tokens)
    return sum(totals)


def _compute_tokens_to_plateau(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
    *,
    plateau_reached: bool,
    runs_to_plateau: int | None,
) -> int | None:
    if not plateau_reached or runs_to_plateau is None:
        return None

    return _compute_cumulative_total_tokens(pr_light_brain_runs[:runs_to_plateau])


def _compute_score_gain_per_token(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
    *,
    cumulative_total_tokens: int | None,
) -> float | None:
    if not pr_light_brain_runs:
        return None
    if not isinstance(cumulative_total_tokens, int) or cumulative_total_tokens <= 0:
        return None

    initial_score = float(pr_light_brain_runs[0]["score"])
    best_score = max(float(run["score"]) for run in pr_light_brain_runs)
    return round((best_score - initial_score) / cumulative_total_tokens, 6)


def _compact_snapshot_comparison(comparison: Any) -> dict[str, Any]:
    return {
        "artifact_count_total": _serialize_dataclass(comparison.artifact_count_total),
        "artifact_count_by_type": {
            artifact_type: _serialize_dataclass(delta)
            for artifact_type, delta in comparison.artifact_count_by_type.items()
        },
        "artifact_ids": {
            "added": list(comparison.artifact_ids["added"]),
            "removed": list(comparison.artifact_ids["removed"]),
        },
        "working_context_diff": _serialize_dataclass(comparison.working_context_diff),
    }


def _compute_context_size(context: Mapping[str, Any]) -> int:
    decisions = _require_list(context, "decisions")
    constraints = _require_list(context, "constraints")
    open_issues = _require_list(context, "open_issues")
    return len(decisions) + len(constraints) + len(open_issues)


def _run_shows_harm(run: Mapping[str, Any]) -> bool:
    score_delta = run.get("score_delta")
    retrieval_delta = run.get("retrieval_delta")
    context_growth = run.get("context_growth_per_run")
    non_persisted = run.get("non_persisted_suggestion_count")

    if isinstance(score_delta, (int, float)) and float(score_delta) < 0:
        return True

    if (
        isinstance(retrieval_delta, (int, float))
        and isinstance(context_growth, int)
        and float(retrieval_delta) < 0
        and context_growth > 0
    ):
        return True

    if (
        isinstance(non_persisted, int)
        and non_persisted > 0
        and isinstance(score_delta, (int, float))
        and float(score_delta) <= 0
    ):
        return True

    return False


def _classify_observed_trajectory(
    *,
    baseline_run: Mapping[str, Any],
    pr_ephemeral_run: Mapping[str, Any] | None,
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
    degradation_detected: bool,
) -> str:
    if not pr_light_brain_runs:
        return "neutral"

    if degradation_detected:
        return "risk"

    best_gain = max(
        float(run["score"]) - max(
            [
                float(run["baseline_score"]),
                *(
                    [float(run["pr_ephemeral_score"])]
                    if run.get("pr_ephemeral_score") is not None
                    else []
                ),
            ]
        )
        for run in pr_light_brain_runs
    )
    final_context_size = int(pr_light_brain_runs[-1]["context_size"])
    baseline_context_size = _compute_context_size(_require_mapping(baseline_run, "context"))
    pr_ephemeral_context_size = (
        _compute_context_size(_require_mapping(pr_ephemeral_run, "context"))
        if pr_ephemeral_run is not None
        else 0
    )

    if best_gain >= 0.15 and final_context_size >= max(baseline_context_size, pr_ephemeral_context_size):
        return "strong_gain"

    return "neutral"


def _build_scenario_summary(trajectory: Mapping[str, Any]) -> dict[str, Any]:
    pr_runs = _require_list(trajectory, "pr_light_brain_runs")
    best_score = max((float(run["score"]) for run in pr_runs), default=0.0)
    final_score = float(pr_runs[-1]["score"]) if pr_runs else 0.0
    final_context_size = int(pr_runs[-1]["context_size"]) if pr_runs else 0
    return {
        "scenario_id": trajectory["scenario_id"],
        "hypothesis_region": trajectory["hypothesis_region"],
        "stress_case": bool(trajectory.get("stress_case")),
        "scenario_role": trajectory.get("scenario_role", "diagnostic"),
        "observed_classification": trajectory["observed_classification"],
        "runs_executed": len(pr_runs),
        "best_score": round(best_score, 6),
        "final_score": round(final_score, 6),
        "final_context_size": final_context_size,
        "cumulative_total_tokens": trajectory.get("cumulative_total_tokens"),
        "tokens_to_plateau": trajectory.get("tokens_to_plateau"),
        "score_gain_per_token": trajectory.get("score_gain_per_token"),
        "final_snapshot_delta_summary": trajectory["final_snapshot_delta_summary"],
        "plateau_reached": trajectory["plateau_reached"],
        "runs_to_plateau": trajectory["runs_to_plateau"],
        "degradation_detected": trajectory["degradation_detected"],
        "stop_reason": trajectory["stop_reason"],
    }


def _build_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# PR Sensitivity Exploration Summary",
        "",
        f"Backend: {summary['backend']}",
        "",
        "| Scenario | Hypothesis | Observed | Runs | Best Score | Final Score | Plateau | Harm |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for item in _require_list(summary, "scenario_summaries"):
        lines.append(
            "| {scenario_id} | {hypothesis_region} | {observed_classification} | {runs_executed} | {best_score:.3f} | {final_score:.3f} | {plateau_reached} | {degradation_detected} |".format(
                **item
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_plateau_interpretation(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
    *,
    plateau_reached: bool,
) -> dict[str, Any]:
    final_delta = _final_snapshot_delta_summary(pr_light_brain_runs)
    return {
        "metric_driven": plateau_reached,
        "snapshot_delta_supports_plateau": bool(
            plateau_reached
            and final_delta is not None
            and final_delta["artifact_count_total"]["delta"] == 0
            and not final_delta["artifact_ids"]["added"]
            and not final_delta["artifact_ids"]["removed"]
            and _working_context_diff_is_empty(final_delta["working_context_diff"])
        ),
        "final_snapshot_delta_summary": final_delta,
    }


def _build_harm_interpretation(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
    *,
    degradation_detected: bool,
) -> dict[str, Any]:
    final_delta = _final_snapshot_delta_summary(pr_light_brain_runs)
    state_growth_detected = bool(
        final_delta is not None and final_delta["artifact_count_total"]["delta"] > 0
    )
    return {
        "metric_driven": degradation_detected,
        "snapshot_delta_indicates_state_growth": state_growth_detected,
        "final_snapshot_delta_summary": final_delta,
    }


def _final_snapshot_delta_summary(
    pr_light_brain_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    for run in reversed(pr_light_brain_runs):
        snapshot_delta = run.get("snapshot_comparison_to_previous")
        if isinstance(snapshot_delta, Mapping):
            return dict(snapshot_delta)
    return None


def _working_context_diff_is_empty(working_context_diff: Mapping[str, Any]) -> bool:
    return (
        not bool(working_context_diff.get("active_task_changed"))
        and not _require_list(working_context_diff, "constraints_added")
        and not _require_list(working_context_diff, "constraints_removed")
        and not _require_list(working_context_diff, "decisions_added")
        and not _require_list(working_context_diff, "decisions_removed")
        and not _require_list(working_context_diff, "open_issues_added")
        and not _require_list(working_context_diff, "open_issues_removed")
    )


def _serialize_dataclass(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _serialize_dataclass(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _serialize_dataclass(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_dataclass(item) for item in value]
    return value


def _snapshot_series_key(scenario_id: str) -> str:
    return hashlib.md5(scenario_id.encode("utf-8")).hexdigest()[:8]


def _build_task_text(config: Mapping[str, Any]) -> str:
    description = str(config.get("description", "")).strip()
    steps = _require_list(config, "steps")
    lines = [description] if description else []
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        instruction = step.get("instruction")
        if isinstance(instruction, str) and instruction.strip():
            lines.append(instruction.strip())
    return "\n".join(lines)


def _require_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"expected mapping for key '{key}'")
    return value


def _require_list(container: Mapping[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        raise ValueError(f"expected list for key '{key}'")
    return value


def _require_numeric(container: Mapping[str, Any], key: str) -> float:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected numeric value for key '{key}'")
    return float(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def main() -> None:
    args = parse_args()
    include_pr_ephemeral = False
    if args.profile:
        from benchmarks.run_benchmarks import load_profile

        include_pr_ephemeral = load_profile(args.profile).diagnostic_modes.pr_ephemeral
    outputs = explore_pr_sensitivity(
        repo_root=Path(args.repo_root),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        include_pr_ephemeral=include_pr_ephemeral,
        max_runs=args.max_runs,
        plateau_window=args.plateau_window,
        harm_window=args.harm_window,
        epsilon_score=args.epsilon_score,
        epsilon_retrieval=args.epsilon_retrieval,
    )
    print(f"saved pr sensitivity summary: {outputs['summary_path']}")


if __name__ == "__main__":
    main()
