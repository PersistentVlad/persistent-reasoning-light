# OpenAI Codex Benchmark Adapter

This directory contains the **benchmark execution adapter** for OpenAI Codex in the Persistent Reasoning Light benchmark framework.

Its purpose is to run benchmark scenarios in controlled modes and emit reproducible benchmark artifacts.

---

# Purpose

This adapter exists for **benchmark execution only**.

It is responsible for running OpenAI Codex against benchmark scenarios in the following modes:

- `baseline`
- `pr_light`
- `pr_light_brain`

and producing benchmark outputs such as:

- raw logs
- event logs
- derived result artifacts

---

# Scope

This adapter may support:

- scenario loading
- benchmark mode switching
- prompt assembly for benchmark runs
- loading benchmark brains
- writing `.trace.log`
- writing `.events.jsonl`
- returning deterministic execution metadata for event-only result derivation

This adapter must remain focused on **controlled benchmark execution**.

---

# Architectural Position

Persistent Reasoning Light benchmark layers:

```text
benchmarks/            -> scenarios, results, reports
benchmark_adapters/    -> benchmark execution harness
reasoning_adapters/    -> reusable production adapter primitives
benchmark_execution/   -> provider-agnostic benchmark execution layer
reasoning-engine/      -> PR-Light runtime
```

This adapter belongs to:
benchmark_adapters/

---

# Benchmark Modes

##**baseline**
Runs OpenAI Codex without PR-Light reasoning context.

Purpose:
- measure unstabilized reasoning behavior
- establish comparison baseline

##**pr_light**
Runs OpenAI Codex with PR-Light runtime support and an empty benchmark reasoning brain.

Purpose:
- measure architecture effect of PR-Light
- isolate reasoning persistence mechanics

##**pr_light_brain**
Runs OpenAI Codex with PR-Light runtime support and a seeded benchmark reasoning brain.

Purpose:
- measure accumulated reasoning advantage
- demonstrate reuse of prior reasoning artifacts

---

# Expected Responsibilities

Typical responsibilities of this adapter may include:
- loading scenario markdown and JSON
- selecting benchmark mode
- loading benchmark brain paths
- attaching working context in PR modes
- capturing benchmark events
- emitting benchmark event logs for result derivation
- returning deterministic benchmark outputs

---

# Non-Goals

This adapter should not implement:
- compared summary generation
- chart rendering
- final report generation
- results comparison logic
- runtime cleanup orchestration
- 
Those responsibilities belong in:
benchmarks/tools/

---

# Dependency Rule

This adapter may depend on:
benchmark_adapters/common/
benchmark_execution/
reasoning_adapters/common/

It may also reuse carefully selected primitives from:
reasoning_adapters/

But it must not depend on benchmark reports or benchmark cleanup outputs.

The required dependency direction is:
```
benchmark_adapters -> reasoning_adapters
reasoning_adapters -X-> benchmark_adapters
```

---

# Suggested Files

A minimal OpenAI Codex benchmark adapter directory may contain:
```
openai_codex/
├── adapter.py
```

A fuller version may later include:

```
openai_codex/
├── adapter.py
├── benchmark_mode_bridge.py
├── benchmark_prompt_bridge.py
└── benchmark_run_controller.py
```

---

# Common Benchmark Utilities

This adapter may reuse shared benchmark helpers from:
benchmark_adapters/common/

Examples:
- benchmark_paths.py
- scenario_utils.py
- event_log_utils.py
- result_utils.py
- benchmark_prompt_utils.py

---

# Output Expectations

A benchmark run should typically produce:
```
results/<mode>/<scenario>.trace.log
results/<mode>/<scenario>.events.jsonl
results/<mode>/<scenario>.result.json
```

Adapter layer emits:
- `results/<mode>/<scenario>.trace.log`
- `results/<mode>/<scenario>.events.jsonl`

Event-derivation layer writes:
- `results/<mode>/<scenario>.result.json`

---

# Usage

This README is a template.

Replace this section later with:
- actual benchmark entrypoint usage
- supported arguments
- supported modes
- output locations
- benchmark-specific notes
- 
Example current runners:
- `python benchmarks/tools/run_baseline_benchmark.py`
- `python benchmarks/tools/run_pr_light_benchmark.py`
- `python benchmarks/tools/run_pr_light_brain_benchmark.py`

---

# Notes

This adapter should remain:
- deterministic
- mode-aware
- benchmark-focused
- isolated from production adapter orchestration

Its role is not to be a general OpenAI Codex integration layer.

Its role is to be a **controlled experimental harness** for evaluating PR-Light.

---
