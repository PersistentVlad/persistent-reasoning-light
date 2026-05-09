# Benchmark Metrics

This directory defines all benchmark metrics used in Persistent Reasoning evaluation.

Metrics are defined as independent, composable units and stored as JSON files:

metric_<metric_name>.json

---

## Purpose

The goal of this system is to:

- make metrics explicit and inspectable
- avoid hardcoded metric definitions in code
- enable flexible composition into radar charts
- support future metric evolution without rewriting adapters

---

## Metric Definition Format

Each metric is defined as a JSON object:

```json
{
  "metric_name": "reasoning_drift_rate",
  "metric_type": "ratio",
  "metric_description": "Frequency of reasoning drift events during execution",
  "metric_formula": "drift_events / total_reasoning_steps"
}
```

---

# Fields

## metric_name
Unique identifier of the metric.

Used in:
- <scenario_id>.result.json
- radar definitions
- comparison layer

## metric_type
Defines how the metric behaves and how it should be normalized.

Supported types:
- ratio → value between 0 and 1 (higher or lower depends on metric semantics)
- count → integer event counts
- latency_ms → time-based metrics
- efficiency → normalized performance metrics
- score → composite or derived score

## metric_description
Short human-readable explanation of what the metric represents.

Used in:
- reports
- documentation
- debugging

## metric_formula
Describes how the metric should be computed from event logs.

Important:
- this is a declarative description, not executable code
- actual computation happens in the analysis layer

---

# Design Principles

## 1. Metrics are independent
Each metric:
- does not depend on other metrics
- is computed from raw execution data (events)

## 2. Metrics are derived, not stored

Metrics should be:
- computed from <scenario_id>.events.jsonl
- not treated as primary data

## 3. No hidden logic

All metrics must:
- be explicitly defined here
- not exist only inside Python code

## 4. Naming consistency

Metric names must:
- be lowercase
- use snake_case
- be stable across versions

---

# Example Metrics
metric_reasoning_drift_rate.json
metric_token_efficiency.json
metric_execution_time_ms.json
metric_structural_integrity_score.json

---

# Relationship to Results

Metrics appear in:
<scenario_id>.result.json

But:
- <scenario_id>.result.json is a derived artifact
- metrics originate from event logs

---

# Future Extensions

This system allows:
- metric versioning
- dynamic metric loading
- custom metric sets per benchmark suite
- automatic validation of metric definitions

---
