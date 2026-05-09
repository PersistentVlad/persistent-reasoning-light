# Benchmark Adapters
## Persistent Reasoning Light — Benchmark Execution Layer

This directory contains benchmark adapters for Persistent Reasoning Light.

Benchmark adapters are responsible for executing controlled benchmark scenarios
and producing structured outputs for comparison across different execution modes.

---

# Purpose

The benchmark adapter layer exists to:

- evaluate reasoning behavior
- measure reasoning stability
- compare execution modes
- produce reproducible benchmark outputs

This layer is not part of the runtime reasoning system.

It is a controlled experimental harness.

---

# Architectural Role

Benchmark adapters sit outside the runtime system.

```text
benchmarks/scenarios/
↓
benchmark_adapters/
↓
(reasoning_adapters/)
↓
reasoning-engine/
↓
benchmark reasoning brain (isolated)
```

They interact with the runtime system but do not modify its architecture.

---

# Key Principles

Benchmark adapters must remain:
- deterministic
- reproducible
- isolated
- comparable across runs
- 
They must not:
- modify canonical reasoning-brain
- bypass runtime proposal flow
- introduce hidden context
- embed benchmark logic into runtime adapters

---

# Execution Modes

All benchmark adapters must support three modes:
baseline
pr_light
pr_light_brain

## baseline
- no PR-Light context
- no reasoning brain

## pr_light
- PR-Light runtime enabled
- empty reasoning brain
- 
## pr_light_brain
- PR-Light runtime enabled
- pre-seeded reasoning brain
- 
These modes must be strictly separated.

---

# Directory Structure
```
benchmark_adapters/
├── README.md
├── benchmark_contract.md
├── common/
│   ├── benchmark_paths.py
│   ├── scenario_utils.py
│   ├── event_log_utils.py
│   ├── result_utils.py
│   └── benchmark_prompt_utils.py
└── openai_codex/
    └── adapter.py
```

---

# OpenAI Execution Contract

See full execution contract:
```
benchmarks/contracts/openai_execution_contract.md
```

---

# Common Utilities

The common/ directory contains shared benchmark logic.

These utilities may:
- load scenarios
- manage benchmark paths
- log events
- write `.trace.log`
- build benchmark prompts

They must not:
- mutate storage
- interact with Git
- bypass runtime logic

---

# Adapter Responsibilities

Each benchmark adapter is responsible for:
1. loading scenarios
2. selecting execution mode
3. running scenario steps deterministically
4. collecting execution signals
5. writing logs and event files

Derived `*.result.json` artifacts are written by:
`benchmarks/tools/compute_metrics_from_events.py`

Adapters must not:
- perform result comparison
- generate summary reports
- clean up runtime state

These responsibilities belong to:
benchmarks/tools/

---

# Output Structure

Benchmark results must be written to:
```
benchmarks/results/<mode>/
```

Each scenario produces:
```
<scenario>.trace.log
<scenario>.events.jsonl
<scenario>.result.json
```

Adapter layer emits:
- `<scenario>.trace.log`
- `<scenario>.events.jsonl`

Event-derivation layer writes:
- `<scenario>.result.json`

Outputs must be:
- structured
- deterministic
- comparable across modes

---

# Reasoning Brain Isolation

Benchmark adapters must use isolated reasoning brain directories:
```
benchmarks-empty-reasoning-brain/
benchmarks-seeded-reasoning-brain/
benchmarks-runtime-reasoning-brain/
```

They must not interact with:
reasoning-brain/

---

# Dependency Rules

Allowed:
```
benchmark_adapters → benchmark_execution
benchmark_adapters → reasoning_adapters
benchmark_adapters → reasoning-engine
```

Forbidden:
```
reasoning_adapters → benchmark_adapters
```

Benchmark adapters may reuse:
reasoning_adapters/common/

They must not reuse:
- full adapter orchestration
- production mutation logic

---

# What This Layer Is Not

Benchmark adapters must not become:
- runtime adapters
- reasoning engines
- storage managers
- governance layers
- 
They exist only to measure behavior.

---

# Contract

All benchmark adapters must follow:
benchmark_adapters/benchmark_contract.md

This document defines:
- execution rules
- isolation requirements
- dependency constraints
- output expectations

---

# Final Principle

Benchmark adapters exist to answer one question:
How does reasoning behave under controlled conditions?

They must measure reasoning — not influence it.

---
