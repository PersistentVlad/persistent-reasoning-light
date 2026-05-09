# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Generate benchmark summary reports from comparison artifacts and radar charts.

This tool:
- reads canonical comparison artifacts
- renders radar SVG charts
- assembles a markdown summary report

It does not:
- execute benchmark scenarios
- derive raw benchmark metrics
- define benchmark truth

Interpretation text in this report is template-based reporting scaffolding.
It should not be treated as semantic inference beyond the available comparison artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.result_utils import ensure_output_path_writable  # noqa: E402
from benchmark_adapters.common.benchmark_modes import (  # noqa: E402
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmarks.tools.compare_results import (  # noqa: E402
    validate_comparison_schema,
)
from benchmarks.tools.generate_quickchart_radar_svg import (  # noqa: E402
    generate_radar_svg,
    validate_required_radar_template_set,
)


REQUIRED_REPORT_METRIC_NAMES = (
    "retrieval_precision",
    "context_utilization_rate",
    "reuse_rate",
    "knowledge_retention_rate",
    "structural_integrity_score",
)
RUN_REPORT_SHOWCASE_RADAR_NAMES = (
    "reasoning_integrity",
    "reasoning_stability",
    "context_efficiency",
    "operational_cost",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark summary markdown report."
    )
    parser.add_argument(
        "--comparison",
        required=True,
        help="Path to comparison JSON file",
    )
    parser.add_argument(
        "--radars",
        nargs="+",
        required=True,
        help="List of radar names to include",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output markdown report path",
    )
    parser.add_argument(
        "--charts-dir",
        default=None,
        help="Optional directory to store generated radar SVG charts",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing report or generated chart output file.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"json file not found: {path}")
    if not path.is_file():
        raise ValueError(f"json path is not a file: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"json file must contain an object: {path}")

    return data


def build_summary_report(
    comparison: dict[str, Any],
    chart_paths: list[Path],
    chart_failures: list[str] | None = None,
) -> str:
    """
    Build a markdown benchmark summary report.

    This report combines validated comparison artifacts, generated radar charts,
    and template-based interpretation text. Interpretation is reporting scaffold,
    not semantic inference beyond the comparison inputs.
    """
    validated_comparison = validate_comparison_schema(comparison)
    comparison_metadata = validated_comparison["comparison_metadata"]
    summary_scores = validated_comparison["summary_scores"]
    metrics = _build_metrics_index(validated_comparison)
    _validate_required_report_metrics(metrics)

    scenario_id = _require_string_field(
        comparison_metadata,
        "scenario_id",
        "comparison_metadata",
    )
    adapter = _require_string_field(
        comparison_metadata,
        "adapter",
        "comparison_metadata",
    )

    baseline_score = _require_numeric_field(
        summary_scores,
        "baseline_pr_stability_score",
        "summary_scores",
    )
    pr_ephemeral_score = _require_optional_numeric_field(
        summary_scores,
        "pr_ephemeral_pr_stability_score",
        "summary_scores",
    )
    pr_light_brain_score = _require_numeric_field(
        summary_scores,
        "pr_light_brain_pr_stability_score",
        "summary_scores",
    )

    report_lines: list[str] = []

    report_lines.append(f"# Benchmark Summary Report - {scenario_id}")
    report_lines.append("")
    report_lines.append(f"**Adapter:** {adapter}")
    report_lines.append("")

    report_lines.append("## PR Stability Scores")
    report_lines.append("")
    report_lines.append("| Mode | Score |")
    report_lines.append("|------|--------|")
    report_lines.append(f"| baseline | {baseline_score:.4f} |")
    if pr_ephemeral_score is not None:
        report_lines.append(f"| pr_ephemeral | {pr_ephemeral_score:.4f} |")
    report_lines.append(f"| pr_light_brain | {pr_light_brain_score:.4f} |")
    report_lines.append("")

    report_lines.append("## Radar Charts")
    report_lines.append("")
    if chart_paths:
        for path in chart_paths:
            report_lines.append(f"![{path.stem}]({_chart_link_target(path)})")
            report_lines.append("")
    else:
        report_lines.append(
            "Radar chart rendering was unavailable during this run; no SVG charts were generated."
        )
        report_lines.append("")

    if chart_failures:
        report_lines.append("Chart rendering warnings:")
        for warning in chart_failures:
            report_lines.append(f"- {warning}")
        report_lines.append("")

    report_lines.append("## Key Metrics")
    report_lines.append("")

    for metric_name in REQUIRED_REPORT_METRIC_NAMES:
        entry = _require_metric_entry(metrics, metric_name)
        values = entry["values"]

        report_lines.append(f"### {metric_name}")
        report_lines.append("")
        report_lines.append(f"- baseline: {values['baseline']}")
        if values.get(PR_EPHEMERAL) is not None:
            report_lines.append(f"- pr_ephemeral: {values[PR_EPHEMERAL]}")
        report_lines.append(f"- pr_light_brain: {values['pr_light_brain']}")
        report_lines.append("")

    report_lines.append("## Interpretation (Template)")
    report_lines.append("")
    report_lines.append(
        "This interpretation section is report scaffold text derived from the comparison artifact."
    )
    report_lines.append(
        "It summarizes the observed comparison values without asserting semantic truth beyond those inputs."
    )
    report_lines.append("")

    return "\n".join(report_lines)


def generate_charts(
    comparison: dict[str, Any],
    radar_names: list[str],
    charts_dir: Path,
    *,
    overwrite: bool = False,
    output_name_template: str = "{scenario_id}.{radar_name}.svg",
) -> tuple[list[Path], list[str]]:
    validated_comparison = validate_comparison_schema(comparison)
    comparison_metadata = validated_comparison["comparison_metadata"]
    metrics = _build_metrics_index(validated_comparison)
    scenario_id = _require_string_field(
        comparison_metadata,
        "scenario_id",
        "comparison_metadata",
    )

    charts_dir.mkdir(parents=True, exist_ok=True)

    baseline_result = _build_chart_result(metrics, BASELINE)
    pr_ephemeral_result = _build_chart_result(metrics, PR_EPHEMERAL)
    pr_light_brain_result = _build_chart_result(metrics, PR_LIGHT_BRAIN)

    chart_paths: list[Path] = []
    chart_failures: list[str] = []

    for radar_name in radar_names:
        try:
            svg = generate_radar_svg(
                radar_name,
                baseline_results=baseline_result,
                pr_ephemeral_results=pr_ephemeral_result,
                pr_light_brain_results=pr_light_brain_result,
            )
        except Exception as exc:
            chart_failures.append(
                f"{radar_name}: {type(exc).__name__}: {exc}"
            )
            continue

        output_path = charts_dir / output_name_template.format(
            scenario_id=scenario_id,
            radar_name=radar_name,
        )
        ensure_output_path_writable(
            output_path,
            overwrite=overwrite,
            artifact_label="radar svg",
        )
        output_path.write_text(svg, encoding="utf-8")

        chart_paths.append(output_path)

    return chart_paths, chart_failures


def save_report(path: Path, content: str, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label="summary report",
    )
    path.write_text(content, encoding="utf-8")


def save_json_artifact(
    path: Path,
    data: dict[str, Any],
    *,
    overwrite: bool = False,
    artifact_label: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label=artifact_label,
    )
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def generate_summary_report_artifact(
    comparison_path: Path,
    *,
    radar_names: list[str],
    output_path: Path,
    charts_dir: Path | None = None,
    overwrite: bool = False,
) -> tuple[Path, list[Path], list[str]]:
    comparison = load_json(comparison_path)

    resolved_charts_dir = (
        charts_dir if charts_dir is not None else output_path.parent / "charts"
    )

    chart_paths, chart_failures = generate_charts(
        comparison,
        radar_names=radar_names,
        charts_dir=resolved_charts_dir,
        overwrite=overwrite,
    )

    report = build_summary_report(
        comparison,
        chart_paths,
        chart_failures=chart_failures,
    )
    save_report(output_path, report, overwrite=overwrite)

    return output_path, chart_paths, chart_failures


def build_run_comparison_summary(
    comparisons_by_scenario: dict[str, dict[str, Any]],
    *,
    run_id: str,
    agent_metadata: dict[str, str],
    showcase_scenario_id: str,
    run_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not comparisons_by_scenario:
        raise ValueError("run comparison summary requires at least one scenario comparison")

    validated_agent_metadata = _validate_run_agent_metadata(agent_metadata)
    validated_run_metadata = _validate_optional_run_metadata(run_metadata)

    scenario_rows: list[dict[str, Any]] = []
    baseline_scores: list[float] = []
    pr_ephemeral_scores: list[float] = []
    pr_light_brain_scores: list[float] = []
    pr_ephemeral_enabled = False

    for scenario_id in sorted(comparisons_by_scenario):
        validated = validate_comparison_schema(comparisons_by_scenario[scenario_id])
        summary_scores = validated["summary_scores"]
        baseline_score = _require_numeric_field(
            summary_scores,
            "baseline_pr_stability_score",
            "summary_scores",
        )
        pr_ephemeral_score = _require_optional_numeric_field(
            summary_scores,
            "pr_ephemeral_pr_stability_score",
            "summary_scores",
        )
        pr_light_brain_score = _require_numeric_field(
            summary_scores,
            "pr_light_brain_pr_stability_score",
            "summary_scores",
        )

        baseline_scores.append(baseline_score)
        if pr_ephemeral_score is not None:
            pr_ephemeral_enabled = True
            pr_ephemeral_scores.append(pr_ephemeral_score)
        pr_light_brain_scores.append(pr_light_brain_score)

        scenario_rows.append(
            {
                "scenario_id": scenario_id,
                "comparison_path": f"scenarios/{scenario_id}.comparison.json",
                "baseline_pr_stability_score": baseline_score,
                "pr_ephemeral_pr_stability_score": pr_ephemeral_score,
                "pr_light_brain_pr_stability_score": pr_light_brain_score,
            }
        )

    return {
        "run_metadata": {
            "run_id": run_id,
            "adapter": validated_agent_metadata["adapter"],
            "full_agent_name": validated_agent_metadata["full_agent_name"],
            "agent_model": validated_agent_metadata["agent_model"],
            "scenario_count": len(scenario_rows),
            "showcase_scenario_id": showcase_scenario_id,
            **validated_run_metadata,
        },
        "stability_scores": {
            "baseline_average_pr_stability_score": _average(baseline_scores),
            "pr_ephemeral_average_pr_stability_score": (
                _average(pr_ephemeral_scores) if pr_ephemeral_scores else None
            ),
            "pr_light_brain_average_pr_stability_score": _average(pr_light_brain_scores),
        },
        "diagnostic_modes": {
            "pr_ephemeral": pr_ephemeral_enabled,
        },
        "effect_summary": _build_effect_summary(comparisons_by_scenario),
        "scenario_comparisons": scenario_rows,
    }


def build_run_summary_report(
    comparison_summary: dict[str, Any],
    *,
    chart_paths: list[Path],
    warnings: list[str],
) -> str:
    run_metadata = _require_dict_field(
        comparison_summary,
        "run_metadata",
        "comparison_summary",
    )
    stability_scores = _require_dict_field(
        comparison_summary,
        "stability_scores",
        "comparison_summary",
    )
    scenario_comparisons = _require_list_field(
        comparison_summary,
        "scenario_comparisons",
        "comparison_summary",
    )
    effect_summary = _require_dict_field(
        comparison_summary,
        "effect_summary",
        "comparison_summary",
    )
    diagnostic_modes = _require_dict_field(
        comparison_summary,
        "diagnostic_modes",
        "comparison_summary",
    )

    run_id = _require_string_field(run_metadata, "run_id", "run_metadata")
    adapter = _require_string_field(run_metadata, "adapter", "run_metadata")
    full_agent_name = _require_string_field(
        run_metadata,
        "full_agent_name",
        "run_metadata",
    )
    agent_model = _require_string_field(
        run_metadata,
        "agent_model",
        "run_metadata",
    )
    showcase_scenario_id = _require_string_field(
        run_metadata,
        "showcase_scenario_id",
        "run_metadata",
    )
    scenario_count = int(_require_numeric_field(run_metadata, "scenario_count", "run_metadata"))

    baseline_average = _require_numeric_field(
        stability_scores,
        "baseline_average_pr_stability_score",
        "stability_scores",
    )
    pr_ephemeral_average = _require_optional_numeric_field(
        stability_scores,
        "pr_ephemeral_average_pr_stability_score",
        "stability_scores",
    )
    pr_light_brain_average = _require_numeric_field(
        stability_scores,
        "pr_light_brain_average_pr_stability_score",
        "stability_scores",
    )
    pr_ephemeral_enabled = _require_bool_field(
        diagnostic_modes,
        "pr_ephemeral",
        "diagnostic_modes",
    )

    report_lines: list[str] = []
    report_lines.append("# Benchmark Summary")
    report_lines.append("")
    report_lines.append("## Run Metadata")
    report_lines.append("")
    report_lines.append(f"- run_id: {run_id}")
    report_lines.append(f"- adapter: {adapter}")
    report_lines.append(f"- Full Agent Name: {full_agent_name}")
    report_lines.append(f"- Agent Model: {agent_model}")
    report_lines.append(f"- scenario_count: {scenario_count}")
    report_lines.append(f"- showcase_scenario_id: {showcase_scenario_id}")
    backend = run_metadata.get("backend")
    if isinstance(backend, str):
        report_lines.append(f"- backend: {backend}")
    provider_profile = run_metadata.get("provider_profile")
    if isinstance(provider_profile, str):
        report_lines.append(f"- provider_profile: {provider_profile}")
    mode_to_key_mapping_enabled = run_metadata.get("mode_to_key_mapping_enabled")
    if isinstance(mode_to_key_mapping_enabled, bool):
        report_lines.append(
            f"- mode_to_key_mapping_enabled: {str(mode_to_key_mapping_enabled).lower()}"
        )
    inter_scenario_delay_seconds = run_metadata.get("inter_scenario_delay_seconds")
    if isinstance(inter_scenario_delay_seconds, (int, float)) and not isinstance(
        inter_scenario_delay_seconds,
        bool,
    ):
        report_lines.append(
            f"- inter_scenario_delay_seconds: {inter_scenario_delay_seconds}"
        )
    quota_stop_reason = run_metadata.get("quota_stop_reason")
    if isinstance(quota_stop_reason, str):
        report_lines.append(f"- quota_stop_reason: {quota_stop_reason}")
    else:
        report_lines.append("- quota_stop_reason: none")
    quota_429_count_total = run_metadata.get("429_count_total")
    if isinstance(quota_429_count_total, (int, float)) and not isinstance(
        quota_429_count_total,
        bool,
    ):
        report_lines.append(f"- 429_count_total: {int(quota_429_count_total)}")
    selected_scenario_subset = run_metadata.get("selected_scenario_subset")
    if isinstance(selected_scenario_subset, list):
        report_lines.append(
            f"- selected_scenario_subset: {', '.join(str(item) for item in selected_scenario_subset)}"
        )
    executed_modes = run_metadata.get("executed_modes")
    if isinstance(executed_modes, list):
        report_lines.append(f"- executed_modes: {', '.join(str(item) for item in executed_modes)}")
    report_lines.append(
        f"- diagnostic_modes.pr_ephemeral: {str(pr_ephemeral_enabled).lower()}"
    )
    report_lines.append("")
    report_lines.append("## Executive Summary")
    report_lines.append("")
    report_lines.append(
        "This report aggregates validated comparison artifacts for the current benchmark run."
    )
    report_lines.append(
        "It is scaffold reporting over comparison outputs and does not claim semantic truth beyond those artifacts."
    )
    if chart_paths:
        report_lines.append("")
        report_lines.append(f"Showcase radar charts were generated for `{showcase_scenario_id}`:")
        for path in chart_paths:
            report_lines.append(f"- [{path.name}]({_chart_link_target(path)})")
    report_lines.append("")
    report_lines.append("## Human-Facing Effects")
    report_lines.append("")
    report_lines.append(
        "This section is a small interpretive layer derived from existing raw metrics."
    )
    _append_effect_summary_line(
        report_lines,
        label="reuse improvement",
        effect_entry=_require_optional_effect_entry(effect_summary, "reuse_improvement"),
        positive_suffix="",
        negative_suffix="",
    )
    _append_effect_summary_line(
        report_lines,
        label="rediscovery reduction",
        effect_entry=_require_optional_effect_entry(effect_summary, "rediscovery_reduction"),
        positive_suffix="% lower",
        negative_suffix="% higher",
    )
    report_lines.append("")
    report_lines.append("## Stability Scores")
    report_lines.append("")
    report_lines.append("| Mode | Average Score |")
    report_lines.append("|------|---------------|")
    report_lines.append(f"| baseline | {baseline_average:.4f} |")
    if pr_ephemeral_average is not None:
        report_lines.append(f"| pr_ephemeral | {pr_ephemeral_average:.4f} |")
    report_lines.append(f"| pr_light_brain | {pr_light_brain_average:.4f} |")
    report_lines.append("")
    report_lines.append("## Per-Scenario Comparison Table")
    report_lines.append("")
    if pr_ephemeral_enabled:
        report_lines.append("| Scenario | Baseline | PR-Ephemeral | PR-Light + Brain | Comparison |")
        report_lines.append("|----------|----------|--------------|------------------|------------|")
    else:
        report_lines.append("| Scenario | Baseline | PR-Light + Brain | Comparison |")
        report_lines.append("|----------|----------|------------------|------------|")

    for entry in scenario_comparisons:
        if not isinstance(entry, dict):
            raise ValueError("comparison_summary scenario_comparisons entries must be objects")
        scenario_id = _require_string_field(entry, "scenario_id", "scenario_comparisons entry")
        comparison_path = _require_string_field(
            entry,
            "comparison_path",
            "scenario_comparisons entry",
        )
        baseline_score = _require_numeric_field(
            entry,
            "baseline_pr_stability_score",
            "scenario_comparisons entry",
        )
        pr_ephemeral_score = _require_optional_numeric_field(
            entry,
            "pr_ephemeral_pr_stability_score",
            "scenario_comparisons entry",
        )
        pr_light_brain_score = _require_numeric_field(
            entry,
            "pr_light_brain_pr_stability_score",
            "scenario_comparisons entry",
        )
        if pr_ephemeral_enabled:
            pr_ephemeral_cell = (
                f"{pr_ephemeral_score:.4f}" if pr_ephemeral_score is not None else "n/a"
            )
            report_lines.append(
                "| "
                f"{scenario_id} | "
                f"{baseline_score:.4f} | "
                f"{pr_ephemeral_cell} | "
                f"{pr_light_brain_score:.4f} | "
                f"[comparison]({comparison_path}) |"
            )
        else:
            report_lines.append(
                "| "
                f"{scenario_id} | "
                f"{baseline_score:.4f} | "
                f"{pr_light_brain_score:.4f} | "
                f"[comparison]({comparison_path}) |"
            )

    report_lines.append("")
    report_lines.append("## Notes / Degradations / Warnings")
    report_lines.append("")
    if warnings:
        for warning in warnings:
            report_lines.append(f"- {warning}")
    else:
        report_lines.append("- none")
    report_lines.append("")

    return "\n".join(report_lines)


def generate_run_summary_report_artifact(
    comparison_paths: list[Path],
    *,
    run_id: str,
    agent_metadata: dict[str, str],
    run_metadata: dict[str, Any] | None = None,
    output_path: Path,
    comparison_summary_output_path: Path | None = None,
    charts_dir: Path | None = None,
    showcase_scenario_id: str,
    overwrite: bool = False,
) -> tuple[Path, Path | None, list[Path], list[str]]:
    comparisons_by_scenario: dict[str, dict[str, Any]] = {}
    for comparison_path in comparison_paths:
        comparison = load_json(comparison_path)
        validated = validate_comparison_schema(comparison)
        scenario_id = _require_string_field(
            validated["comparison_metadata"],
            "scenario_id",
            "comparison_metadata",
        )
        comparisons_by_scenario[scenario_id] = validated

    comparison_summary = build_run_comparison_summary(
        comparisons_by_scenario,
        run_id=run_id,
        agent_metadata=agent_metadata,
        showcase_scenario_id=showcase_scenario_id,
        run_metadata=run_metadata,
    )

    resolved_charts_dir = (
        charts_dir if charts_dir is not None else output_path.parent / "charts"
    )

    warnings: list[str] = []
    chart_paths: list[Path] = []
    showcase_comparison = comparisons_by_scenario.get(showcase_scenario_id)
    if showcase_comparison is None:
        warnings.append(
            "showcase comparison artifact is unavailable; report generated without radar charts"
        )
    else:
        radar_names = validate_required_radar_template_set()
        if set(radar_names) != set(RUN_REPORT_SHOWCASE_RADAR_NAMES):
            raise ValueError(
                "run report radar names must match required showcase set; "
                f"expected {list(RUN_REPORT_SHOWCASE_RADAR_NAMES)}, got {radar_names}"
            )

        generated_chart_paths, chart_failures = generate_charts(
            showcase_comparison,
            radar_names=radar_names,
            charts_dir=resolved_charts_dir,
            overwrite=overwrite,
            output_name_template="radar_chart_{radar_name}.svg",
        )
        chart_paths.extend(generated_chart_paths)
        warnings.extend(
            [
                f"showcase radar rendering warning ({showcase_scenario_id}): {warning}"
                for warning in chart_failures
            ]
        )
        if not generated_chart_paths:
            warnings.append(
                f"no showcase radar SVGs were generated for {showcase_scenario_id}"
            )

    report = build_run_summary_report(
        comparison_summary,
        chart_paths=chart_paths,
        warnings=warnings,
    )
    save_report(output_path, report, overwrite=overwrite)

    written_summary_path: Path | None = None
    if comparison_summary_output_path is not None:
        save_json_artifact(
            comparison_summary_output_path,
            comparison_summary,
            overwrite=overwrite,
            artifact_label="comparison summary json",
        )
        written_summary_path = comparison_summary_output_path

    return output_path, written_summary_path, chart_paths, warnings


def _build_effect_summary(
    comparisons_by_scenario: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        "reuse_improvement": _build_effect_indicator(
            comparisons_by_scenario,
            source_metric="reuse_rate",
            delta_kind="increase",
        ),
        "rediscovery_reduction": _build_effect_indicator(
            comparisons_by_scenario,
            source_metric="rediscovery_rate",
            delta_kind="reduction",
        ),
    }


def _build_effect_indicator(
    comparisons_by_scenario: dict[str, dict[str, Any]],
    *,
    source_metric: str,
    delta_kind: str,
) -> dict[str, Any]:
    paired_values: list[tuple[float, float]] = []
    for comparison in comparisons_by_scenario.values():
        validated = validate_comparison_schema(comparison)
        metric_entry = _find_metric_entry(validated["metrics_comparison"], source_metric)
        if metric_entry is None:
            continue
        values = _require_dict_field(metric_entry, "values", f"metric '{source_metric}'")
        baseline_value = _require_optional_numeric_field(values, BASELINE, f"metric '{source_metric}' values")
        pr_light_brain_value = _require_optional_numeric_field(
            values,
            PR_LIGHT_BRAIN,
            f"metric '{source_metric}' values",
        )
        if baseline_value is None or pr_light_brain_value is None:
            continue
        paired_values.append((baseline_value, pr_light_brain_value))

    if not paired_values:
        return {
            "source_metric": source_metric,
            "baseline": None,
            "pr_light_brain": None,
            "delta_percent": None,
        }

    baseline_average = _average([item[0] for item in paired_values])
    pr_light_brain_average = _average([item[1] for item in paired_values])
    delta_percent = _compute_effect_delta_percent(
        baseline=baseline_average,
        pr_light_brain=pr_light_brain_average,
        delta_kind=delta_kind,
    )
    return {
        "source_metric": source_metric,
        "baseline": baseline_average,
        "pr_light_brain": pr_light_brain_average,
        "delta_percent": delta_percent,
    }


def _find_metric_entry(
    metrics_comparison: list[Any],
    metric_name: str,
) -> dict[str, Any] | None:
    for entry in metrics_comparison:
        if not isinstance(entry, dict):
            continue
        if entry.get("metric_name") == metric_name:
            return entry
    return None


def _compute_effect_delta_percent(
    *,
    baseline: float | None,
    pr_light_brain: float | None,
    delta_kind: str,
) -> float | None:
    if baseline is None or pr_light_brain is None:
        return None
    if baseline <= 0:
        return None
    if delta_kind == "increase":
        return round(((pr_light_brain - baseline) / baseline) * 100.0, 6)
    if delta_kind == "reduction":
        return round(((baseline - pr_light_brain) / baseline) * 100.0, 6)
    raise ValueError(f"unsupported effect delta_kind: {delta_kind}")


def _append_effect_summary_line(
    report_lines: list[str],
    *,
    label: str,
    effect_entry: dict[str, Any],
    positive_suffix: str,
    negative_suffix: str,
) -> None:
    baseline = _require_optional_numeric_field(effect_entry, "baseline", f"effect_summary.{label}")
    pr_light_brain = _require_optional_numeric_field(
        effect_entry,
        "pr_light_brain",
        f"effect_summary.{label}",
    )
    delta_percent = _require_optional_numeric_field(
        effect_entry,
        "delta_percent",
        f"effect_summary.{label}",
    )

    line = (
        f"- {label}: "
        f"baseline={_format_effect_value(baseline)}, "
        f"pr_light_brain={_format_effect_value(pr_light_brain)}"
    )
    if delta_percent is not None:
        suffix = positive_suffix if delta_percent >= 0 else negative_suffix
        if suffix:
            line += f", delta={abs(delta_percent):.1f}{suffix}"
        else:
            line += f", delta={delta_percent:+.1f}%"
    report_lines.append(line)


def _format_effect_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _require_optional_effect_entry(
    effect_summary: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    value = effect_summary.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"effect_summary field '{field_name}' must be an object")
    return value


def _require_dict_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> dict[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{label} field '{field_name}' must be an object")
    return value


def _validate_run_agent_metadata(agent_metadata: dict[str, str]) -> dict[str, str]:
    if not isinstance(agent_metadata, dict):
        raise ValueError("agent_metadata must be an object")

    return {
        "adapter": _require_string_field(agent_metadata, "adapter", "agent_metadata"),
        "full_agent_name": _require_string_field(
            agent_metadata,
            "full_agent_name",
            "agent_metadata",
        ),
        "agent_model": _require_string_field(
            agent_metadata,
            "agent_model",
            "agent_metadata",
        ),
    }


def _validate_optional_run_metadata(
    run_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    if run_metadata is None:
        return {}
    if not isinstance(run_metadata, dict):
        raise ValueError("run_metadata must be an object")

    validated: dict[str, Any] = {}

    string_fields = (
        "backend",
        "provider_profile",
        "quota_stop_reason",
    )
    for field_name in string_fields:
        value = run_metadata.get(field_name)
        if value is None:
            continue
        validated[field_name] = _require_string_field(run_metadata, field_name, "run_metadata")

    bool_fields = ("mode_to_key_mapping_enabled",)
    for field_name in bool_fields:
        value = run_metadata.get(field_name)
        if value is None:
            continue
        if not isinstance(value, bool):
            raise ValueError(f"run_metadata field '{field_name}' must be a boolean")
        validated[field_name] = value

    numeric_fields = (
        "inter_scenario_delay_seconds",
        "429_count_total",
    )
    for field_name in numeric_fields:
        value = run_metadata.get(field_name)
        if value is None:
            continue
        validated[field_name] = _require_numeric_field(run_metadata, field_name, "run_metadata")

    selected_scenario_subset = run_metadata.get("selected_scenario_subset")
    if selected_scenario_subset is not None:
        if not isinstance(selected_scenario_subset, list):
            raise ValueError("run_metadata field 'selected_scenario_subset' must be a list")
        normalized_subset: list[str] = []
        for item in selected_scenario_subset:
            if not isinstance(item, str):
                raise ValueError(
                    "run_metadata field 'selected_scenario_subset' must contain only strings"
                )
            cleaned = item.strip()
            if not cleaned:
                raise ValueError(
                    "run_metadata field 'selected_scenario_subset' must not contain empty strings"
                )
            normalized_subset.append(cleaned)
        validated["selected_scenario_subset"] = normalized_subset

    executed_modes = run_metadata.get("executed_modes")
    if executed_modes is not None:
        if not isinstance(executed_modes, list):
            raise ValueError("run_metadata field 'executed_modes' must be a list")
        normalized_modes: list[str] = []
        for item in executed_modes:
            if not isinstance(item, str):
                raise ValueError("run_metadata field 'executed_modes' must contain only strings")
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("run_metadata field 'executed_modes' must not contain empty strings")
            normalized_modes.append(cleaned)
        validated["executed_modes"] = normalized_modes

    diagnostic_modes = run_metadata.get("diagnostic_modes")
    if diagnostic_modes is not None:
        if not isinstance(diagnostic_modes, dict):
            raise ValueError("run_metadata field 'diagnostic_modes' must be an object")
        validated["diagnostic_modes"] = {
            "pr_ephemeral": _require_bool_field(
                diagnostic_modes,
                "pr_ephemeral",
                "run_metadata diagnostic_modes",
            )
        }

    return validated


def _require_list_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> list[Any]:
    value = data.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{label} field '{field_name}' must be a list")
    return value


def _require_string_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> str:
    value = data.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{label} field '{field_name}' must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} field '{field_name}' must not be empty")
    return cleaned


def _require_numeric_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> float:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} field '{field_name}' must be numeric")
    return float(value)


def _require_optional_numeric_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> float | None:
    value = data.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} field '{field_name}' must be numeric or null")
    return float(value)


def _require_bool_field(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> bool:
    value = data.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{label} field '{field_name}' must be a boolean")
    return value


def _build_metrics_index(comparison: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics_list = _require_list_field(
        comparison,
        "metrics_comparison",
        "comparison",
    )

    indexed: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(metrics_list, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"metrics entry #{index} must be an object")

        metric_name = entry.get("metric_name")
        if not isinstance(metric_name, str) or not metric_name.strip():
            raise ValueError(f"metrics entry #{index} has invalid metric_name")

        indexed[metric_name] = entry

    return indexed


def _require_metric_entry(
    metrics: dict[str, dict[str, Any]],
    metric_name: str,
) -> dict[str, Any]:
    if metric_name not in metrics:
        raise ValueError(f"required metric '{metric_name}' is missing from comparison")
    return metrics[metric_name]


def _validate_required_report_metrics(
    metrics: dict[str, dict[str, Any]],
) -> None:
    missing = [metric_name for metric_name in REQUIRED_REPORT_METRIC_NAMES if metric_name not in metrics]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            f"comparison artifact is missing required report metrics: {joined}"
        )


def _build_chart_result(
    metrics: dict[str, dict[str, Any]],
    mode: str,
) -> dict[str, Any] | None:
    flattened_metrics: dict[str, float] = {}

    for metric_name, entry in metrics.items():
        values = entry.get("values")
        if not isinstance(values, dict):
            raise ValueError(
                f"metrics_comparison entry '{metric_name}' is missing values object"
            )
        value = values.get(mode)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"metrics_comparison entry '{metric_name}' has invalid value for mode '{mode}'"
            )
        flattened_metrics[metric_name] = float(value)

    return {
        "metadata": {
            "mode": mode,
        },
        "metrics": flattened_metrics,
    }


def _chart_link_target(path: Path) -> str:
    if path.parent.name == "charts":
        return f"charts/{path.name}"
    return path.name


def _average(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty list of values")
    return sum(values) / len(values)


def main() -> None:
    args = parse_args()

    output_path, chart_paths, chart_failures = generate_summary_report_artifact(
        Path(args.comparison),
        radar_names=args.radars,
        output_path=Path(args.output),
        charts_dir=Path(args.charts_dir) if args.charts_dir is not None else None,
        overwrite=args.overwrite,
    )

    print(f"saved benchmark summary report: {output_path}")
    if chart_paths:
        print(f"generated radar charts: {len(chart_paths)}")
    if chart_failures:
        print("radar chart warnings:")
        for warning in chart_failures:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
