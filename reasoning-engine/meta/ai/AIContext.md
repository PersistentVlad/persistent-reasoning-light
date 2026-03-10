# AIContext.md
## Persistent Reasoning Light — Reasoning Engine Context

This document provides context and constraints for AI coding agents working on the Persistent Reasoning Light (PR-Light) repository.

The goal of this file is to ensure that AI-generated code remains aligned with the architectural intent of the project.

AI tools should treat this document as authoritative architectural guidance.

---

# Project Goal

The repository implements a minimal reasoning engine that provides structured reasoning persistence for agents.

The system allows agents to maintain continuity across long tasks by storing structured reasoning artifacts.

The system intentionally avoids heavy frameworks and complex infrastructure.

The objective is to demonstrate a small, inspectable reasoning brain for agents.

---

# Agent-First Adoption Strategy

Persistent Reasoning Light follows an **agent-first adoption model**.

The system is designed primarily for **AI agents**, not for human users.

Agents should be able to:

- discover the capability
- install it
- use it automatically
- benefit from improved reasoning stability

Human developers typically discover the system later by observing improvements in agent behavior.

Example adoption flow:

```
agent detects reasoning instability
↓
agent installs structured memory capability
↓
agent begins storing reasoning artifacts
↓
task stability improves
↓
human notices artifact files in repository
```

This design principle influences the entire architecture:

- artifacts must be simple
- integration must be lightweight
- installation must be transparent
- reasoning benefits must be observable

---

# Core Idea

Instead of storing raw conversation logs or embeddings, the system stores **small structured reasoning artifacts**.

Artifacts represent durable reasoning elements.

Examples:

- tasks
- decisions
- constraints
- procedures
- unresolved issues

Artifacts must remain concise and atomic.

Rule:

```
One artifact = one durable reasoning element
```

---

# Artifact Types

The reasoning engine supports a minimal artifact vocabulary.

Allowed artifact types:

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

These types must be treated as runtime enums.

No additional artifact types should be introduced without architectural discussion.

---

# Artifact Design Principles

Artifacts must follow strict rules.

1. Artifacts must remain small.

2. Artifacts represent structured knowledge, not conversation history.

3. Artifacts must not contain long reasoning traces.

4. Artifacts should store decisions and constraints, not temporary thoughts.

5. Artifacts should remain readable and diff-friendly in Git.

---

# Domain Field

Artifacts may include domains metadata.

Example:

```
"domains": ["coding", "architecture"]
```

Rules:

- domains must be lowercase snake_case strings
- domains are metadata only
- domains must not influence Git lineage
- if domains are absent:

```
domains = ["general"]
```

The first element represents the primary domain.

---

# Reasoning Brain

The reasoning brain is stored as a repository structure.

Example:

```
reasoning-brain/

tasks/
decisions/
constraints/
procedures/
issues/
```

Each artifact is stored as a JSON file.

Artifacts must never be rewritten in place.

Reasoning evolution should occur through Git commits.

---

# Working Context

Agents should not load the entire reasoning brain.

Instead the engine constructs a **working context projection**.

Example file:

```
views/working_context.json
```

Typical fields:

- active_task
- decisions
- constraints
- open_issues

Working context must remain small.

---

# Artifact Suggestion Flow

Agents may propose artifacts during reasoning.

Typical pipeline:

```
agent output
↓
artifact suggestion
↓
artifact_filter
↓
draft artifact
↓
storage
```

Important rule:

The artifact filter is a **proposal quality gate**.

It does not:

- commit artifacts
- modify storage
- mutate the brain

It only returns a verdict.

---

# Artifact Suggestion Filter

The filter ensures only durable reasoning elements are stored.

Heuristics must remain simple and deterministic.

Example checks:

- valid artifact type
- meaningful content field
- not temporary reasoning
- not trivial duplicate

The filter must avoid complex semantic reasoning.

---

# Storage Layer

The system is designed for **Git-based persistence**.

Git provides:

- artifact history
- reasoning evolution transparency
- distributed replication

Git commit history acts as lightweight reasoning lineage.

The engine should avoid introducing complex databases.

---

# Scope of This Repository

This repository implements **Persistent Reasoning Light**, not full Persistent Reasoning.

Excluded features include:

- heavy governance protocols
- distributed reasoning networks
- reasoning marketplaces
- full reasoning operating systems

The focus is a **minimal reasoning brain prototype for agents**.

---

# Integration Philosophy

The reasoning engine is designed to integrate with agent systems.

Examples:

- coding agents
- automation agents
- workflow agents
- research assistants

Adapters should be implemented at the edges.

The reasoning core must remain stable and small.

---

# Architectural Constraints

AI agents modifying this repository must follow these rules:

1. Keep the system minimal.

2. Avoid unnecessary frameworks.

3. Avoid deep abstraction layers.

4. Prefer readability over complexity.

5. Do not extend artifact schemas casually.

6. Keep the reasoning engine understandable in minutes.

---

# Long-Term Direction (Informational)

Persistent Reasoning may evolve toward larger infrastructures including:

- reasoning bundles
- reasoning repositories
- reasoning operating systems
- distributed reasoning networks

However, this repository focuses strictly on a **minimal reasoning engine prototype**.

---

End of AIContext