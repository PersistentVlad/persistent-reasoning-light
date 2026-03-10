# Codex Rules

## Purpose

This document defines rules for AI coding tools (such as Codex or Claude Code) working inside this repository.

The goal is to ensure that automatically generated code remains aligned with the architecture of Persistent Reasoning Light.

AI agents must follow these rules when generating or modifying code.

---

## Rule 1 — Preserve Architectural Simplicity

The reasoning engine must remain small and understandable.

AI agents must avoid introducing:

- unnecessary frameworks
- deep abstraction layers
- complex dependency graphs
- large infrastructure components

The goal is a minimal reasoning engine prototype.

---

## Rule 2 — Do Not Expand Artifact Types

The supported artifact types are fixed:

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

AI agents must not introduce additional artifact types without explicit architectural approval.

---

## Rule 3 — Keep Artifacts Small

Artifacts must remain concise.

AI agents must not generate artifacts containing:

- long reasoning explanations
- conversation history
- full reasoning chains
- large text blocks

Artifacts represent durable reasoning elements only.

---

## Rule 4 — Do Not Modify Git History

The reasoning system relies on Git as a reasoning lineage layer.

AI agents must never attempt to:

- rewrite Git history
- squash reasoning commits automatically
- alter artifact evolution silently

Artifact history must remain transparent.

---

## Rule 5 — Do Not Bypass the Artifact Filter

All artifact suggestions must pass through the artifact filter.

AI agents must not:

- write artifacts directly to storage
- bypass validation
- bypass the artifact suggestion pipeline

The correct pipeline is:

```
artifact suggestion
↓
artifact_filter
↓
storage
```

---

## Rule 6 — Preserve Repository Structure

AI agents must respect the repository layout.

Key directories include:

```
reasoning-engine
reasoning-brain
reasoning-adapters
```

Core runtime modules must remain inside:

```
reasoning-engine/core
```

---

## Rule 7 — Avoid Overengineering

The project intentionally prioritizes clarity over complexity.

AI agents should prefer:

- simple functions
- readable modules
- minimal dependencies
- explicit logic

Complex frameworks should not be introduced.

---

## Rule 8 — Respect Adapter Boundaries

Adapters must remain isolated from the reasoning engine.

AI agents must not introduce agent-specific logic into the core engine modules.

Agent integrations belong in:

```
reasoning-adapters/
```

---

## Rule 9 — Prefer Deterministic Behavior

The reasoning engine must behave predictably.

AI agents should avoid:

- hidden heuristics
- non-deterministic artifact transformations
- unpredictable reasoning logic

Core engine behavior should remain deterministic.

---

## Summary

When generating code for this repository, AI agents must prioritize:

- architectural clarity
- minimal design
- artifact discipline
- deterministic reasoning behavior

Persistent Reasoning Light is intentionally small and must remain easy to inspect and understand.