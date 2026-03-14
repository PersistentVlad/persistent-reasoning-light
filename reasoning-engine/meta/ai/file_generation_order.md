# File Generation Order
## Persistent Reasoning Light — Safe Generation Sequence

This document defines the recommended generation order for the Persistent Reasoning Light runtime.

Codex must generate files in this order.

The order is chosen to minimize ambiguity, prevent architecture drift, and ensure that dependencies between modules are satisfied.

---

# Phase 0 — Repository Sanity Check

Before generating runtime code, verify that the repository structure and architecture documentation already exist.

The following directories must already exist:

```
reasoning-engine/
reasoning-engine/core/
reasoning-engine/meta/
reasoning-engine/meta/ai/
reasoning-engine/meta/docs/

reasoning-engine/tests/

reasoning-brain/
reasoning-adapters/
```

The following architecture documents must already exist:

```
reasoning-engine/meta/ai/AIContext.md
reasoning-engine/meta/ai/architecture_context.md
reasoning-engine/meta/ai/codex_rules.md
reasoning-engine/meta/ai/codex_tasks.md
```

Code generation must not begin until these files are present.

Codex must not create missing architecture documents.

---

# Phase 1 — Artifact Model Foundation

Generate first:

```
reasoning-engine/core/artifact_types.py
reasoning-engine/core/artifact_cards.py
reasoning-engine/core/validation.py
```

Reason:

All later modules depend on artifact schema and artifact type definitions.

Validation must exist before storage and relation logic.

---

## Phase 1 Validation Scope

`validation.py` in Phase 1 must focus on **artifact schema validation only**.

Responsibilities include:

- artifact type validation
- required field validation
- domain format validation
- timestamp format validation
- TaskCard.context structure validation

Relation-aware validation must **not** be implemented yet.

Relation validation may be added later once `relations.py` exists.

---

# Phase 2 — Storage and Relations Foundation

Generate next:

```
reasoning-engine/core/storage.py
reasoning-engine/core/relations.py
```

Reason:

Storage depends on artifact schema.

Relations depend on artifact IDs and canonical storage paths.

View generation depends on both storage and relations.

---

## Storage Implementation Order

Storage generation should begin with **canonical artifact paths first**.

Step 1 — Canonical storage:

- load canonical artifacts
- save canonical artifacts
- list canonical artifacts
- enforce duplicate artifact protection

Step 2 — Transient runtime storage:

- runtime/inbox
- runtime/drafts

Transient runtime paths must not interfere with canonical artifact storage.

---

# Phase 3 — Context System

Generate next:

```
reasoning-engine/core/view_builder.py
reasoning-engine/core/context_loader.py
```

Reason:

Working context generation depends on stored artifacts and relations.

Context loading depends on working context output.

---

# Phase 4 — Proposal Quality Gate

Generate next:

```
reasoning-engine/core/artifact_filter.py
```

Reason:

The filter depends on artifact schema and validation logic.

It should be implemented only after the artifact model is stable.

---

# Phase 5 — Git Integration and CLI

Generate last:

```
reasoning-engine/core/git_adapter.py
reasoning-engine/core/cli.py
```

Reason:

Git integration depends on stable storage paths.

CLI depends on all runtime modules and acts as orchestration surface.

---

# Test Generation Order

Tests should only be generated after corresponding runtime modules exist.

Recommended order:

```
reasoning-engine/tests/test_cards.py
reasoning-engine/tests/test_storage.py
reasoning-engine/tests/test_relations.py
reasoning-engine/tests/test_view_builder.py
reasoning-engine/tests/test_git_adapter.py
```

Tests must validate implemented behavior only.

Speculative tests are forbidden.

---

# Phase Boundary Rule

After a phase is reviewed and accepted, later phases must **not redefine responsibilities of earlier modules**.

Examples of forbidden behavior:

- adding storage logic to validation module
- moving relation logic into storage module
- merging context builder logic into CLI

Module responsibilities become fixed once a phase is accepted.

---

# Recommended Execution Pattern

Do not generate the entire runtime at once.

Use the following sequence:

1. generate one phase
2. review generated code
3. correct issues
4. proceed to the next phase

This prevents architecture drift and keeps the implementation aligned with the specification.