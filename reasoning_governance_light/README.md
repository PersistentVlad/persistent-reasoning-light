# reasoning_governance_light

`reasoning_governance_light/` is a minimal governance boundary for Persistent Reasoning Light.

It is responsible for **deterministic acceptance decisions** over candidate reasoning artifacts before they are persisted into the reasoning brain.

This layer is intentionally small, strict, and non-intelligent.

---

## Purpose

The purpose of `reasoning_governance_light` is to introduce a **clean separation between reasoning and persistence**:

- reasoning-engine produces candidate artifacts
- governance decides whether they are acceptable
- storage persists accepted artifacts

Without this layer, acceptance logic risks leaking into storage or benchmark code.

---

## Architectural Role

```
reasoning-engine = proposes
reasoning_governance_light = decides
reasoning_brain_storage = persists
```

This separation is required to:
- keep storage domain non-intelligent
- avoid implicit acceptance logic
- preserve auditability of reasoning state evolution
- prepare for future governance expansion

---

## Scope (v1)

This layer performs only deterministic acceptance checks.

### Included:
- schema validation
- required-field validation
- exact duplicate detection
- simple deterministic rediscovery classification (optional)
- explicit accept / reject decision
- structured reason codes

### Explicitly Excluded:
- model-based evaluation
- semantic reasoning
- ranking or scoring
- artifact merging
- replace / forget logic
- promotion workflows
- human review
- benchmark-specific logic

This is not a full governance system.

---

## Key Principle

`reasoning_governance_light` does not think.

It only applies explicit deterministic rules.

---

## Inputs

### Candidate Artifact

A structured artifact proposed by the reasoning engine.

- must already be parsed
- must not be raw text
- may be valid or invalid

Canonical v1 artifact taxonomy:
- `task`
- `decision`
- `constraint`
- `procedure`
- `issue`

### Brain State

A read-only structured snapshot of the reasoning brain.

Used only for:
- duplicate detection
- validation context
- consistency checks

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

Must not be mutable or write-capable.

---

## Output

The layer returns a structured decision:

```
status: accepted | rejected | duplicate | rediscovered
reason_code: str
```

Optional fields may include:
- `artifact_id`
- `duplicate_of`
- `rediscovered_of`
- `notes`

### `reason_code` Requirements
- must be stable across runs
- must be machine-readable
- must not depend on phrasing variations
- must not contain free-form explanations

Examples of valid `reason_code` values:
- `accepted`
- `invalid_schema`
- `missing_required_field`
- `duplicate_id`
- `duplicate_exact`
- `rediscovered_rule_match`

Human-readable explanation (if needed) must be placed in `notes`, not in `reason_code`.

---

## Rediscovered (v1 Constraint)

`rediscovered` is optional in v1 and must remain strictly deterministic.

Allowed:
- rule-based matching
- exact structural equivalence
- explicit deterministic conditions

Forbidden:
- semantic similarity judgment
- fuzzy matching
- model-based evaluation

If deterministic rediscovery cannot be guaranteed,
the system SHOULD fall back to:

```
status = duplicate
```

---

## Decision Model

Acceptance is deterministic and auditable.

```
same input → same decision
```

No randomness, no heuristics, no hidden logic.

---

## Error vs Decision

```
Reject = decision
Error = contract violation
```

Decision examples:
- invalid schema → rejected
- duplicate id → duplicate

Error examples:
- invalid input type
- corrupted brain state

---

## Mutation Boundary

This layer is strictly read-only.

It must not:
- write artifacts
- modify brain state
- rebuild context
- create snapshots

All mutations are handled by `reasoning_brain_storage`.

---

## Relationship to Storage

`reasoning_governance_light` does not persist anything.

It only returns a decision.

```
if accepted → storage persists
if rejected → storage does nothing
```

---

## Relationship to Benchmark

This layer is benchmark-agnostic.

It must not depend on:
- scenarios
- benchmark modes
- prompts
- evaluation metrics

This ensures reuse outside benchmark environments.

---

## Minimal Execution Flow

At the seam, storage first exports the governance-facing `brain_state` snapshot,
then governance evaluates the candidate against that read-only value.

```
engine
→ candidate artifact
→ governance_light.evaluate_artifact(...)
→ decision

if decision.status == accepted:
    → storage.persist_artifact(...)
    → storage.rebuild_working_context(...)
```

---

## Why This Exists

Without a governance boundary:
- storage becomes “smart”
- acceptance logic becomes implicit
- reasoning state becomes unreliable
- evolution becomes non-auditable

This layer ensures:
- explicit decisions
- reproducible behavior
- clean separation of concerns

---

## Relationship to Future Governance

This is a lightweight v1 layer.

Future `reasoning_governance/` may include:
- artifact promotion
- review workflows
- trust models
- contradiction resolution
- replace / forget policies

This module is designed to evolve or be replaced by that system.

---

## Design Philosophy

- minimal
- deterministic
- explicit
- side-effect free
- contract-driven

No hidden intelligence.

---

## Final Principle

Reasoning is produced by the engine.

Governance only decides what is allowed to persist.

---
