# Agent Execution Contract v1

Persistent Reasoning Light — Benchmark Mode

---

## 1. Purpose

Define the system-level execution contract for integrating any benchmarked reasoning agent into the Persistent Reasoning Light benchmark subsystem.

This contract ensures:

- deterministic benchmark handling
- event-first architecture preservation
- no hidden computation
- strict boundary enforcement
- consistent execution semantics across providers

This is the **general benchmarked-agent contract**.
Provider-specific contracts must comply with this document and may only define additional execution details or restrictions.

---

## 2. Scope

This contract governs:

- benchmark adapter execution behavior
- benchmarked-agent invocation boundaries
- prompt and output handling
- event emission requirements
- result derivation boundaries
- failure semantics
- scaffold compatibility

This contract does **not** define:

- provider-specific SDK usage
- provider-specific transport details
- provider-specific authentication mechanisms
- provider-specific response quirks

Those belong in provider-specific execution contracts.

---

## 3. Execution Role Definition

A benchmarked agent operates as:

> a reasoning agent under evaluation

A benchmarked agent is **not**:

- a repository engineer
- a benchmark controller
- a report generator
- a metric calculator
- a system mutator

---

## 4. Execution Boundary

All benchmarked-agent interactions MUST be routed exclusively through the corresponding benchmark adapter.

### Forbidden

- direct model invocation from runners
- direct model invocation from benchmark tools
- direct model invocation from comparison/reporting layers
- hidden or temporary shortcut paths
- direct result construction outside the event → derivation flow

### Allowed

- adapter-controlled invocation only

This is a system-level invariant.

---

## 5. Input Contract

The benchmarked agent receives:

> exactly one final benchmark prompt string

The adapter is the sole authority for benchmark prompt construction.

All context available to the benchmarked agent MUST be explicitly embedded in the prompt.

No implicit context is allowed.

### The benchmarked agent MUST NOT rely on:

- hidden repository state
- arbitrary filesystem reads
- unstated environment context
- implicit benchmark internals
- hidden memory outside the provided prompt

---

## 6. Output Contract

The benchmarked agent MUST return:

> exactly one raw textual response

The adapter treats the response as:

> one opaque contiguous string

### Allowed

- plain text answer
- optionally embedded structured content inside the text

### Not allowed

- multiple logical outputs
- side-channel communication
- partial streaming fragments as benchmark output
- multi-channel structured response protocols
- repository writes

The benchmarked agent MUST NOT use external tools unless explicitly included in the prompt.

---

## 7. Adapter Parsing Responsibility

The benchmarked agent output is **not structured by contract**.

The adapter:

- receives one raw string
- may optionally extract structured artifact suggestions
- validates extracted structure using existing artifact validation rules
- treats invalid structured content as:
  - no valid artifact suggestion
  
Structured extraction MUST NOT alter the original raw output.

The benchmarked agent does **not**:

- control parsing
- enforce artifact schema
- write artifacts directly

---

## 8. Canonical Execution Flow

The benchmark execution flow is:

```text
scenario
→ build prompt (adapter)
→ invoke benchmarked agent
→ capture raw textual output
→ write .trace.log
→ emit events (.events.jsonl)
→ derive_result_artifact(...)
→ result.json
→ comparison
→ reporting
```

This flow must not be bypassed.

---

## 9. Event Emission Rules

The adapter MUST emit:

### Required core events
- task_started
- at least one non-terminal execution/progress event
- exactly one terminal event:
  - task_completed
  - or task_failed

### Conditional events
- working_context_loaded (if applicable)
- artifact_suggested (if applicable)

### Rules
- terminal event MUST always be emitted
- event emission MUST never be skipped entirely
- event semantics MUST remain adapter-controlled
- metrics MUST NOT be derived inside the adapter

---

## 10. Result Derivation Boundary

result.json MUST be derived only from benchmark events.

### Forbidden
- adapter constructing result.json
- benchmarked agent influencing result.json directly
- hidden metric computation
- bypassing the event → derivation pipeline

Events are the only source of truth for metric derivation.

---

## 11. Determinism Constraint

The system does not require the external model/provider to produce identical outputs across independent invocations.

The required determinism invariant is:

> given the same prompt and the same captured raw output,
adapter handling, event emission, and result derivation MUST remain deterministic

This means:
- event content and ordering must be deterministic
- result derivation must be reproducible
- optional metadata must not affect result derivation semantics

---

## 12. Repository Mutation Policy

In benchmark mode, the benchmarked agent is:
> read-only with respect to the repository

### Forbidden
- modifying repository files
- writing benchmark artifacts directly
- committing changes
- mutating benchmark brain state
- mutating reports, comparison, or result artifacts

---

## 13. Brain Interaction Rules

The benchmarked agent:
- receives projected context only

The benchmarked agent does not mutate:
- runtime brain
- seeded brain
- empty brain

Brain evolution is outside benchmark execution.

---

## 14. Failure Semantics

Execution failure conditions include:
- empty output
- whitespace-only output
- malformed output
- runtime error
- timeout / no response
- output size violation

Timeout MUST be explicitly enforced for every execution attempt.

On failure, the adapter MUST:
- emit task_failed
- include explicit failure reason metadata when available
- preserve the event-first pipeline
- avoid crashing unrelated benchmark layers unnecessarily
- allow result derivation to proceed from events

---

## 15. Output Constraints

The adapter MUST enforce execution-output constraints.

Output must be:
- a single contiguous string
- non-empty
- bounded in size
- suitable for deterministic capture and logging

The output MUST represent a single complete response, not a concatenation of partial outputs.

If output constraints are violated, the adapter MUST treat the execution as failed.

---

## 16. Retry Policy

Implicit retries are forbidden.

> One benchmark run = one execution attempt

The adapter MUST NOT perform hidden retries.

If execution fails, failure must be recorded explicitly.

---

## 17. Scaffold Mode Compatibility

In scaffold mode:
- benchmarked-agent output MAY be replaced with placeholder output

However, scaffold mode MUST still preserve:
- adapter-only execution boundary
- event emission
- event-derived result generation
- no shortcut rule

Scaffold mode MUST NOT bypass the benchmark architecture.

---

## 18. Compliance Checklist

Before enabling any benchmarked-agent execution path:
- [ ] invocation routed only through benchmark adapter
- [ ] prompt constructed only by adapter
- [ ] output captured as a single raw string
- [ ] no implicit context or hidden filesystem access
- [ ] no retries
- [ ] events emitted correctly
- [ ] no result.json before derivation
- [ ] no repository mutation
- [ ] deterministic adapter/event/result handling verified

---

## 19. Provider-Specific Specialization Rule

Provider-specific execution contracts:
- MUST comply with this contract
- MUST NOT redefine system invariants
- MAY add provider-specific transport, configuration, timeout, or output-handling rules
- MAY impose stricter restrictions
- MUST document only the delta from this general contract whenever possible

---

## Final Principle

The benchmarked agent produces reasoning output.

The benchmark system evaluates reasoning through events.

The adapter enforces the boundary between them.

---
