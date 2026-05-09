# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Compare benchmark result artifacts across baseline, PR-Ephemeral, and PR-Light + Brain modes.

This tool operates only on canonical *.result.json artifacts.
It must not depend on raw trace logs, event logs, or adapter-specific hidden logic.

Metric comparison uses metric definition files from tools/metrics/.
Radar snapshots use radar definition files from tools/radar_charts/.
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


from benchmark_adapters.common.benchmark_modes import (  # noqa: E402
    BASELINE,
    PR_EPHEMERAL,
    PR_LIGHT_BRAIN,
)
from benchmark_adapters.common.benchmark_paths import (  # noqa: E402
    get_benchmark_paths,
    result_json_path,
)
from benchmark_adapters.common.result_utils import (  # noqa: E402
    ensure_output_path_writable,
    load_result_json,
    validate_adapter_name,
)
from benchmarks.tools.normalize_metrics import (  # noqa: E402
    normalize_metrics_for_radar,
    validate_metric_definition_coverage,
)


METRICS_DIR = TOOLS_DIR / "metrics"
RADAR_CHARTS_DIR = TOOLS_DIR / "radar_charts"

REQUIRED_COMPARISON_TOP_LEVEL_FIELDS = (
    "comparison_metadata",
    "summary_scores",
    "metrics_comparison",
)
REQUIRED_SUMMARY_SCORE_FIELDS = (
    "baseline_pr_stability_score",
    "pr_ephemeral_pr_stability_score",
    "pr_light_brain_pr_stability_score",
)
REQUIRED_COMPARISON_MODES = (BASELINE, PR_LIGHT_BRAIN)
OPTIONAL_COMPARISON_MODES = (PR_EPHEMERAL,)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare benchmark result artifacts across modes."
    )
    parser.add_argument(
        "--scenario-id",
        required=True,
        help="Scenario id to compare across baseline / pr_ephemeral / pr_light_brain.",
    )
    parser.add_argument(
        "--adapter-name",
        default=None,
        help="Optional adapter name override. If omitted, all inputs must share the same adapter.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output comparison JSON file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing comparison output file.",
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


def load_metric_definition(metric_name: str) -> dict[str, Any]:
    path = METRICS_DIR / f"metric_{metric_name}.json"
    return load_json(path)


def has_metric_definition(metric_name: str) -> bool:
    return (METRICS_DIR / f"metric_{metric_name}.json").is_file()


def flatten_numeric_metrics(
    result: dict[str, Any],
) -> dict[str, float]:
    metrics: dict[str, float] = {}

    for section_name, section_value in result.items():
        if section_name == "metadata":
            continue
        if not isinstance(section_value, dict):
            continue

        for field_name, field_value in section_value.items():
            if isinstance(field_value, bool):
                continue
            if isinstance(field_value, (int, float)):
                metrics[field_name] = float(field_value)

    return metrics


def discover_metric_names(*results: dict[str, Any]) -> list[str]:
    """
    Discover numeric metric names present in result artifacts and require explicit
    metric definition coverage for all of them.
    """
    discovered: set[str] = set()

    for result in results:
        discovered.update(flatten_numeric_metrics(result).keys())

    metric_names = sorted(discovered)
    validate_metric_definition_coverage(metric_names, metrics_dir=METRICS_DIR)
    return metric_names


def build_metric_comparison_entry(
    metric_name: str,
    baseline_metrics: dict[str, float],
    pr_ephemeral_metrics: dict[str, float] | None,
    pr_light_brain_metrics: dict[str, float],
) -> dict[str, Any]:
    baseline_value = _require_metric_value(baseline_metrics, metric_name, "baseline")
    pr_ephemeral_value = (
        _require_metric_value(pr_ephemeral_metrics, metric_name, "pr_ephemeral")
        if pr_ephemeral_metrics is not None
        else None
    )
    pr_light_brain_value = _require_metric_value(
        pr_light_brain_metrics,
        metric_name,
        "pr_light_brain",
    )

    metric_definition = load_metric_definition(metric_name)

    return {
        "metric_name": metric_name,
        "metric_type": metric_definition.get("metric_type", "unknown"),
        "metric_description": metric_definition.get("metric_description", ""),
        "metric_formula": metric_definition.get("metric_formula", ""),
        "values": {
            BASELINE: baseline_value,
            PR_EPHEMERAL: pr_ephemeral_value,
            PR_LIGHT_BRAIN: pr_light_brain_value,
        },
        "deltas": {
            "pr_ephemeral_vs_baseline": (
                pr_ephemeral_value - baseline_value
                if pr_ephemeral_value is not None
                else None
            ),
            "pr_light_brain_vs_baseline": pr_light_brain_value - baseline_value,
            "pr_light_brain_vs_pr_ephemeral": (
                pr_light_brain_value - pr_ephemeral_value
                if pr_ephemeral_value is not None
                else None
            ),
        },
    }


def validate_comparison_inputs(
    baseline_results: dict[str, Any],
    pr_ephemeral_results: dict[str, Any] | None,
    pr_light_brain_results: dict[str, Any],
    adapter_name: str | None = None,
) -> dict[str, str]:
    baseline_metadata = _require_metadata(baseline_results, "baseline")
    pr_light_brain_metadata = _require_metadata(pr_light_brain_results, "pr_light_brain")
    pr_ephemeral_metadata = (
        _require_metadata(pr_ephemeral_results, "pr_ephemeral")
        if pr_ephemeral_results is not None
        else None
    )

    baseline_scenario_id = _require_string_field(
        baseline_metadata,
        "scenario_id",
        "baseline metadata",
    )
    pr_light_brain_scenario_id = _require_string_field(
        pr_light_brain_metadata,
        "scenario_id",
        "pr_light_brain metadata",
    )

    scenario_ids = {
        baseline_scenario_id,
        pr_light_brain_scenario_id,
    }
    if pr_ephemeral_metadata is not None:
        scenario_ids.add(
            _require_string_field(
                pr_ephemeral_metadata,
                "scenario_id",
                "pr_ephemeral metadata",
            )
        )
    if len(scenario_ids) != 1:
        raise ValueError("comparison inputs must share the same scenario_id")

    baseline_mode = _require_string_field(
        baseline_metadata,
        "mode",
        "baseline metadata",
    )
    pr_light_brain_mode = _require_string_field(
        pr_light_brain_metadata,
        "mode",
        "pr_light_brain metadata",
    )
    pr_ephemeral_mode = (
        _require_string_field(
            pr_ephemeral_metadata,
            "mode",
            "pr_ephemeral metadata",
        )
        if pr_ephemeral_metadata is not None
        else None
    )

    if baseline_mode != BASELINE:
        raise ValueError(f"baseline result has invalid mode: {baseline_mode}")
    if pr_ephemeral_mode is not None and pr_ephemeral_mode != PR_EPHEMERAL:
        raise ValueError(f"pr_ephemeral result has invalid mode: {pr_ephemeral_mode}")
    if pr_light_brain_mode != PR_LIGHT_BRAIN:
        raise ValueError(f"pr_light_brain result has invalid mode: {pr_light_brain_mode}")

    if adapter_name is not None:
        validated_adapter = _normalize_optional_adapter_name(adapter_name)
    else:
        baseline_adapter = _require_string_field(
            baseline_metadata,
            "adapter",
            "baseline metadata",
        )
        pr_light_brain_adapter = _require_string_field(
            pr_light_brain_metadata,
            "adapter",
            "pr_light_brain metadata",
        )
        pr_ephemeral_adapter = (
            _require_string_field(
                pr_ephemeral_metadata,
                "adapter",
                "pr_ephemeral metadata",
            )
            if pr_ephemeral_metadata is not None
            else None
        )

        adapters = {
            baseline_adapter,
            pr_light_brain_adapter,
        }
        if pr_ephemeral_adapter is not None:
            adapters.add(pr_ephemeral_adapter)
        if len(adapters) != 1:
            raise ValueError("comparison inputs must share the same adapter")
        validated_adapter = baseline_adapter

    return {
        "scenario_id": baseline_scenario_id,
        "adapter": validated_adapter,
        "baseline_mode": baseline_mode,
        "pr_ephemeral_mode": pr_ephemeral_mode,
        "pr_light_brain_mode": pr_light_brain_mode,
    }


def build_comparison(
    baseline_results: dict[str, Any],
    pr_ephemeral_results: dict[str, Any] | None,
    pr_light_brain_results: dict[str, Any],
    *,
    adapter_name: str | None = None,
) -> dict[str, Any]:
    comparison_metadata = validate_comparison_inputs(
        baseline_results=baseline_results,
        pr_ephemeral_results=pr_ephemeral_results,
        pr_light_brain_results=pr_light_brain_results,
        adapter_name=adapter_name,
    )

    metric_names = discover_metric_names(
        baseline_results,
        pr_light_brain_results,
        *( [pr_ephemeral_results] if pr_ephemeral_results is not None else [] ),
    )

    baseline_metrics = flatten_numeric_metrics(baseline_results)
    pr_ephemeral_metrics = (
        flatten_numeric_metrics(pr_ephemeral_results)
        if pr_ephemeral_results is not None
        else None
    )
    pr_light_brain_metrics = flatten_numeric_metrics(pr_light_brain_results)

    metric_entries = [
        build_metric_comparison_entry(
            metric_name,
            baseline_metrics,
            pr_ephemeral_metrics,
            pr_light_brain_metrics,
        )
        for metric_name in metric_names
    ]

    normalized = normalize_metrics_for_radar(
        baseline_metrics=baseline_metrics,
        pr_ephemeral_metrics=pr_ephemeral_metrics,
        pr_light_brain_metrics=pr_light_brain_metrics,
        metric_names=metric_names,
        metrics_dir=METRICS_DIR,
    )

    comparison = {
        "comparison_metadata": comparison_metadata,
        "summary_scores": {
            "baseline_pr_stability_score": compute_pr_stability_score(
                normalized.get(BASELINE, {})
            ),
            "pr_ephemeral_pr_stability_score": (
                compute_pr_stability_score(normalized.get(PR_EPHEMERAL, {}))
                if PR_EPHEMERAL in normalized
                else None
            ),
            "pr_light_brain_pr_stability_score": compute_pr_stability_score(
                normalized.get(PR_LIGHT_BRAIN, {})
            ),
            "metric_count": len(metric_entries),
        },
        "metrics_comparison": metric_entries,
    }

    return validate_comparison_schema(comparison)


def compute_pr_stability_score(results: dict[str, Any]) -> float:
    """
    Compute a PoC heuristic PR stability score from selected normalized metrics.

    This helper uses a fixed weighted combination of normalized benchmark metrics.
    It is intended for comparative visualization and summary reporting only.
    """
    weighted_metrics = {
        "retrieval_precision": 0.35,
        "reuse_rate": 0.30,
        "context_utilization_rate": 0.20,
        "knowledge_retention_rate": 0.07,
        "structural_integrity_score": 0.05,
        "controlled_mutations_ratio": 0.03,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for metric_name, weight in weighted_metrics.items():
        value = results.get(metric_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        weighted_sum += float(value) * weight
        total_weight += weight

    if total_weight <= 0:
        return 0.0

    return round(weighted_sum / total_weight, 6)


def save_comparison(
    path: Path,
    comparison: dict[str, Any],
    *,
    overwrite: bool = False,
) -> None:
    validate_comparison_schema(comparison)
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label="comparison json",
    )
    with path.open("w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def build_result_paths(
    scenario_id: str,
) -> dict[str, Path]:
    paths = get_benchmark_paths(REPO_ROOT)
    return {
        BASELINE: result_json_path(paths, BASELINE, scenario_id),
        PR_EPHEMERAL: result_json_path(paths, PR_EPHEMERAL, scenario_id),
        PR_LIGHT_BRAIN: result_json_path(paths, PR_LIGHT_BRAIN, scenario_id),
    }


def generate_comparison_artifact(
    scenario_id: str,
    *,
    output_path: Path,
    adapter_name: str | None = None,
    repo_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    if repo_root is not None:
        globals()["REPO_ROOT"] = repo_root.resolve()

    result_paths = build_result_paths(scenario_id)

    baseline_results = load_result_json(result_paths[BASELINE])
    pr_ephemeral_results = (
        load_result_json(result_paths[PR_EPHEMERAL])
        if result_paths[PR_EPHEMERAL].exists()
        else None
    )
    pr_light_brain_results = load_result_json(result_paths[PR_LIGHT_BRAIN])

    comparison = build_comparison(
        baseline_results,
        pr_ephemeral_results,
        pr_light_brain_results,
        adapter_name=adapter_name,
    )

    save_comparison(output_path, comparison, overwrite=overwrite)
    return output_path


def _require_metadata(result: dict[str, Any], label: str) -> dict[str, Any]:
    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{label} result must contain metadata object")
    return metadata


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


def _require_metric_value(
    metrics: dict[str, float],
    metric_name: str,
    label: str,
) -> float:
    if metric_name not in metrics:
        raise ValueError(f"missing metric '{metric_name}' in {label} result")
    return metrics[metric_name]


def _normalize_optional_adapter_name(adapter_name: str) -> str:
    return validate_adapter_name(adapter_name)


def validate_comparison_schema(comparison: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(comparison, dict):
        raise ValueError("comparison must be an object")

    missing = [
        field for field in REQUIRED_COMPARISON_TOP_LEVEL_FIELDS if field not in comparison
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"comparison is missing required fields: {joined}")

    comparison_metadata = validate_comparison_metadata(
        comparison["comparison_metadata"]
    )
    summary_scores = validate_summary_scores(comparison["summary_scores"])
    metrics_comparison = validate_metrics_comparison(
        comparison["metrics_comparison"]
    )

    return {
        "comparison_metadata": comparison_metadata,
        "summary_scores": summary_scores,
        "metrics_comparison": metrics_comparison,
    }


def validate_comparison_metadata(comparison_metadata: dict[str, Any]) -> dict[str, str]:
    if not isinstance(comparison_metadata, dict):
        raise ValueError("comparison_metadata must be an object")

    validated = {
        "scenario_id": _require_string_field(
            comparison_metadata,
            "scenario_id",
            "comparison_metadata",
        ),
        "adapter": _require_string_field(
            comparison_metadata,
            "adapter",
            "comparison_metadata",
        ),
        "baseline_mode": _require_string_field(
            comparison_metadata,
            "baseline_mode",
            "comparison_metadata",
        ),
        "pr_light_brain_mode": _require_string_field(
            comparison_metadata,
            "pr_light_brain_mode",
            "comparison_metadata",
        ),
    }
    pr_ephemeral_mode = comparison_metadata.get("pr_ephemeral_mode")
    if pr_ephemeral_mode is not None and not isinstance(pr_ephemeral_mode, str):
        raise ValueError("comparison_metadata field 'pr_ephemeral_mode' must be a string or null")
    validated["pr_ephemeral_mode"] = (
        pr_ephemeral_mode.strip() if isinstance(pr_ephemeral_mode, str) else None
    )

    if validated["baseline_mode"] != BASELINE:
        raise ValueError(
            f"comparison_metadata field 'baseline_mode' must be '{BASELINE}'"
        )
    if validated["pr_ephemeral_mode"] is not None and validated["pr_ephemeral_mode"] != PR_EPHEMERAL:
        raise ValueError(
            f"comparison_metadata field 'pr_ephemeral_mode' must be '{PR_EPHEMERAL}' when present"
        )
    if validated["pr_light_brain_mode"] != PR_LIGHT_BRAIN:
        raise ValueError(
            f"comparison_metadata field 'pr_light_brain_mode' must be '{PR_LIGHT_BRAIN}'"
        )

    return validated


def validate_summary_scores(summary_scores: dict[str, Any]) -> dict[str, float | int]:
    if not isinstance(summary_scores, dict):
        raise ValueError("summary_scores must be an object")

    validated: dict[str, float | int | None] = {
        "baseline_pr_stability_score": _require_numeric_field(
            summary_scores,
            "baseline_pr_stability_score",
            "summary_scores",
        ),
        "pr_ephemeral_pr_stability_score": _require_optional_numeric_field(
            summary_scores,
            "pr_ephemeral_pr_stability_score",
            "summary_scores",
        ),
        "pr_light_brain_pr_stability_score": _require_numeric_field(
            summary_scores,
            "pr_light_brain_pr_stability_score",
            "summary_scores",
        ),
    }

    metric_count = summary_scores.get("metric_count")
    if not isinstance(metric_count, int) or metric_count < 0:
        raise ValueError("summary_scores field 'metric_count' must be a non-negative integer")
    validated["metric_count"] = metric_count

    return validated


def validate_metrics_comparison(metrics_comparison: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(metrics_comparison, list):
        raise ValueError("metrics_comparison must be a list")

    validated_entries: list[dict[str, Any]] = []
    seen_metric_names: set[str] = set()

    for index, entry in enumerate(metrics_comparison, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"metrics_comparison entry #{index} must be an object")

        metric_name = _require_string_field(
            entry,
            "metric_name",
            f"metrics_comparison entry #{index}",
        )
        if metric_name in seen_metric_names:
            raise ValueError(f"duplicate metric_name in metrics_comparison: {metric_name}")
        seen_metric_names.add(metric_name)

        values = _require_mode_numeric_mapping(
            entry,
            "values",
            f"metrics_comparison entry '{metric_name}'",
        )
        deltas = _require_delta_mapping(
            entry,
            f"metrics_comparison entry '{metric_name}'",
        )

        validated_entries.append(
            {
                "metric_name": metric_name,
                "metric_type": str(entry.get("metric_type", "unknown")),
                "metric_description": str(entry.get("metric_description", "")),
                "metric_formula": str(entry.get("metric_formula", "")),
                "values": values,
                "deltas": deltas,
            }
        )

    return validated_entries


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


def _require_mode_numeric_mapping(
    data: dict[str, Any],
    field_name: str,
    label: str,
) -> dict[str, float]:
    value = data.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{label} field '{field_name}' must be an object")

    validated: dict[str, float] = {}
    for mode in REQUIRED_COMPARISON_MODES:
        validated[mode] = _require_numeric_field(value, mode, f"{label} field '{field_name}'")
    for mode in OPTIONAL_COMPARISON_MODES:
        validated[mode] = _require_optional_numeric_field(
            value,
            mode,
            f"{label} field '{field_name}'",
        )

    return validated


def _require_delta_mapping(
    data: dict[str, Any],
    label: str,
) -> dict[str, float]:
    deltas = data.get("deltas")
    if not isinstance(deltas, dict):
        raise ValueError(f"{label} field 'deltas' must be an object")

    required_delta_fields = (
        "pr_ephemeral_vs_baseline",
        "pr_light_brain_vs_baseline",
    )
    validated = {
        field: _require_optional_numeric_field(deltas, field, f"{label} field 'deltas'")
        if field == "pr_ephemeral_vs_baseline"
        else _require_numeric_field(deltas, field, f"{label} field 'deltas'")
        for field in required_delta_fields
    }
    validated["pr_light_brain_vs_pr_ephemeral"] = _require_optional_numeric_field(
        deltas,
        "pr_light_brain_vs_pr_ephemeral",
        f"{label} field 'deltas'",
    )
    return validated


def main(repo_root: Path | None = None) -> None:
    args = parse_args()

    output_path = generate_comparison_artifact(
        args.scenario_id,
        output_path=Path(args.output),
        adapter_name=args.adapter_name,
        repo_root=repo_root,
        overwrite=args.overwrite,
    )

    print(f"saved benchmark comparison json: {output_path}")


if __name__ == "__main__":
    main()
