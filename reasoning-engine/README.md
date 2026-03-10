# Persistent Reasoning Light — Reasoning Engine

## Overview

The **Reasoning Engine** is the core runtime component of the **Persistent Reasoning Light (PR-Light)** framework.

Its purpose is to provide a **minimal structured reasoning layer** that allows agents and automation systems to maintain reasoning continuity across long tasks.

Unlike traditional AI agents that rely on ephemeral prompts and temporary context, the reasoning engine enables systems to persist important reasoning elements as structured artifacts.

These artifacts form a lightweight reasoning substrate that supports:

- task continuity
- decision persistence
- constraint enforcement
- reusable procedures
- open reasoning questions

The engine is intentionally designed to be **small, transparent, and inspectable**.

---

# Role in the Persistent Reasoning Architecture

The Persistent Reasoning architecture separates reasoning into two layers.

## Full Persistent Reasoning

A governance-heavy system designed for long-lived reasoning repositories and strict reasoning lineage.

Features include:

- proposal → validation → commit governance
- invariant preservation
- explicit recovery semantics
- strict reasoning lineage

## Persistent Reasoning Light (PR-Light)

A simplified operational profile designed for:

- AI agents
- coding assistants
- automation systems
- workflow orchestrators

PR-Light focuses on **practical reasoning continuity** rather than full governance.

The reasoning engine implements this lightweight profile.

---

# Core Concept

Instead of storing raw conversation history or large unstructured memory logs, the reasoning engine stores **structured reasoning artifacts**.

Each artifact represents a durable reasoning element.

Typical artifacts include:

- TaskCard
- DecisionCard
- ConstraintCard
- ProcedureCard
- IssueCard

Together these artifacts form a **structured reasoning brain**.

---

# Example Reasoning Flow

Typical reasoning cycle inside the engine:

```
task
 ↓
agent reasoning
 ↓
artifact suggestion
 ↓
artifact filter
 ↓
draft artifact
 ↓
artifact persistence
 ↓
context update
```

Only durable reasoning outcomes are persisted.

Temporary reasoning traces are intentionally discarded.

---

# Repository Structure

The reasoning engine works together with a reasoning brain repository.

Example layout:

```
persistent-reasoning-light/

reasoning-engine/
    core/
    adapters/
    validation/
    storage/
    view_builder/

reasoning-brain/
    tasks/
    decisions/
    constraints/
    procedures/
    issues/
```

The **reasoning brain** stores persistent artifacts.

The **reasoning engine** manages how artifacts are created, validated, and retrieved.

---

# Artifact Model

Artifacts represent the minimal set of durable reasoning structures.

Example artifact:

```json
{
  "id": "decision_use_git_storage",
  "type": "DecisionCard",
  "statement": "Use Git repository as canonical artifact storage",
  "reason": [
    "Git provides transparent history",
    "Git enables easy forking and experimentation"
  ],
  "status": "accepted"
}
```

Artifacts are intentionally small.

Rule:

```
One artifact = one durable reasoning element
```

Artifacts must not contain:

- long essays
- raw LLM reasoning traces
- conversational logs

---

# Working Context

Agents should not load the entire reasoning brain.

Instead the engine constructs a **working context projection**.

Example:

```
views/working_context.json
```

```json
{
  "active_task": "task_git_artifact_loader",
  "decisions": [
    "decision_use_git_storage"
  ],
  "constraints": [
    "constraint_no_artifact_overwrite"
  ],
  "open_issues": [
    "issue_relation_storage"
  ]
}
```

This small context allows efficient reasoning.

---

# Artifact Suggestion Filter

Agents may propose new artifacts during reasoning.

To prevent the brain from filling with temporary thoughts, the engine includes an **Artifact Suggestion Filter**.

The filter verifies:

- artifact type is valid
- artifact contains meaningful content
- artifact is not an obvious duplicate
- artifact does not look like a temporary reasoning trace

The filter acts as a **proposal quality gate**, not as a governance system.

---

# Git-Based Persistence

The reasoning engine is designed to work with **Git repositories** as the persistence substrate.

Git provides:

- artifact history
- reasoning evolution visibility
- distributed replication
- zero infrastructure cost

Git commit history acts as a lightweight reasoning lineage.

---

# Integration Targets

The reasoning engine is designed to integrate with agent systems such as:

- coding agents
- automation agents
- research assistants
- workflow orchestrators

Adapters may be implemented for systems like:

- OpenClaw
- Claude Code
- Codex
- custom agent frameworks

---

# Reasoning Escalation

PR-Light supports optional **reasoning escalation**.

When a task exceeds local reasoning capability, the engine may create a **DeepQueryCard** and send it to an external reasoning service.

External responses return as **draft artifacts**, which must be explicitly accepted before entering the canonical brain.

This preserves artifact integrity.

---

# Design Principles

The reasoning engine follows several strict principles.

### Simplicity

The system should remain understandable in minutes.

### Small Artifacts

Artifacts must remain concise.

### Inspectability

The reasoning brain should remain human-readable.

### Deterministic Behavior

Core logic should remain simple and predictable.

### Agent Compatibility

The system must integrate easily with existing agent environments.

---

# Intended Scope

The reasoning engine is intentionally minimal.

It does **not implement the full Persistent Reasoning architecture**.

Instead it demonstrates the practical benefits of structured reasoning continuity for agents.

This minimal prototype forms the foundation for experimentation and ecosystem growth.

---

# Long-Term Direction

PR-Light systems may eventually evolve toward richer infrastructures including:

- reasoning bundles
- reasoning repositories
- distributed reasoning nodes
- reasoning operating systems
- reasoning ecosystems

However, the reasoning engine focuses on **a minimal working reasoning brain for agents**.

---

# Summary

The Persistent Reasoning Light engine provides a minimal structured reasoning layer that allows agents to preserve decisions, constraints, and procedures across long tasks.

By storing small reasoning artifacts instead of raw memory logs, the system creates a lightweight but powerful reasoning substrate that improves task continuity and reasoning stability.