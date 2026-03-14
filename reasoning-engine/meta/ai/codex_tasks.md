# Codex Tasks
## Persistent Reasoning Light — Implementation Plan

This document defines the implementation tasks and constraints for AI coding agents (Codex / Claude Code) working inside the Persistent Reasoning Light repository.

Codex acts as an implementation executor, not an architecture designer.

All generated code must follow the architecture defined in:

```
reasoning-engine/meta/ai/AIContext.md
reasoning-engine/meta/ai/architecture_context.md
reasoning-engine/meta/ai/codex_rules.md
```

The goal is to implement a minimal deterministic prototype of the Light Persistent Reasoning engine.

---

# Global Implementation Rules

## Repository Structure Rule

Codex must not create new directories unless explicitly specified in this document.

Allowed top-level directories:

```
reasoning-engine/
reasoning-brain/
reasoning-adapters/
```

Core runtime modules must remain inside:

```
reasoning-engine/core/
```

Tests must live inside:

```
reasoning-engine/tests/
```

---

## Golden Target Reference

AI agents must follow the execution style defined in:

```
reasoning-engine/meta/ai/golden_target.md
```

This document provides examples of acceptable code patterns and runtime behavior.

---

## Dependency Rule

Allowed dependencies:

```
Python standard library only
```

External packages must not be introduced.

---

## Function Size Rule

Functions must remain small and readable.

Guideline:

```
Avoid functions longer than 50 lines.
```

Prefer explicit logic over abstraction.

---

# Artifact ID Rules

Artifact IDs must follow the format:

```
<type_prefix>_<short_name>
```

Allowed prefixes:

```
task
decision
constraint
procedure
issue
```

Examples:

```
task_git_loader
decision_use_git
constraint_no_overwrite
procedure_add_artifact
issue_relation_storage
```

Artifact IDs must remain stable once created.

---

# Artifact Filename Rule

Artifact filenames must match artifact IDs exactly.

Examples:

```
task_git_loader.json
decision_use_git.json
```

No alternative filename patterns are allowed.

---

# Artifact Schema

Base artifact fields:

```
id
type
domains
created_at
updated_at
```

Timestamp rules:

```
ISO 8601 UTC
example: 2026-03-08T12:34:00Z
```

Behavior:

- if `created_at` missing → set automatically
- if `updated_at` missing → set equal to `created_at`
- if artifact updated through allowed operation → refresh `updated_at`

---

# Domains

```
domains: list[str]
```

Rules:

- lowercase snake_case
- first element = primary domain

Default if missing:

```
["general"]
```

This default must be applied during:

- artifact loading
- validation
- serialization
- working context building

Domains are classification metadata only.

Domains must not be used as:

- policy flags
- semantic meaning
- replacement for relations

Artifact meaning is determined by:

```
artifact type
artifact content
explicit relations
```

---

# Artifact Types

Supported types:

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

Codex must not introduce additional artifact types.

---

# Artifact Content Fields

## TaskCard

Required:

```
goal
status
context
```

Types:

```
goal: str
status: str
context: list[str]
```

Rules:

```
TaskCard.context must contain only artifact IDs.
```

It must not contain:

- free text
- nested objects
- mixed values
- comments

---

## DecisionCard

Required:

```
statement
reason
status
```

Types:

```
statement: str
reason: list[str]
status: str
```

---

## ConstraintCard

Required:

```
statement
reason
```

---

## ProcedureCard

Required:

```
name
steps
```

Types:

```
name: str
steps: list[str]
```

---

## IssueCard

Required:

```
question
priority
```

---

# Canonical Artifact Storage

Canonical artifact directories:

```
reasoning-brain/brain/tasks/
reasoning-brain/brain/decisions/
reasoning-brain/brain/constraints/
reasoning-brain/brain/procedures/
reasoning-brain/brain/issues/
```

These directories store persistent reasoning artifacts.

No other directories may contain canonical artifacts.

---

# Artifact Path Mapping

Artifact-to-directory mapping is fixed:

```
TaskCard -> reasoning-brain/brain/tasks/
DecisionCard -> reasoning-brain/brain/decisions/
ConstraintCard -> reasoning-brain/brain/constraints/
ProcedureCard -> reasoning-brain/brain/procedures/
IssueCard -> reasoning-brain/brain/issues/
```

This mapping must be implemented in one shared location.

Do not infer paths dynamically.

---

# Duplicate Artifact Protection

If an artifact with the same ID already exists in canonical storage:

```
storage must fail explicitly
```

Silent overwriting is forbidden.

---

# Deterministic JSON Serialization

Artifacts must be serialized using deterministic JSON formatting.

Recommended behavior:

```
json.dumps(
    obj,
    sort_keys=True,
    ensure_ascii=False,
    indent=2
)
```

Additional rules:

- UTF-8 encoding
- stable key ordering
- no trailing whitespace
- indentation must remain stable

This ensures clean Git diffs.

---

# Runtime Proposal Pipeline

Transient directories:

```
reasoning-brain/runtime/inbox/
reasoning-brain/runtime/drafts/
```

Meaning:

```
inbox  = raw artifact suggestions
drafts = filtered artifact suggestions
```

Artifacts stored here are non-canonical.

Pipeline:

```
agent
↓
artifact suggestion
↓
runtime/inbox
↓
artifact_filter
↓
runtime/drafts
↓
commit
↓
brain
↓
relations
↓
views
```

---

# Relations

Relation files:

```
reasoning-brain/relations/depends_on.jsonl
reasoning-brain/relations/blocks.jsonl
```

Relations are directed edges.

Meaning depends on relation file name.

Examples:

```
depends_on:
task -> decision

blocks:
constraint -> task
```

Format:

```json
{"from": "task_git_loader", "to": "decision_use_git"}
```

Rules:

- JSONL format
- one relation per line
- fields required: `from`, `to`

Self-edges are forbidden:

```json
{"from": "task_a", "to": "task_a"}
```

Relation validation:

Both referenced artifact IDs must exist in canonical artifact directories at validation time.

Dangling edges must be rejected.

---

# Artifact Filter

Module:

```
reasoning-engine/core/artifact_filter.py
```

Allowed verdicts:

```
ACCEPT
REJECT
REWRITE
POSSIBLE_DUPLICATE
```

Explanation:

```
POSSIBLE_DUPLICATE signals that human review may be required.
It does not automatically block storage.
```

The filter applies only to:

- agent-proposed artifacts
- auto-generated draft artifacts

The filter must not:

- write files
- commit artifacts
- mutate storage
- persist artifacts

---

# Working Context

File:

```
reasoning-brain/views/working_context.json
```

If the reasoning brain contains no artifacts, the system must still operate without errors.

The working context must remain intentionally minimal.

It must not contain:

- full artifact bodies
- reasoning traces
- duplicated artifact content
- large summaries

The context must reference canonical artifacts instead of copying them.

Fields:

```
active_task
decisions
constraints
open_issues
```

Active task rule:

```
active_task = first TaskCard where status == "active"
```

If none exists:

```
active_task = null
```

---

# Deterministic Ordering

All lists returned by the engine must use deterministic ordering.

Prefer:

```
lexicographic ordering of artifact IDs
```

Applies to:

- storage.list_artifacts()
- relation loading
- context building

---

# Brain Path Configuration

The reasoning brain path must be configurable.

Modules must not hardcode repository-relative paths.

Use a shared path-resolution helper.

---

# CLI

Module:

```
reasoning-engine/core/cli.py
```

Commands:

```
load-brain
build-context
add-artifact
validate-brain
```

Rule:

```
add-artifact must create artifacts in runtime/inbox
```

CLI output should remain minimal and human-readable.

Avoid verbose logging in the prototype.

---

# Tests

Tests live in:

```
reasoning-engine/tests/
```

Files:

```
test_cards.py
test_storage.py
test_relations.py
test_view_builder.py
test_git_adapter.py
```

Test scope rules:

- test only implemented prototype behavior
- do not generate speculative tests
- no adapter integration tests
- no governance tests

Prefer small unit tests.

---

# Silent Schema Expansion Rule

Codex must not introduce additional schema fields unless explicitly defined.

Forbidden examples:

```
metadata
tags
notes
description
debug_info
```

This rule applies to:

- artifacts
- relations
- working context
- runtime structures

---

# Central Constants Rule

Fixed values must be defined in one shared location and reused across modules.

Examples:

- artifact type list
- artifact-to-directory mapping
- supported relation files
- canonical paths

Codex must not duplicate these constants across multiple modules.

---

# No Fallback Magic Rule

Codex must not introduce implicit fallback behavior.

If input is invalid or unsupported, the system must fail explicitly.

Do not silently invent:

- alternative paths
- fallback filenames
- implicit schema interpretations

---

# Module Boundary Rule

Each runtime module must keep a narrow responsibility.

Examples:

```
reasoning-engine/core/validation.py → schema validation
reasoning-engine/core/artifact_filter.py → suggestion verdicts
reasoning-engine/core/storage.py → filesystem operations
reasoning-engine/core/git_adapter.py → Git operations
reasoning-engine/core/view_builder.py → derived views
reasoning-engine/core/context_loader.py → context loading
```

Responsibilities must not be merged across modules.

---

# Runtime Module Map

This section defines the responsibility of each runtime module in the Persistent Reasoning Light engine.

Codex must follow this module map strictly.

Do not introduce extra runtime modules unless explicitly approved.

---

## `reasoning-engine/core/artifact_types.py`

Purpose:

- define supported artifact types
- define artifact type prefixes
- define artifact-to-directory mapping
- define canonical directory constants
- define supported relation file names

This module is the **single shared location** for fixed runtime constants.

It must not contain storage logic or validation logic.

---

## `reasoning-engine/core/artifact_cards.py`

Purpose:

- define artifact data structures
- implement TaskCard
- implement DecisionCard
- implement ConstraintCard
- implement ProcedureCard
- implement IssueCard
- implement serialization helpers
- implement deserialization helpers
- apply artifact defaults where required

This module defines the unified artifact schema.

It must not perform storage operations or Git operations.

---

## `reasoning-engine/core/validation.py`

Purpose:

- validate artifact schema
- validate artifact type
- validate required fields
- validate domain format
- validate timestamp format
- validate TaskCard.context structure
- validate relation object structure
- reject invalid self-edges
- reject dangling relation references at validation time

This module performs **schema and structure validation only**.

It must not perform filtering, storage, or Git operations.

---

## `reasoning-engine/core/storage.py`

Purpose:

- load canonical artifacts
- save canonical artifacts
- load transient proposal artifacts
- save transient proposal artifacts
- list artifacts by type
- resolve canonical file paths
- enforce duplicate artifact protection

This module performs **filesystem read/write operations only**.

It must not perform Git commits or artifact filtering.

---

## `reasoning-engine/core/relations.py`

Purpose:

- load relation files from JSONL
- validate relation file format
- provide relation lookup helpers
- expose deterministic relation ordering

Supported files:

- `reasoning-brain/relations/depends_on.jsonl`
- `reasoning-brain/relations/blocks.jsonl`

This module handles **relation loading and lookup only**.

It must not implement graph databases or advanced graph algorithms.

---

## `reasoning-engine/core/artifact_filter.py`

Purpose:

- evaluate artifact suggestions
- return one of the allowed verdicts:
  - `ACCEPT`
  - `REJECT`
  - `REWRITE`
  - `POSSIBLE_DUPLICATE`
- detect trivial duplicates
- reject temporary or low-value reasoning suggestions

This module applies only to:

- agent-proposed artifacts
- auto-generated draft artifacts

It must not:

- persist artifacts
- modify storage
- commit to Git

---

## `reasoning-engine/core/view_builder.py`

Purpose:

- build derived views from canonical artifacts
- generate `reasoning-brain/views/working_context.json`
- resolve active task
- collect referenced decisions
- collect referenced constraints
- collect referenced issues
- preserve working context minimalism
- preserve deterministic ordering

This module builds **views only**.

It must not load the entire brain into memory unnecessarily and must not duplicate full artifact bodies into working context.

---

## `reasoning-engine/core/context_loader.py`

Purpose:

- load `reasoning-brain/views/working_context.json`
- resolve referenced artifact IDs where required
- return compact context structures for agent use

This module loads **prepared context only**.

It must not build views or perform storage writes.

---

## `reasoning-engine/core/git_adapter.py`

Purpose:

- stage artifact files
- commit changes
- read repository state

Required functions:

- `stage_artifact(path)`
- `commit_changes(message)`
- `get_repo_state()`

This module handles **Git operations only**.

It must not implement storage writes, validation, or artifact filtering.

---

## `reasoning-engine/core/cli.py`

Purpose:

- expose minimal developer commands
- call runtime modules in the correct order
- provide human-readable CLI output

Commands:

- `load-brain`
- `build-context`
- `add-artifact`
- `validate-brain`

Important rule:

- `add-artifact` must create artifacts in `reasoning-brain/runtime/inbox/`

The CLI must remain minimal and must not introduce framework-style command systems.

---

# Module Boundary Rule

Each runtime module must keep a narrow responsibility.

Codex must not merge responsibilities across modules unless explicitly required by this document.

Examples:

- `reasoning-engine/core/validation.py` validates only
- `reasoning-engine/core/storage.py` reads/writes files only
- `reasoning-engine/core/artifact_filter.py` returns verdicts only
- `reasoning-engine/core/git_adapter.py` stages/commits only
- `reasoning-engine/core/view_builder.py` builds views only
- `reasoning-engine/core/context_loader.py` loads prepared context only

This boundary is a core architectural rule of the PR-Light prototype.

# AI Execution Discipline

This section defines the execution behavior expected from AI coding agents (Codex / Claude Code) when implementing the Persistent Reasoning Light runtime.

AI agents must follow these rules to ensure deterministic and stable implementation.

---

## Single Task Focus

AI agents must implement **only the files required for the current implementation phase**.

Do not generate files from future phases.

Do not anticipate future architecture changes.

Each phase must be completed before moving to the next.

---

## No Architecture Interpretation

AI agents must **not reinterpret architecture documents**.

Architecture documents define the system structure and must be followed exactly.

AI agents must not:

- redesign module boundaries
- introduce alternative abstractions
- simplify the architecture
- introduce additional components

The architecture is already finalized.

---

## Deterministic Implementation

Generated code must behave deterministically.

Avoid:

- random ordering
- implicit dictionary iteration
- non-deterministic filesystem traversal

When listing artifacts or relations, prefer:

```
sorted(list_of_ids)
```

Deterministic ordering ensures stable behavior and clean Git diffs.

---

## Explicit Error Handling

The system must fail explicitly when encountering invalid input.

Avoid silent fallback behavior.

Examples:

Invalid artifact type  
Invalid domain format  
Unknown artifact directory  
Malformed relation entry

These conditions must raise explicit errors.

---

## Minimal Logic Rule

Code must remain simple and readable.

Avoid:

- complex helper abstractions
- dynamic metaprogramming
- generic frameworks
- overly abstract utility layers

Persistent Reasoning Light is intentionally minimal.

---

## Avoid Premature Optimization

Do not introduce performance optimizations unless explicitly required.

Examples of forbidden optimizations in this prototype:

- caching layers
- indexing structures
- background processing
- asynchronous execution

The prototype prioritizes **clarity and determinism over performance**.

---

## Respect Module Boundaries

Each runtime module has a narrow responsibility.

AI agents must not merge responsibilities across modules.

Example violations:
```
storage module performing validation
artifact_filter writing files
git_adapter loading artifacts
```

Such behavior violates the architecture.

---

## Preserve Code Readability

Generated code must remain readable for human developers.

Guidelines:

- meaningful variable names
- short functions
- explicit control flow
- minimal nested logic

The system should be easy to inspect and understand.

---

## Do Not Introduce Hidden Behavior

AI agents must not introduce hidden behavior or implicit side effects.

Examples of forbidden behavior:

- automatic schema migration
- silent artifact renaming
- automatic relation repair
- implicit domain correction

All behavior must be explicit and predictable.

---

## Follow the Architecture Strictly

Persistent Reasoning Light is a minimal architectural prototype.

AI agents must implement the architecture **exactly as specified**.

Do not expand the architecture.

Do not simplify the architecture.

Do not introduce speculative features.

---

# Implementation Phases

## Phase 1 — Artifact Model

```
reasoning-engine/core/artifact_types.py
reasoning-engine/core/artifact_cards.py
reasoning-engine/core/validation.py
```

## Phase 2 — Storage

```
reasoning-engine/core/storage.py
reasoning-engine/core/relations.py
```

## Phase 3 — Context System

```
reasoning-engine/core/view_builder.py
reasoning-engine/core/context_loader.py
```

## Phase 4 — Proposal Flow

```
reasoning-engine/core/artifact_filter.py
```

## Phase 5 — Git Integration

```
reasoning-engine/core/git_adapter.py
reasoning-engine/core/cli.py
```

---

# Explicit Non-Goals

The following must not be implemented in this prototype:

- REST API
- web UI
- database storage
- vector search
- embeddings
- graph database
- distributed reasoning
- bundle registry
- automatic merge logic
- semantic clustering

Persistent Reasoning Light must remain a minimal inspectable prototype.

---

# Final Rule

The system must remain:

```
minimal
deterministic
inspectable
Git-native
```

Codex must not expand the architecture beyond this document.