# Radar Charts

This directory defines radar chart configurations for benchmark visualization.

Each radar chart groups related metrics into a single visual comparison.

Files are stored as:
radar_<radar_name>.json

---

## Purpose

Radar charts are used to:

- compare benchmark modes (baseline vs PR-Light)
- visualize trade-offs across dimensions
- provide quick high-level insight into system behavior

---

## Radar Definition Format

Example:

```
{
  "radar_name": "reasoning_stability",
  "metrics": [
    "replanning_events",
    "context_loss_events",
    "plan_retention_rate",
    "knowledge_retention_rate",
    "controlled_mutations_ratio"
  ]
}
```

---

# Fields

## radar_name
Unique identifier of the radar chart.

Used in:
- report generation
- SVG filenames

## metrics
List of metric names included in the chart.

Rules:
- must reference valid metric definitions
- order defines visual layout
- recommended: 4–6 metrics per chart

---

# Design Principles

## 1. Semantic grouping
Each radar chart should represent a meaningful dimension:

Examples:
- reasoning stability
- memory efficiency
- knowledge persistence
- operational cost

## 2. No duplication within a chart
Each metric should appear only once per radar.

## 3. Cross-radar reuse is allowed
A metric may appear in multiple radars if relevant.

## 4. Consistent scale
All metrics must be normalized before visualization.

Radar charts assume:
values are in comparable ranges (typically 0..1)

---

# Rendering Flow
Radar charts are generated using:
generate_quickchart_radar_svg.py

Pipeline:
```
<scenario_id>.result.json
↓
normalize_metrics.py
↓
radar config
↓
SVG chart
```

In full benchmark runs, showcase radar charts are generated only for:
`sc_99_killer_all_scenarios`

---

# Output
Generated files:
radar_chart_<radar_name>.svg

Stored in:
benchmarks/reports/<run_id>/charts/

---

# Example Radar Sets
radar_reasoning_stability.json
radar_reasoning_integrity.json
radar_context_efficiency.json
radar_operational_cost.json

---

# Best Practices
- keep charts readable (≤ 6 metrics)
- avoid mixing unrelated metrics
- prefer interpretable groupings over arbitrary sets
- document intent via radar_name

---

# Future Extensions
- weighted radar charts
- dynamic radar generation
- interactive visualization
- comparison overlays (baseline vs PR)

---
