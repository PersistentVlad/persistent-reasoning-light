# Repository Layout

## Purpose

This document explains the structure of the Persistent Reasoning Light repository.

The layout is designed to clearly separate:

- reasoning engine code
- reasoning brain artifacts
- integration adapters
- documentation

This separation keeps the architecture easy to understand and extend.

---

## Top-Level Structure

```
persistent-reasoning-light/

reasoning-engine/
reasoning-brain/
reasoning-adapters/
```

Each directory represents a distinct architectural component.

---

## reasoning-engine

The reasoning engine contains the core runtime responsible for managing reasoning artifacts.

Example structure:

```
reasoning-engine/

core/
meta/
tests/
```

---

### core

The `core` directory contains the main runtime modules.

Example modules:

```
artifact_cards.py
artifact_filter.py
storage.py
validation.py
relations.py
view_builder.py
git_adapter.py
context_loader.py
cli.py
```

These modules implement the core reasoning engine functionality.

---

### meta

The `meta` directory contains documentation and AI guidance files.

Structure:

```
meta/

ai/
docs/
```

---

#### ai

Files intended for AI coding tools.

Examples:

```
AIContext.md
architecture_context.md
codex_rules.md
```

These files guide automated code generation.

---

#### docs

Human-readable architecture documentation.

Examples:

```
architecture.md
reasoning_model.md
repository_layout.md
```

---

### tests

Contains unit tests for the reasoning engine.

Example:

```
tests/

test_cards.py
test_storage.py
test_relations.py
test_view_builder.py
```

---

## reasoning-brain

The reasoning brain stores persistent reasoning artifacts.

Example structure:

```
reasoning-brain/

tasks/
decisions/
constraints/
procedures/
issues/
```

Artifacts are stored as individual JSON files.

The brain repository may be local or external.

---

## reasoning-adapters

The adapters directory contains integration layers for external agent systems.

Example structure:

```
reasoning-adapters/

codex_adapter/
claude_code_adapter/
openclaw_adapter/
zeroclaw_adapter/
generic_agent_adapter/
```

Adapters translate between agent environments and the reasoning engine.

---

## Design Principles

The repository layout follows several principles.

Separation of concerns  
Engine, storage, and adapters remain independent.

Transparency  
Reasoning artifacts remain easily inspectable.

Minimalism  
The project structure should remain small and understandable.

Extensibility  
New adapters and modules can be added without modifying the core architecture.

---

## Summary

The repository layout reflects the architecture of Persistent Reasoning Light.

```
Agents
↓
Adapters
↓
Reasoning Engine
↓
Reasoning Brain
```

This structure allows the reasoning engine to remain simple while supporting a wide variety of agent systems.