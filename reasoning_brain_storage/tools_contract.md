# reasoning_brain_storage/tools Contract v1.1

## 1. Purpose

This document defines the minimal API surface, invariants, and behavioral rules for all reasoning brain storage operations.

The goal is to ensure:
- strict separation between benchmark and storage domains
- explicit and auditable reasoning state transitions
- prevention of ad hoc filesystem manipulation
- preservation of Persistent Reasoning principles

---

## 2. Ownership Boundary (CRITICAL)

```
benchmark = consumer
reasoning_brain_storage = owner of reasoning state
```

### Benchmark MUST:
- call storage tools only
- never manipulate brain folders directly
- never write artifact files directly
- never rebuild working context manually

### Storage MUST:
- own all brain lifecycle transitions
- enforce invariants
- reject invalid or unsafe mutations

---

## 3. Core Concepts

### empty
Canonical zero-state reasoning brain template.

### runtime
Mutable active reasoning brain used during accumulation.

### seeded
Curated immutable input brain.

## snapshot
Immutable captured brain state.

---

## 4. API Surface (v1)

Storage tools must expose the following operations:

```
initialize_brain(source, target_root)
load_brain(root)
export_governance_brain_state(brain)
persist_artifact(runtime_root, artifact)
rebuild_working_context(runtime_root)
create_snapshot(source_root, snapshot_root)
reset_to_empty(empty_template_root, runtime_root)
inspect_brain_snapshot(root)
compare_brain_snapshots(brain_a, brain_b)
diff_brains(brain_a, brain_b)
```

### Constraints:
- operations must be explicit
- no hidden side effects
- no implicit filesystem mutations

Canonical v1 on-disk schema for every reasoning brain root:

```
<brain_root>/
  brain/
    tasks/
    decisions/
    constraints/
    procedures/
    issues/
  runtime/
    drafts/
    inbox/
  relations/
  views/
    working_context.json
```

Persisted accepted artifacts must be written only under:

```
brain/<plural-category>/<artifact_id>.json
```

## Canonical v1 Artifact Taxonomy

Canonical persisted artifact families:
- `task`
- `decision`
- `constraint`
- `procedure`
- `issue`

## Benchmark-Visible Subset (v1)

These canonical families affect `working_context.json` in v1:
- `decision`
- `constraint`
- `issue`

Mapping:
- `decision` -> `decisions`
- `constraint` -> `constraints`
- `issue` -> `open_issues`

## Non-Benchmark-Visible Canonical Families (v1)

These families remain canonical and persistable in v1, but do not affect
`working_context.json` or benchmark-visible context in v1:
- `task`
- `procedure`

---

## 5. Artifact Lifecycle

```
model output
→ Artifact Suggestion
→ parse
→ acceptance check
→ if accepted → persist
→ rebuild working context
```

---

## 6. Artifact Acceptance Ownership

Artifact acceptance is not benchmark logic.

### Rules:
- Benchmark provides candidate artifacts only
- Benchmark MUST NOT decide acceptance
- Storage layer persists already-accepted artifacts only
- Storage layer exports the governance-facing read-only `brain_state` snapshot
- Governance evaluates candidate artifacts against that exported snapshot

Minimal governance-facing `brain_state` shape:

```
{
  "artifacts_by_id": {
    "<artifact_id>": {
      ...full persisted artifact payload...
    }
  }
}
```

Seam rules:
- export must read only canonical persisted artifacts under `brain/<plural-category>/`
- export must be deterministic and side-effect free
- export must not include runtime drafts, runtime inbox, relations, or live handles
- malformed persisted artifacts must raise explicit storage validation errors
- duplicate persisted artifact ids must raise explicit storage conflict errors

---

## 7. Invariants (MUST HOLD)

### 1. No Silent Mutation
Forbidden:
- silent overwrite
- implicit merge
- hidden cleanup
- in-place mutation without explicit operation

### 2. Append-Only Mutation Discipline
Rules:
- Existing artifacts must not be modified in place
- New knowledge must be introduced via new artifacts
- Replacement must be explicit and traceable

Implications:
- reasoning history must remain reconstructable
- lineage must be preserved
- no hidden rewriting of reasoning state

### 3. Deterministic Behavior
- same input → same output
- rebuild must be stable

### 4. Separation of Roles
benchmark ≠ storage ≠ governance

---

## 8. Forbidden Operations

Storage tools MUST NOT:
- mutate seeded brain
- overwrite existing artifacts silently
- auto-clean runtime without explicit call
- infer missing structure implicitly
- mutate during read operations
- merge states implicitly

Benchmark MUST NOT:
- write into brain folders directly
- copy/delete brain files manually
- bypass storage tools
- perform its own artifact persistence

---

## 9. Brain Input / Output Model

###brain_in

```
brain_in:
  type: empty | runtime | seeded | snapshot
  ref: ...
```

### brain_out

```
brain_out:
  mode: continue | snapshot | empty
```

### Semantics
**continue**
- runtime brain remains active
- mutations are preserved

**snapshot**
- runtime state is copied into immutable snapshot
- runtime state remains unchanged

**empty**
- all runtime mutations are discarded
- runtime brain is reset to canonical empty template

### empty Constraints
- reset must be explicit and complete
- no partial cleanup allowed
- no artifacts from previous run may remain
- runtime must match empty template exactly
- lineage is NOT implicitly preserved

Snapshots created before reset remain unaffected.

---

## 10. Evolution Model

```
evolution/<experiment_id>/
  run_1/
  run_2/
  ...
  plateau/
```

### Meaning:
- one experiment = one accumulation lineage
- each run = one state transition
- plateau = stabilization point (manual in v1)

---

## 11. Diff Auditor

Must be implemented as a storage tool.

Responsibilities:
- compare brain states
- inspect a single brain state
- detect:
 - added artifacts
 - removed artifacts
 - mismatched same-id payloads
 - shared persisted core
- summarize structural changes

V1 limits:
- duplicate and contradiction counts remain structural placeholders only
- mismatch is structural same-id payload mismatch
- no cross-id semantic matching
- no union merge semantics

### Storage-Domain Compare Entry Point

`reasoning_brain_storage/run_brain_compare.py` is the operational read-only entry point for:
- inspect
- compare

Compare reports are written under:

```
reasoning_brain_storage/compare_reports/<timestamp>_<label>/
```

V1 compare outputs:
- `comparison_summary.json`
- `diff.json`
- `intersect.json`
- `diff.md`
- `intersect.md`

Meaning:
- `diff` = structural added / removed / mismatched outputs
- `intersect` = shared persisted core under conservative identity rules

`intersect` is not truth and does not imply merge or union semantics.

---

## 12. Design Constraints

- no silent behavior
- no implicit mutation
- no hidden coupling with benchmark layer
- no direct filesystem manipulation outside tools

---

## 13. Final Principle

Reasoning brain is a persistent governed structure.

All mutations must be explicit, deterministic, and contract-bound.

---
