# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

"""
Generate radar SVG charts from benchmark result JSON files using QuickChart.

This module:
- loads radar definitions and benchmark results
- normalizes metrics via normalization layer
- builds chart configuration
- fetches SVG from external QuickChart service

It does not:
- compute metrics
- compare results
- define benchmark truth

Note:
- This tool depends on external QuickChart API availability.
- It is part of the visualization/reporting layer only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from benchmark_adapters.common.result_utils import ensure_output_path_writable  # noqa: E402
from benchmarks.tools.normalize_metrics import (  # noqa: E402
    normalize_metrics_for_radar,
    validate_metric_definition_coverage,
    validate_normalization_config_coverage,
)


RADAR_CHARTS_DIR = TOOLS_DIR / "radar_charts"
METRICS_DIR = TOOLS_DIR / "metrics"
REQUIRED_RADAR_TEMPLATE_NAMES = (
    "reasoning_integrity",
    "reasoning_stability",
    "context_efficiency",
    "operational_cost",
)

MODE_LABELS = {
    "baseline": "Baseline",
    "pr_ephemeral": "PR-Ephemeral",
    "pr_light_brain": "PR-Light + Brain",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate radar SVG chart from benchmark result JSON files."
    )
    parser.add_argument(
        "--radar",
        required=True,
        help="Radar chart name without prefix/suffix, e.g. reasoning_stability",
    )
    parser.add_argument(
        "--baseline-result",
        required=True,
        help="Path to baseline <scenario_id>.result.json",
    )
    parser.add_argument(
        "--pr-ephemeral-result",
        default=None,
        help="Optional path to pr_ephemeral <scenario_id>.result.json",
    )
    parser.add_argument(
        "--pr-light-brain-result",
        required=True,
        help="Path to pr_light_brain <scenario_id>.result.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output SVG file",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing SVG output file.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional chart title override",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=720,
        help="Chart width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Chart height in pixels",
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


def load_radar_definition(
    radar_name: str,
    *,
    radar_charts_dir: Path = RADAR_CHARTS_DIR,
) -> dict[str, Any]:
    radar_path = radar_charts_dir / f"radar_{radar_name}.json"
    return load_json(radar_path)


def list_available_radar_template_names(
    *,
    radar_charts_dir: Path = RADAR_CHARTS_DIR,
) -> list[str]:
    names: list[str] = []

    for path in sorted(radar_charts_dir.glob("radar_*.json")):
        name = path.stem.removeprefix("radar_")
        if name:
            names.append(name)

    return names


def validate_required_radar_template_set(
    *,
    radar_charts_dir: Path = RADAR_CHARTS_DIR,
) -> list[str]:
    actual_names = set(list_available_radar_template_names(radar_charts_dir=radar_charts_dir))
    required_names = set(REQUIRED_RADAR_TEMPLATE_NAMES)

    if actual_names != required_names:
        raise ValueError(
            "radar template set must exactly match required names; "
            f"expected {sorted(required_names)}, got {sorted(actual_names)}"
        )

    return list(REQUIRED_RADAR_TEMPLATE_NAMES)


def validate_radar_definition(
    radar_definition: dict[str, Any],
    *,
    metrics_dir: Path = METRICS_DIR,
) -> dict[str, Any]:
    radar_name = str(radar_definition.get("radar_name", "unknown"))
    metric_names = _require_radar_field(
        radar_definition,
        "metrics",
        radar_name,
    )
    if not isinstance(metric_names, list) or not metric_names:
        raise ValueError("radar definition 'metrics' must be a non-empty list")

    for metric in metric_names:
        if not isinstance(metric, str):
            raise ValueError("radar definition 'metrics' must contain only strings")

    validate_metric_definition_coverage(metric_names, metrics_dir=metrics_dir)
    validate_normalization_config_coverage(metric_names)
    return radar_definition


def flatten_result_metrics(result: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}

    for section_name, section_value in result.items():
        if section_name == "metadata":
            continue
        if not isinstance(section_value, dict):
            continue

        for metric_name, value in section_value.items():
            if isinstance(value, bool):
                metrics[metric_name] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                metrics[metric_name] = float(value)

    return metrics


def build_chart_config(
    radar_definition: dict[str, Any],
    *,
    baseline_results: dict[str, Any],
    pr_ephemeral_results: dict[str, Any] | None,
    pr_light_brain_results: dict[str, Any],
    title: str,
    metrics_dir: Path = METRICS_DIR,
) -> dict[str, Any]:
    validated_radar_definition = validate_radar_definition(
        radar_definition,
        metrics_dir=metrics_dir,
    )
    radar_name = str(validated_radar_definition.get("radar_name", "unknown"))
    metric_names = validated_radar_definition["metrics"]

    baseline_metrics = flatten_result_metrics(baseline_results)
    pr_ephemeral_metrics = (
        flatten_result_metrics(pr_ephemeral_results)
        if pr_ephemeral_results is not None
        else None
    )
    pr_light_brain_metrics = flatten_result_metrics(pr_light_brain_results)

    dataset_by_mode = normalize_metrics_for_radar(
        baseline_metrics=baseline_metrics,
        pr_ephemeral_metrics=pr_ephemeral_metrics,
        pr_light_brain_metrics=pr_light_brain_metrics,
        metric_names=metric_names,
        metrics_dir=metrics_dir,
    )

    _validate_dataset_completeness(dataset_by_mode, metric_names)

    datasets: list[dict[str, Any]] = []
    for mode, values in dataset_by_mode.items():
        if mode not in MODE_LABELS:
            raise ValueError(f"unsupported mode for chart dataset: {mode}")

        datasets.append(
            {
                "label": MODE_LABELS[mode],
                "data": [values[metric] for metric in metric_names],
                "fill": True,
            }
        )

    return {
        "type": "radar",
        "data": {
            "labels": metric_names,
            "datasets": datasets,
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": title,
                },
                "legend": {
                    "display": True,
                    "position": "top",
                },
            },
            "responsive": True,
            "maintainAspectRatio": False,
            "scales": {
                "r": {
                    "min": 0,
                    "max": 1,
                    "ticks": {
                        "stepSize": 0.2,
                    },
                }
            },
        },
    }


def fetch_quickchart_svg(chart_config: dict[str, Any], width: int, height: int) -> str:
    """
    Fetch radar chart SVG from QuickChart API.

    This function performs an external HTTP request and may fail due to:
    - network issues
    - service availability
    - invalid chart configuration
    """
    if not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")
    if not isinstance(height, int) or height <= 0:
        raise ValueError("height must be a positive integer")

    chart_json = json.dumps(chart_config, separators=(",", ":"), ensure_ascii=False)
    query = urllib.parse.urlencode(
        {
            "c": chart_json,
            "format": "svg",
            "width": str(width),
            "height": str(height),
        }
    )
    url = f"https://quickchart.io/chart?{query}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "persistent-reasoning-light/benchmark-radar"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")

    trimmed = body.strip()
    svg_index = trimmed.find("<svg")
    if svg_index < 0:
        preview = trimmed[:100]
        raise ValueError(
            f"quickchart response is not valid SVG (preview: {preview})"
        )

    return trimmed[svg_index:]


def generate_radar_svg(
    radar_name: str,
    *,
    baseline_results: dict[str, Any],
    pr_ephemeral_results: dict[str, Any] | None,
    pr_light_brain_results: dict[str, Any],
    title: str | None = None,
    width: int = 720,
    height: int = 720,
    radar_charts_dir: Path = RADAR_CHARTS_DIR,
    metrics_dir: Path = METRICS_DIR,
) -> str:
    radar_definition = load_radar_definition(
        radar_name,
        radar_charts_dir=radar_charts_dir,
    )

    radar_name_value = _require_radar_field(
        radar_definition,
        "radar_name",
        radar_name,
    )
    if not isinstance(radar_name_value, str) or not radar_name_value.strip():
        raise ValueError("radar definition 'radar_name' must be a non-empty string")

    chart_title = title or f"PR-Light Radar — {radar_name_value}"

    chart_config = build_chart_config(
        radar_definition,
        baseline_results=baseline_results,
        pr_ephemeral_results=pr_ephemeral_results,
        pr_light_brain_results=pr_light_brain_results,
        title=chart_title,
        metrics_dir=metrics_dir,
    )

    return fetch_quickchart_svg(chart_config, width, height)


def save_svg(path: Path, svg_text: str, *, overwrite: bool = False) -> None:
    if not isinstance(svg_text, str):
        raise ValueError("svg_text must be a string")

    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_writable(
        path,
        overwrite=overwrite,
        artifact_label="radar svg",
    )
    path.write_text(svg_text, encoding="utf-8")


def _require_radar_field(
    radar_definition: dict[str, Any],
    field_name: str,
    radar_name: str,
) -> Any:
    if field_name not in radar_definition:
        raise ValueError(
            f"radar definition '{radar_name}' is missing field: {field_name}"
        )
    return radar_definition[field_name]


def _validate_dataset_completeness(
    dataset_by_mode: dict[str, dict[str, float]],
    metric_names: list[str],
) -> None:
    required_modes = {"baseline", "pr_light_brain"}

    missing_modes = required_modes - set(dataset_by_mode.keys())
    if missing_modes:
        raise ValueError(f"missing dataset(s) for modes: {sorted(missing_modes)}")

    for mode, values in dataset_by_mode.items():
        for metric in metric_names:
            if metric not in values:
                raise ValueError(
                    f"dataset for mode '{mode}' is missing metric: {metric}"
                )


def main() -> None:
    args = parse_args()

    baseline_results = load_json(Path(args.baseline_result))
    pr_ephemeral_results = (
        load_json(Path(args.pr_ephemeral_result))
        if args.pr_ephemeral_result is not None
        else None
    )
    pr_light_brain_results = load_json(Path(args.pr_light_brain_result))

    svg = generate_radar_svg(
        args.radar,
        baseline_results=baseline_results,
        pr_ephemeral_results=pr_ephemeral_results,
        pr_light_brain_results=pr_light_brain_results,
        title=args.title,
        width=args.width,
        height=args.height,
    )

    output_path = Path(args.output)
    save_svg(output_path, svg, overwrite=args.overwrite)

    print(f"saved radar svg: {output_path}")


if __name__ == "__main__":
    main()
