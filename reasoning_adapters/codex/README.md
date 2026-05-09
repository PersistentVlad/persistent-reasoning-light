# Codex Adapter

This directory contains the **Codex integration adapter** for Persistent Reasoning Light.

The purpose of this adapter is to connect Codex-style execution workflows to the PR-Light runtime without embedding benchmark-specific logic.

---

# Purpose

The Codex adapter is intended for **real adapter integration**, not for benchmark orchestration.

It provides a thin bridge between:

- Codex-style task execution
- PR-Light working context
- artifact suggestion flow
- runtime reasoning persistence

---

# Scope

This adapter may support:

- loading PR-Light working context
- attaching reasoning context to Codex-facing prompts
- resolving artifact references
- submitting artifact suggestions into runtime proposal flow

This adapter must remain focused on **production-style integration behavior**.

It must not contain:

- benchmark scenario execution logic
- benchmark result generation
- benchmark comparison logic
- benchmark cleanup logic

Those responsibilities belong in:

```text
benchmark_adapters/
```

---

# Architectural Position

Persistent Reasoning Light repository layers:

reasoning-engine/      -> PR-Light runtime
reasoning-brain/       -> canonical and runtime reasoning storage
reasoning_adapters/    -> real agent integrations
benchmark_adapters/    -> benchmark-specific execution harness

This adapter belongs to:
reasoning_adapters/

---

# Expected Responsibilities

Typical responsibilities of this adapter may include:
- loading working_context.json
- preparing Codex-compatible prompt context
- exposing artifact suggestion hooks
- bridging Codex task flow to PR-Light runtime interfaces

---

# Non-Goals

This adapter should not implement:
- benchmark orchestration
- benchmark scenario loading
- event-log generation for benchmark metrics
- compared summary reports
- benchmark chart generation
- runtime benchmark cleanup

---

# Common Dependencies

This adapter may reuse shared production utilities from:
reasoning_adapters/common/

Examples:
- context_utils.py
- prompt_utils.py
- artifact_utils.py
- 
This adapter must not depend on:
benchmark_adapters/

Dependency direction must remain:
```
benchmark_adapters -> reasoning_adapters
reasoning_adapters -X-> benchmark_adapters
```

---

# Suggested Files

A minimal Codex adapter directory may contain:
```
codex/
├── adapter.py
```

A more complete version may later include:
```
codex/
├── adapter.py
├── context_bridge.py
├── proposal_bridge.py
└── prompt_builder.py
```

---

# Usage

This README is a template.
Replace this section later with:

- actual entrypoint information
- supported modes
- required inputs
- output behavior
- integration notes
- 
Current adapter file:
`reasoning_adapters/codex/adapter.py`

---

# Notes

This adapter should remain:
- thin
- explicit
- predictable
- isolated from benchmark-only behavior
- 
The goal is to keep Codex integration clean and reusable across real PR-Light workflows.

---
