# Interpretation Contract

## Purpose

This document defines the deterministic evaluation protocol for benchmark scenarios.

It specifies:
- evaluation signals
- decision order
- allowed operations
- forbidden operations

This contract MUST be followed exactly.

No heuristic or implicit interpretation is allowed.

---

## Core Principle

Evaluation is:
- deterministic
- metadata-driven
- final-state anchored

Interpretation MUST NOT:
- infer missing information
- repair model outputs
- apply semantic reasoning

---

## Signal Classification

### Core Metrics (affect evaluation)
- retention
- correctness
- structural ghost

### Diagnostic Signals (do NOT affect evaluation)
- temporal ghost
- trajectory warnings

---

## Scenario Metadata Requirements

Each scenario MUST explicitly declare:

```
{
  "supports_retention": true,
  "supports_correctness": false,
  "supports_ghost": true,
  "return_to_origin": false,
  "scenario_mode": "standard"
}
```

For composite scenarios:

```
{
  "scenario_mode": "sectioned"
}
```

No behavior may be inferred from scenario_id.

---

## Capability Enablement Rules

A scenario may declare a signal as supported **only if all corresponding conditions are satisfied**.

No signal may be enabled implicitly.

---

### return_to_origin = true

Allowed only if:
1. The scenario is reversible by design
2. An exact initial state exists
3. An exact final state exists
4. Exact equality comparison is parser-safe

Additional rule:
- Failure is binary:
  final_state != initial_state → failure
- Decomposition is continuous:
  retention, correctness, structural ghost, and temporal diagnostics may be used to explain the failure

---

### retention = true

Allowed only if:
1. A canonical unit set is explicitly defined
2. unit_ids are deterministic and explicitly declared
3. Final state can be extracted without inference
4. preserved vs lost units can be computed via exact matching

---

### correctness = true

Allowed only if:
1. Verifiable values or ordering are explicitly defined
2. An exact truth contract exists
3. Final values / slots / ordered output can be compared via exact match
4. No semantic interpretation is required

---

### ghost = true

Allowed only if:
1. Allowed set is explicitly defined
2. Final state can be extracted deterministically
3. A strict token/unit pattern exists for detection
4. Ghost units can be computed without semantic filtering

Note:
- Allowed set MAY be:
  - global
  - phase-aware
  - section-aware
- Allowed set MUST NOT be inferred from model output

---

### temporal_ghost (diagnostic only)

Temporal ghost is NOT a core metric.

It may be reported only if:
1. Intermediate trajectory or step outputs are available
2. A phase contract or allowed state space is defined

Rules:
- MUST NOT affect:
  - retention
  - correctness
  - structural ghost
  - scoring
- MUST be treated strictly as a diagnostic signal

---

## Evaluation Order (STRICT)

Evaluation MUST follow this exact order:
1. Validate output structure (headings, format)
2. Evaluate retention
3. Evaluate correctness (if enabled)
4. Evaluate structural ghost
5. Evaluate return-to-origin constraint (if enabled)
6. Compute evaluation result
7. Attach diagnostic signals (temporal ghost)

Steps MUST NOT be reordered.

---

## Retention

### Definition

Presence of canonical units in the final state.

### Rules
- exact unit matching only
- no aliasing
- no renaming
- no semantic equivalence

---

## Correctness

### Definition

Exact value match for defined slots.

### Rules
- exact string comparison
- no rounding
- no normalization
- no approximation

---

## Structural Ghost

### Definition

Any unit present in the final state that does not belong to the allowed set.

### Allowed Set

Must be explicitly defined and may include:
- canonical units
- explicitly allowed intermediate units
- explicitly allowed final units

### Rules

- pattern-based detection only
- no semantic filtering
- no inference from model output

---

## Temporal Ghost (Diagnostic Only)

### Definition

Any unit or state that appears during intermediate steps but is not part of the allowed state space or phase contract.

### Properties
- phase-local (trajectory-based)
- not final-state-based

### Rules
- MUST NOT affect:
 - retention
 - correctness
 - structural ghost
 - scoring
- MUST be reported only as diagnostics

### Minimal Output

```
{
  "temporal_diagnostics": {
    "temporal_ghost_detected": true,
    "temporal_ghost_count": 2
  }
}
```

---

## Structural vs Temporal Ghost Distinction

If a unit:
- appears during intermediate steps
- but is not allowed in final state

then:
- it MUST NOT be counted as structural ghost
- it MAY be counted as temporal ghost (diagnostic only)

Structural ghost is strictly final-state based.
Temporal ghost is strictly trajectory-based.

---

## Return-to-Origin Contract

Applies only if:

```
{
  "return_to_origin": true
}
```

### Rule

If:

```
final_state != initial_state
```

then:

```
→ failure signal MUST be triggered
```

### Decomposition

Failure MUST be analyzed via:
- retention loss
- correctness deviation
- structural ghost
- temporal ghost (diagnostic only)

Failure condition is binary:

```
final_state != initial_state → failure
```

Decomposition is continuous:
- retention
- correctness
- structural ghost
- temporal ghost (diagnostic)

These signals explain the failure but do not change its binary nature.

---

## Sectioned Scenarios (Composite)

Applies when:

```
{
  "scenario_mode": "sectioned"
}
```

### Rules
- each section MUST be evaluated independently
- no unit sharing between sections
- no cross-section inference

### Sectioned Aggregation Rules

For sectioned scenarios:
- each section MUST define max_percent
- total percent MUST equal 100
- aggregation MUST be:

```
final_score = sum(section_scores)
```

No weighting or normalization allowed.

---

## Parsing Failure Handling

If required structure is invalid:
- evaluation MUST NOT proceed
- no partial evaluation is allowed

Result MUST be marked as:

```
{
  "evaluation_status": "invalid_structure"
}
```

Score MUST be zero or undefined.

---

## Allowed Set Definition (CRITICAL)

Allowed set MUST be explicitly declared.

Allowed set MUST NOT be:
- inferred from model output
- constructed from trajectory
- expanded dynamically

---

## Allowed Set Resolution

Allowed set MAY be defined at multiple levels:
- global
- per_phase (optional)
- per_section (optional)

### Resolution Order (STRICT)

Allowed set MUST be resolved in the following order:
1. per_section + per_phase
2. per_section
3. per_phase
4. global

Allowed set MUST NOT be inferred from model output.

---

## Forbidden Operations

The system MUST NOT:
- infer missing units
- normalize or rewrite outputs
- fix model errors
- merge units across sections
- treat temporal ghost as a failure
- derive correctness from retention
- derive retention from correctness
- apply heuristic matching
- use scenario_id branching

---

## Interpretation Responsibility Boundaries

-------------------------------------------------
Layer				| Responsibility
-------------------------------------------------
Scenario			| defines rules and structure
Runner				| executes scenario
Parser				| extracts structured data
Interpretation		| applies this contract
Metrics	computes	| evaluation values
-------------------------------------------------

Responsibilities MUST NOT overlap.

---

## Golden Rule

If output is slightly wrong, it MUST fail.

There is no:
- "almost correct"
- "close enough"
- "semantically equivalent"

Only exact compliance is valid.

---