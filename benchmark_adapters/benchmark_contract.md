# Benchmark Contract
## Persistent Reasoning Light — Benchmark Adapter Contract

This document defines the shared contract for benchmark adapters in the `benchmark_adapters/` layer.

It applies to all benchmark-specific adapters, including:

- Codex benchmark adapter
- Claude benchmark adapter
- OpenClaw benchmark adapter
- zeroClaw benchmark adapter

The purpose of this contract is to ensure that benchmark execution remains:

- deterministic
- reproducible
- comparable across modes
- architecturally isolated from runtime adapters

---

# Purpose

A benchmark adapter is responsible for executing predefined benchmark scenarios
under controlled conditions and producing structured outputs for comparison.

The benchmark adapter acts as an execution harness between:

- benchmark scenarios
- reasoning adapters (optional dependency)
- reasoning-engine runtime
- benchmark-specific reasoning brain copies

---

# Architectural Position

The benchmark adapter sits outside the runtime adapter layer.

```text
Benchmark Scenarios
↓
Benchmark Adapter
↓
(Optionally) Reasoning Adapter
↓
Reasoning Engine
↓
Benchmark Reasoning Brain (isolated)
```

The benchmark adapter is not:
- a runtime adapter
- a reasoning engine
- a reasoning brain
- a governance layer

---

# Core Role

A benchmark adapter is responsible for:
1. loading benchmark scenarios
2. selecting execution mode
3. executing agent interactions deterministically
4. capturing execution signals
5. writing structured benchmark outputs

The benchmark adapter must remain a controlled execution harness.

---

# Benchmark Path Conventions

All benchmark-related paths must follow a consistent and explicit structure.

Base directories:
```
benchmarks/
benchmarks-empty-reasoning-brain/
benchmarks-seeded-reasoning-brain/
benchmarks-runtime-reasoning-brain/
```

Benchmark artifact output paths:
```
benchmarks/results/<mode>/<scenario_id>.trace.log
benchmarks/results/<mode>/<scenario_id>.events.jsonl
benchmarks/results/<mode>/<scenario_id>.result.json
```

Rules:
- paths must not be dynamically inferred
- paths must not depend on adapter-specific logic
- all path resolution must be centralized in benchmark_adapters/common/benchmark_paths.py
- adapters must not hardcode path strings inline

---

# Supported Execution Modes

All benchmark adapters must support the following modes:
baseline
pr_light
pr_light_brain

Mode semantics:

## baseline
- no PR-Light context
- no reasoning brain usage

Baseline benchmark policy regarding context visibility is an explicit benchmark design choice and must not be inferred from helper implementation alone.

## pr_light
- PR-Light runtime enabled
- empty benchmark reasoning brain

## pr_light_brain
- PR-Light runtime enabled
- seeded benchmark reasoning brain

Mode handling must be explicit and deterministic.

---

# Required Responsibilities
## 1. Scenario Loading

The adapter must load scenario definitions from:
benchmarks/scenarios/

Scenarios may include:
- markdown instructions
- structured JSON steps

Adapters must not modify scenario definitions at runtime.

## 2. Mode Selection

The adapter must explicitly select and validate execution mode.

Mode must not be inferred implicitly.

Invalid modes must raise explicit errors.

## 3. Execution Control

The adapter must execute scenarios step-by-step in a deterministic manner.

Execution must not depend on:
- hidden state
- previous runs
- external uncontrolled inputs

Each scenario execution must be reproducible.

## 4. Context Handling

In PR modes:
- adapter may load working context via reasoning-engine
- adapter must not reconstruct context independently

In baseline mode:
- adapter must not inject PR context

Context handling must respect mode boundaries.

## 5. Event Logging

The adapter must produce structured event logs.
Recommended format:
```
.events.jsonl
```

Each event must be:
- append-only
- timestamped or step-indexed
- structured

Example events:
```
{"type": "step_start", "step": 1}
{"type": "context_loaded", "tokens": 1200}
{"type": "artifact_suggested", "id": "decision_x"}
{"type": "drift_detected"}
```

Event logs must be deterministic and comparable.

Event logs must be isolated per:
- benchmark run
- execution mode
- scenario

Adapters must not:
- append to logs from previous runs
- reuse event logs across runs
- mix events from different modes

Each benchmark execution must produce a fresh, isolated event log set.

## 6. Result Writing

The adapter must write outputs to:
```
benchmarks/results/<mode>/
```

Each scenario must produce:

adapter writes:
```
<scenario>.events.jsonl
<scenario>.trace.log
```

compute_metrics_from_events.py
writes:
```
<scenario>.result.json
```

Result JSON must follow a consistent schema.

Adapters must not mix outputs across modes.

## 7. Isolation of Reasoning Brain

Each benchmark run must use isolated reasoning brain directories:
```
benchmarks-empty-reasoning-brain/
benchmarks-seeded-reasoning-brain/
benchmarks-runtime-reasoning-brain/
```

The adapter must not:
- mutate canonical reasoning-brain/
- reuse runtime brain across runs without reset

---

# Forbidden Responsibilities

Benchmark adapters must not:
- write to canonical reasoning-brain/
- bypass runtime proposal flow
- commit to Git
- perform canonical artifact acceptance
- modify artifact schema
- embed benchmark logic into runtime adapters
- introduce agent-specific schema changes

Benchmark adapters are execution tools, not governance components.

---

# Dependency Rule
Allowed:
```
benchmark_adapters → reasoning_adapters
benchmark_adapters → reasoning-engine (read-only or controlled usage)
```

Forbidden:
```
reasoning_adapters → benchmark_adapters
```

Benchmark adapters may reuse:
- reasoning_adapters/common/
- selected reasoning adapter primitives

They must not reuse:
- full runtime adapter orchestration
- production mutation flows

They may reuse strictly bounded primitives from:
reasoning_adapters/common/

Benchmark adapters may also call minimal adapter-level entry functions,
but must not reuse or embed full runtime adapter orchestration.

Forbidden reuse includes:
- full adapter execution loops
- proposal orchestration logic
- canonical mutation flows
- implicit runtime state handling

---

# Shared Utilities Boundary

The benchmark_adapters/common/ directory contains shared benchmark utilities.

These utilities may:
- load scenarios
- manage paths
- build benchmark prompts
- write `.trace.log`
- validate result schema used by the event-derivation layer

They must:
- remain deterministic
- remain side-effect controlled

They must not:
- perform canonical storage mutation
- interact with Git
- bypass benchmark isolation rules

---

# Determinism Rule

Benchmark execution must be deterministic.

Adapters must avoid:
- random ordering
- hidden retries
- non-deterministic prompt construction
- implicit fallback logic

Given the same:
- scenario
- mode
- reasoning brain state

The output must be reproducible.

---

# Reproducibility Rule

Benchmark runs must be resettable.

After each full benchmark run:
- runtime reasoning brain must be cleared
- logs must be isolated per run
- seeded brain must remain unchanged unless explicitly updated

---

# Error Handling Rule

Benchmark adapters must fail explicitly when:
- scenario is invalid
- mode is unsupported
- required files are missing
- runtime cannot be initialized

Adapters must not silently skip or repair failures.

---

# Expected Interface Shape

This contract does not require a strict Python API.
However, adapters should conceptually support:
```
load_scenario(...)
select_mode(...)
run_scenario(...)
log_event(...)
write_trace_log(...)
```

These responsibilities must remain explicit and separable.

---

# Runtime vs Benchmark Separation

Runtime adapters and benchmark adapters are separate systems.

Rule:
```
benchmark_adapters may depend on reasoning_adapters
runtime adapters must not depend on benchmark_adapters
```

Benchmark adapters must not introduce:
- evaluation logic into runtime adapters
- benchmark-specific prompt hacks into production adapters

This separation is mandatory.

---

# Context Integrity Rule

Benchmark adapters must not inflate context artificially.

They must not:
- inject hidden context
- preload additional artifacts beyond mode definition
- modify working context outside reasoning-engine

This ensures fair comparison across modes.

---

# Output Consistency Rule

All outputs must be:
- structured
- machine-readable
- comparable across runs

Adapters must not:
- change output schema dynamically
- omit fields conditionally
- include non-deterministic debug content

---

# Final Principle

A benchmark adapter must remain a deterministic, isolated execution harness for evaluating Persistent Reasoning Light behavior.

It must not become:
- a runtime adapter
- a reasoning engine
- a governance layer
- a storage manager
- a hidden optimization layer

The benchmark layer exists to measure reasoning behavior, not to modify it.

---
