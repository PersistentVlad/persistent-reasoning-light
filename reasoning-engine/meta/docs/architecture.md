# Architecture

## Overview

Persistent Reasoning Light (PR-Light) implements a minimal structured reasoning engine designed to stabilize agent behavior across long tasks.

The system introduces a lightweight reasoning layer that sits between agent systems and persistent artifact storage.

The architecture intentionally remains simple and consists of three main layers.

```
Agent System
↓
Reasoning Adapter
↓
Reasoning Engine
↓
Reasoning Brain (artifact repository)
```

Each layer has a clear responsibility.

---

## Core Components

### Reasoning Engine

The reasoning engine is the core runtime responsible for managing reasoning artifacts.

Main responsibilities include:

- artifact validation
- artifact suggestion filtering
- artifact storage
- relation tracking
- working context generation

The engine operates purely on structured reasoning artifacts.

It does not store conversation logs or raw reasoning traces.

---

### Reasoning Brain

The reasoning brain is the persistent storage layer for reasoning artifacts.

Artifacts are stored as small JSON files.

Typical structure:

```
reasoning-brain/

tasks/
decisions/
constraints/
procedures/
issues/
```

Each artifact represents a durable reasoning element.

The brain may live:

- inside the same repository
- in a separate repository
- on remote storage

---

### Reasoning Adapters

Adapters connect external agent systems to the reasoning engine.

They translate between:

- agent runtime state
- reasoning artifacts
- engine operations

Adapters allow the reasoning engine to remain independent of specific agent platforms.

Examples include adapters for:

- coding agents
- automation agents
- workflow agents
- research agents

---

## Reasoning Flow

A typical reasoning cycle looks like this:

```
agent performs step
↓
adapter retrieves working context
↓
agent produces reasoning outcome
↓
adapter generates artifact suggestion
↓
artifact_filter evaluates suggestion
↓
artifact stored as draft
↓
artifact committed to reasoning brain
```

This process gradually builds a persistent reasoning brain.

---

## Git-Based Persistence

PR-Light uses Git as the persistence layer.

Git provides:

- transparent artifact history
- distributed replication
- inspectable reasoning evolution

Because artifacts are small JSON files, Git history becomes a timeline of reasoning development.

---

## Design Goals

The architecture prioritizes:

Minimalism  
The system must remain easy to understand.

Transparency  
Reasoning artifacts must be human-readable.

Stability  
The reasoning core must remain stable across integrations.

Extensibility  
Adapters allow integration with multiple agent systems.

---

## Scope

This architecture implements **Persistent Reasoning Light**, not the full Persistent Reasoning system.

It intentionally excludes:

- governance protocols
- distributed reasoning clusters
- blockchain lineage anchoring
- reasoning marketplaces

Those features belong to the full PR architecture.