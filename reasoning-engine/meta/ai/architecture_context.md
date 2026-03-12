# architecture_context.md
## Persistent Reasoning Light — Architecture Context

This document explains the architectural structure of the Persistent Reasoning Light (PR-Light) prototype.

It provides guidance for AI agents generating or modifying code inside this repository.

This file complements `AIContext.md` and focuses specifically on **system architecture and component responsibilities**.

---

# Architectural Purpose

The PR-Light repository implements a **minimal reasoning engine** that allows agents to persist structured reasoning artifacts across execution cycles.

The architecture intentionally separates three layers:

```
Agent Layer
↓
Reasoning Engine
↓
Reasoning Brain Storage
```

The reasoning engine acts as the **bridge between agents and the persistent reasoning brain**.

---

# High-Level System Architecture

```
AI Agent
   ↓
Reasoning Adapter
   ↓
Reasoning Engine
   ↓
Reasoning Brain Repository (Git)
```

Each layer has a specific responsibility.

---

# Component Overview

The reasoning engine is composed of a small set of modules.

Core modules include:

```
reasoning-engine/core/artifact_cards.py
reasoning-engine/core/artifact_filter.py
reasoning-engine/core/storage.py
reasoning-engine/core/relations.py
reasoning-engine/core/validation.py
reasoning-engine/core/view_builder.py
reasoning-engine/core/git_adapter.py
reasoning-engine/core/context_loader.py
```

Each module should remain small and focused.

---

# Artifact Cards Module

File:

```
reasoning-engine/core/artifact_cards.py
```

Purpose:

Defines the structure of reasoning artifacts.

This module defines the supported artifact types:

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

These are lightweight structured objects representing durable reasoning elements.

The module should include:

- artifact schemas
- constructors
- serialization helpers

---

# Artifact Filter Module

File:

```
reasoning-engine/core/artifact_filter.py
```

Purpose:

Acts as a **quality gate for agent-proposed artifacts**.

Pipeline position:

```
agent output
↓
artifact suggestion
↓
artifact_filter
↓
draft artifact
```

Important constraints:

The filter must NOT:

- persist artifacts
- modify storage
- commit to Git

The filter only returns a verdict:

```
ACCEPT
REJECT
REWRITE
POSSIBLE_DUPLICATE
```

Heuristics must remain simple.

---

# Storage Module

File:

```
reasoning-engine/core/storage.py
```

Purpose:

Handles reading and writing artifact files inside the reasoning brain repository.

Responsibilities:

- loading artifacts
- saving draft artifacts
- listing artifacts by type

Artifacts are stored as JSON files.

Example directory structure:

```
reasoning-brain/

tasks/
decisions/
constraints/
procedures/
issues/
```

The storage module must remain simple and file-based.

No database should be introduced.

---

# Relations Module

File:

```
reasoning-engine/core/relations.py
```

Purpose:

Manages relationships between artifacts.

Relations are stored separately from artifact files.

Example:

```
relations/
depends_on.jsonl
blocks.jsonl
```

Each line represents a graph edge.

Example:

```
task_010 -> decision_002
```

This structure enables graph-like reasoning while keeping artifacts small.

---

# Validation Module

File:

```
reasoning-engine/core/validation.py
```

Purpose:

Performs lightweight schema validation for artifacts.

Examples:

- valid artifact type
- required fields present
- correct field types

Validation must remain deterministic.

The system must avoid complex semantic reasoning.

---

# View Builder Module

File:

```
reasoning-engine/core/view_builder.py
```

Purpose:

Constructs derived views of the reasoning brain.

The most important view is:

```
reasoning-brain/views/working_context.json
```

The working context contains only the information required by the agent.

Typical fields:

```
active_task
decisions
constraints
open_issues
```

This keeps reasoning retrieval efficient.

---

# Git Adapter

File:

```
reasoning-engine/core/git_adapter.py
```

Purpose:

Handles interaction with Git.

Examples:

- commit artifacts
- read repository state
- create branches if needed

Git acts as the **reasoning lineage layer**.

The engine must avoid complex Git workflows.

Only basic operations should be supported.

---

# Context Loader

File:

```
reasoning-engine/core/context_loader.py
```

Purpose:

Loads the working context for the agent.

This module prepares the compact reasoning context used during execution.

Example flow:

```
load active task
↓
load referenced decisions
↓
load relevant constraints
↓
build working context
```

The output is a small JSON structure.

---

# Artifact Lifecycle

Artifacts typically follow this lifecycle:

```
agent produces reasoning
↓
artifact suggestion generated
↓
artifact_filter evaluates suggestion
↓
artifact saved as draft
↓
optional human or system review
↓
artifact committed to brain
```

This preserves reasoning discipline without heavy governance.

---

# Brain Repository Separation

The reasoning brain may live:

- inside the same repository
- in a separate repository
- on a remote storage system

The reasoning engine must therefore treat the brain location as configurable.

Example configuration:

```
REASONING_BRAIN_PATH
```

---

# Architectural Principles

The reasoning engine must follow these design principles.

Minimalism  
The system should remain small and understandable.

Transparency  
Artifacts must be readable and inspectable.

Determinism  
Core logic must remain predictable.

Extensibility  
Adapters may be added without modifying the core.

---

# Non-Goals

This prototype intentionally does NOT implement:

- full Persistent Reasoning governance
- distributed reasoning clusters
- blockchain lineage anchoring
- reasoning marketplaces
- large knowledge graphs

Those features belong to the **full PR architecture**.

---

# Relationship to Full Persistent Reasoning

Persistent Reasoning Light is a simplified operational profile.

Conceptual progression:

```
PR Light
↓
Agent PR
↓
Full Persistent Reasoning
```

This repository implements only the **first stage**.

---

End of architecture_context.md