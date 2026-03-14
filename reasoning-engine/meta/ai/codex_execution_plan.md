# Codex Execution Plan
## Persistent Reasoning Light — Step-by-Step Implementation

This document defines how Codex should be used to implement the Persistent Reasoning Light runtime safely.

Codex must execute implementation incrementally.

Do not generate the entire runtime in one step.

---

# Execution Rules

1. Execute one phase at a time.
2. Do not generate future-phase files early.
3. Review each phase before proceeding.
4. Do not introduce new modules.
5. Do not reinterpret architecture documents.

Later phases must not redefine earlier accepted module boundaries without explicit review.

Before generating code, review the style reference:

```
reasoning-engine/meta/ai/golden_target.md
```

Generated code should follow the patterns and constraints defined there.

---

# Phase 1 — Artifact Model

Files:

```
reasoning-engine/core/artifact_types.py
reasoning-engine/core/artifact_cards.py
reasoning-engine/core/validation.py
```

Objectives:

Implement:

- artifact type constants
- artifact prefixes
- canonical directory mapping
- artifact structures
- timestamp defaults
- domain defaults
- schema validation

---

## Validation Scope (Phase 1)

Validation in Phase 1 must focus only on **artifact schema validation**.

Validation must include:

- artifact type validation
- required fields
- domain format
- timestamp format
- TaskCard.context structure

Relation-aware validation must **not** be implemented in Phase 1.

Dangling relation reference checks belong to Phase 2.

---

## Acceptance Criteria

- five artifact types supported
- schema fields match artifact specification
- domain default is `["general"]`
- timestamps use ISO 8601 UTC
- invalid artifact type is rejected
- invalid domain format is rejected
- invalid TaskCard.context is rejected

---

# Phase 2 — Storage and Relations

Files:

```
reasoning-engine/core/storage.py
reasoning-engine/core/relations.py
```

Objectives:

Implement canonical artifact storage and relation handling.

Storage must be implemented in two steps.

Step 1 — Canonical storage

- canonical artifact load/save
- deterministic artifact listing
- duplicate artifact protection

Step 2 — Transient runtime storage

- runtime/inbox
- runtime/drafts

---

## Relation Validation (Phase 2)

Once relations module exists, validation may include:

- relation format validation
- self-edge rejection
- dangling relation reference rejection

Relation validation must verify that referenced artifacts exist in canonical artifact directories.

---

## Acceptance Criteria

- canonical artifact directories are respected
- duplicate artifact IDs are rejected
- relation files use JSONL format
- relation entries contain `from` and `to`
- self-edge relations are rejected
- dangling references are rejected
- deterministic ordering is preserved

---

# Phase 3 — Context System

Files:

```
reasoning-engine/core/view_builder.py
reasoning-engine/core/context_loader.py
```

Objectives:

Implement working context generation and loading.

Working context file:

```
reasoning-brain/views/working_context.json
```

---

## Context Design Rule

Working context must remain intentionally minimal.

The system should prefer **artifact IDs and references over embedded objects**.

The working context must not include:

- full artifact bodies
- reasoning traces
- duplicated artifact content

---

## Acceptance Criteria

- working context generated deterministically
- active task resolved correctly
- empty brain handled without errors
- context loader returns compact structures
- context prefers IDs over embedded objects

---

# Phase 4 — Artifact Suggestion Filter

File:

```
reasoning-engine/core/artifact_filter.py
```

Objectives:

Implement artifact suggestion filtering.

Allowed verdicts:

```
ACCEPT
REJECT
REWRITE
POSSIBLE_DUPLICATE
```

---

## Acceptance Criteria

- filter applies only to proposal flow
- filter does not write files
- filter does not commit to Git
- filter does not mutate storage
- POSSIBLE_DUPLICATE is advisory only

---

# Phase 5 — Git Integration and CLI

Files:

```
reasoning-engine/core/git_adapter.py
reasoning-engine/core/cli.py
```

Objectives:

Implement minimal Git operations and CLI interface.

Git adapter must provide:

```
stage_artifact(path)
commit_changes(message)
get_repo_state()
```

CLI must provide:

```
load-brain
build-context
add-artifact
validate-brain
```

---

## CLI Rule

The `add-artifact` command must create artifacts in:

```
reasoning-brain/runtime/inbox/
```

CLI must not write directly to canonical artifact directories.

CLI output should remain minimal and human-readable.

---

# Test Plan

Tests should be generated only after runtime modules exist.

Files:

```
reasoning-engine/tests/test_cards.py
reasoning-engine/tests/test_storage.py
reasoning-engine/tests/test_relations.py
reasoning-engine/tests/test_view_builder.py
reasoning-engine/tests/test_git_adapter.py
```

Rules:

- test only implemented behavior
- do not test speculative features
- no adapter integration tests
- prefer small deterministic unit tests

---

# Codex Execution Discipline

Codex must behave as an implementation worker.

It must not:

- redesign architecture
- introduce new modules
- expand artifact schema
- introduce framework dependencies
- anticipate future subsystems

Persistent Reasoning Light is intentionally minimal.

The goal is a deterministic, inspectable runtime prototype.

---

# Final Execution Principle

The system must remain:

```
minimal
deterministic
inspectable
Git-native
```

Codex must implement the architecture exactly as defined.