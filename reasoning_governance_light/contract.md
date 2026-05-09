# reasoning_governance_light Contract v1.1

## 1. Purpose

This document defines the minimal API surface, invariants, and behavioral rules for the `reasoning_governance_light/` layer.

The goal is to provide a **deterministic acceptance boundary** between:
- reasoning-engine
- reasoning_brain_storage

This layer decides whether a candidate reasoning artifact may enter persistent brain state.

It is intentionally minimal and strictly bounded.

---

## 2. Role

```text
reasoning-engine = proposes
reasoning_governance_light = decides
reasoning_brain_storage = persists
```

### reasoning_governance_light MUST:
- validate candidate artifacts
- detect duplicates / rediscovery (deterministically)
- return explicit acceptance decisions
- remain deterministic and auditable

### reasoning_governance_light MUST NOT:
- perform model inference
- mutate storage directly
- rewrite artifacts
- perform benchmark orchestration
- act as a full governance system

---

## 3. Scope (v1)

This layer is intentionally limited to:
- schema validation
- required-field validation
- exact duplicate detection
- simple deterministic rediscovery classification (optional)
- accept / reject decision
- explicit reason codes

This layer does not include:
- ranking
- semantic reasoning
- merge logic
- replace / forget logic
- promotion to seeded
- human review workflow
- LLM-in-the-loop governance

---

## 4. API Surface (v1)

Single public operation:

```
evaluate_artifact(candidate, brain_state) -> AcceptanceDecision
```

Requirements:
- must be side-effect free
- must not perform I/O
- must not mutate inputs
- must not access storage directly
- must not depend on environment state

Internal helpers (e.g. duplicate checks) must not be exposed as public contract.

---

## 5. Inputs

### Candidate Artifact
A structured artifact candidate produced by the reasoning engine.

Requirements:
- must already be parsed
- must not be raw free-form text
- must conform to expected artifact structure (or be rejected)

Canonical v1 artifact taxonomy:
- `task`
- `decision`
- `constraint`
- `procedure`
- `issue`

### Brain State (CRITICAL)
`brain_state` must be a read-only structured snapshot of the reasoning brain.

It must be sufficient to evaluate:
- existing artifact ids
- existing artifact structure
- duplicate conditions

Minimal v1 required shape:

```
{
  "artifacts_by_id": {
    "<artifact_id>": {
      ...full persisted artifact payload...
    }
  }
}
```

### Brain State MUST NOT be:
- a mutable live handle
- a storage owner object
- a write-capable wrapper
- a direct filesystem manipulation interface

### Rule:

```
governance reads state
governance never mutates state
```

---

## 6. Output — AcceptanceDecision

Acceptance decisions must follow a strict structured format.

### Required fields:

```
status: accepted | rejected | duplicate | rediscovered
reason_code: str
```

### Optional fields:
- `artifact_id`
- `duplicate_of`
- `rediscovered_of`
- `notes` (human-readable only)

---

## 7. Acceptance Status Values

Allowed values:
- `accepted` — valid new artifact accepted for persistence
- `rejected` — invalid or forbidden artifact
- `duplicate` — exact duplicate of an existing artifact
- `rediscovered` — deterministic reappearance of existing knowledge (v1 optional)

No other values are allowed.

---

## 8. Acceptance Rules (v1)

A candidate artifact may be accepted only if:
- schema is valid
- required fields are present
- required values are valid
- duplicate constraints are satisfied
- no forbidden mutation is implied

### Minimum Checks

1. Schema validation
Reject malformed artifacts.

2. Required fields
Reject missing identifiers or type.

3. Exact duplicate id
Reject artifacts with an existing id.

4. Duplicate detection
Detect exact duplicates deterministically.

### Rediscovery (STRICT v1 CONSTRAINT)

`rediscovered` must remain:
- deterministic
- rule-based
- non-semantic

Forbidden in v1:
- semantic similarity judgment
- fuzzy matching
- model-based classification

If deterministic rediscovery cannot be guaranteed, implementations SHOULD fall back to:

```
status = duplicate
```

---

## 9. Determinism Constraints (STRICT)

Acceptance must be fully deterministic.

```
same candidate + same brain_state → same decision
```

Forbidden:
- randomness
- time-based logic
- external API calls
- model inference

Allowed inputs:
- candidate artifact
- brain_state snapshot

---

## 10. Auditability Requirement

Every decision must be explainable via `reason_code`.

Examples:
- `accepted`
- `invalid_schema`
- `missing_required_field`
- `duplicate_id`
- `duplicate_exact`
- `rediscovered_rule_match`
- `forbidden_mutation`

Rules:
- `reason_code` must be stable
- `reason_code` must be machine-readable
- vague descriptions are forbidden

---

## 11. Error Handling vs Decision Results

### Decision Results

Rejection is a valid outcome and MUST NOT raise an error.

Examples:
- invalid schema → status = rejected
- duplicate → status = duplicate

### Errors

Errors are reserved for contract violations:
- invalid input type
- missing required function arguments
- corrupted brain_state
- unexpected runtime failures

### Rule:

```
Reject = decision
Error = contract violation
```

---

## 12. Mutation Boundary

`reasoning_governance_light` must not mutate brain state.

Forbidden:
- writing artifacts
- rebuilding context
- creating snapshots
- deleting artifacts
- modifying runtime state

Storage layer owns all mutations.

---

## 13. Benchmark Isolation

This layer must not depend on benchmark-specific logic.

Forbidden:
- scenario-specific rules
- benchmark modes (baseline, pr_light, etc.)
- prompt structure assumptions
- benchmark metrics

Allowed inputs:
- candidate artifact
- brain_state snapshot

---

## 14. Separation of Roles

```
engine → produces candidate
governance_light → decides
storage → persists
```

These responsibilities must not be collapsed.

---

## 15. Relationship to Future Governance

This layer is a minimal governance-compatible boundary, not full governance.

Future `reasoning_governance/` may include:
- promotion workflows
- review queues
- replace / forget logic
- trust models
- contradiction resolution
- human approval

v1 must remain small, stable, and deterministic.

---

## 16. Final Principle

`reasoning_governance_light` does not think.

It applies explicit deterministic rules
to decide whether reasoning artifacts may persist.

---
