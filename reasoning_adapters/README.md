# Reasoning Adapters
## Persistent Reasoning Light — Runtime Integration Layer

This directory contains runtime adapters that connect external agent systems
to the Persistent Reasoning Light engine.

Adapters act as **thin, deterministic bridges** between agents and the reasoning system.

---

# Purpose

The adapter layer exists to:

- connect agents to the reasoning engine
- translate working context into agent-usable form
- extract reasoning outcomes from agent output
- submit artifact suggestions into the approved proposal flow

Adapters enable integration without modifying the core reasoning architecture.

---

# Architectural Role

Adapters sit between agent systems and the reasoning engine.

```text
Agent System
↓
Reasoning Adapter
↓
Reasoning Engine
↓
Reasoning Brain
```

The adapter is not:
- a reasoning engine
- a reasoning brain
- a benchmark harness
- a governance layer
- 
It is a translation layer.

---

# Why Adapters Exist

Different agent systems have different:
- execution models
- context formats
- tool interfaces
- reasoning behaviors

Adapters allow Persistent Reasoning Light to integrate with all of them without leaking agent-specific logic into the core system.

---

# Core Responsibilities

A runtime adapter is responsible for four things:
## 1. Context Retrieval

Load prepared working context from the reasoning engine.

Adapters must use:
reasoning-brain/views/working_context.json

Adapters must not load the full reasoning brain unless explicitly required.

## 2. Context Translation

Transform working context into agent-compatible format.

Examples:
- prompt sections
- structured payloads
- compact references

Adapters must preserve context minimalism.

## 3. Artifact Suggestion Preparation

Extract candidate reasoning outcomes from agent output.

Examples:
- TaskCard
- DecisionCard
- ConstraintCard
- ProcedureCard
- IssueCard
- 
Adapters may normalize suggestions to match the approved schema.

## 4. Proposal Handoff

Submit artifact suggestions into the approved proposal flow:
```
runtime/inbox
↓
artifact_filter
↓
runtime/drafts
↓
canonical brain
```

Adapters submit into this flow.

They must not bypass it.

Adapters do not control canonical acceptance.

---

# Design Principles

Adapters must follow these principles.

## Isolation
Agent-specific logic must not leak into the reasoning engine.

## Minimalism
Adapters must remain thin and explicit.

## Non-invasive
Adapters must not mutate canonical artifacts directly.

## Determinism
Adapter behavior must be predictable and reproducible.

## Transparency
Adapter behavior should be observable and inspectable.

---

# Forbidden Responsibilities

Adapters must not:
- write directly to canonical artifact directories
- bypass artifact_filter
- commit artifacts to Git
- mutate canonical artifacts in place
- rebuild reasoning views
- ryedefine artifact schema
- introduce extra artifact fields
- embed benchmark logic
- perform evaluation or scoring
- 
Adapters are integration layers, not governance layers.

---

# Shared Utilities

Shared helper code lives in:
reasoning_adapters/common/

These utilities may:
- format context
- assemble prompts
- shape artifact payloads

They must:
- remain stateless
- remain agent-agnostic
- avoid side effects

They must not:
- write to storage
- interact with Git
- implement adapter orchestration
- contain benchmark logic

---

# Adapter Independence
Adapters must not depend on each other.

Forbidden:
```
codex → claude
openclaw → codex
```

All shared logic must go through:
- reasoning_adapters/common/
- reasoning-engine
- adapter_contract.md

---

# Runtime vs Benchmark Separation

Runtime adapters and benchmark adapters are separate layers.

Rule:
```
benchmark_adapters may depend on reasoning_adapters
reasoning_adapters must not depend on benchmark_adapters
```

Runtime adapters must not include:
- benchmark scenarios
- benchmark metrics
- evaluation logic
- benchmark-specific prompt hacks

---

# Directory Structure
```
reasoning_adapters/
├── README.md
├── adapter_contract.md
├── common/
│   ├── context_utils.py
│   ├── prompt_utils.py
│   └── artifact_utils.py
├── codex/
│   └── adapter.py
├── claude/
│   └── adapter.py
├── openclaw/
│   └── adapter.py
└── zeroclaw/
    └── adapter.py
```

---

# Adapter Contract

All adapters must follow:
reasoning_adapters/adapter_contract.md

This contract defines:
- allowed responsibilities
- forbidden behaviors
- dependency rules
- schema constraints

---

# Example Execution Flow
```
agent starts task
↓
adapter loads working context
↓
adapter builds agent input
↓
agent executes step
↓
adapter extracts reasoning outcome
↓
adapter submits artifact suggestion
↓
runtime proposal flow processes suggestion
```

---

# What This Layer Is Not

Adapters must not become:
- reasoning engines
- storage layers
- governance systems
- benchmark harnesses
- hidden orchestration layers

---

# Final Principle

A reasoning adapter must remain a thin, deterministic bridge between agents and the Persistent Reasoning Light runtime.

Its role is to connect reasoning — not to redefine it.

---
