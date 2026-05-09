# Adapter Contract
## Persistent Reasoning Light — Runtime Adapter Contract

This document defines the shared contract for runtime adapters in the `reasoning_adapters/` layer.

It applies to all agent-specific adapters, including:

- Codex
- Claude
- OpenClaw
- zeroClaw

The purpose of this contract is to keep all adapters structurally compatible with the Light Persistent Reasoning runtime.

Adapters may differ in implementation details, but they must follow the same architectural boundaries.

---

# Purpose

A runtime adapter connects an external agent system to the Persistent Reasoning Light engine.

The adapter acts as a thin translation layer between:

- agent execution context
- reasoning-engine runtime modules
- reasoning-brain persistent artifacts

Adapters exist to allow agent-specific integration without leaking agent-specific behavior into the reasoning engine.

---

# Architectural Position

The adapter layer sits between the agent and the reasoning engine.

```text
Agent System
↓
Reasoning Adapter
↓
Reasoning Engine
↓
Reasoning Brain
```

The adapter is not the reasoning engine.

The adapter is not the reasoning brain.

The adapter is not a benchmark harness.

---

# Core Role

A runtime adapter is responsible for four things:
1. load compact reasoning context
2. translate context into agent-usable input
3. extract candidate reasoning outcomes from agent output
4. hand off artifact suggestions into the approved proposal flow

The adapter must remain a thin operational bridge.

---

# Required Responsibilities

All adapters must support the following responsibilities in some implementation-specific form.

## 1. Context Retrieval

The adapter must be able to retrieve the prepared working context from the reasoning engine.

This means using the existing context system rather than rebuilding context independently.

Typical responsibility:
load working context

The adapter must not load the full reasoning brain unless explicitly required by a higher-level workflow.

## 2. Context Translation

The adapter must translate PR-Light working context into a format suitable for the target agent.
This may include:
- prompt sections
- structured tool payloads
- compact summaries
- reference lists

The adapter should preserve the minimal context philosophy.

Adapters should prefer IDs and compact references over large embedded structures.

## 3. Artifact Suggestion Preparation

The adapter may prepare artifact suggestions from agent output.

Typical examples:
- TaskCard suggestion
- DecisionCard suggestion
- ConstraintCard suggestion
- ProcedureCard suggestion
- IssueCard suggestion

The adapter may normalize the suggestion shape before it enters the runtime proposal flow.

## 4. Proposal Handoff

The adapter must hand off artifact suggestions through the approved proposal path.

This means the adapter may pass suggestions into:
```
runtime/inbox
↓
artifact_filter
↓
runtime/drafts
↓
canonical brain
```

The adapter must not bypass this flow.

The adapter submits artifact suggestions into the approved proposal entrypoint.

Downstream processing (artifact_filter, draft handling, and canonical acceptance)
is handled by reasoning-engine runtime components.

The adapter must not orchestrate or replicate these downstream steps.

---

## Canonical Acceptance Rule

Adapters may submit artifact proposals, but they do not decide canonical acceptance.

Final acceptance into canonical artifact storage is governed by the reasoning-engine
and must not be performed or influenced directly by adapters.

---

# Forbidden Responsibilities

Adapters must not perform responsibilities that belong to the reasoning engine or brain.

Adapters must not:
- write directly to canonical artifact directories
- bypass artifact_filter
- commit artifacts directly to Git history
- mutate canonical artifacts in place
- rebuild reasoning views independently
- redefine artifact schema
- introduce agent-specific fields into artifact objects
- modify reasoning-engine module boundaries

Adapters are integration layers, not governance layers.

---

# Minimal Adapter Behavior

A runtime adapter should remain small and explicit.
Adapters should prefer:
- simple functions
- explicit transformations
- deterministic formatting
- minimal helper usage

Adapters should avoid:
- deep abstraction hierarchies
- dynamic plugin systems
- hidden side effects
- speculative helper frameworks

The adapter layer should remain easy to inspect.

---

# Shared Utilities Boundary

The reasoning_adapters/common/ directory contains shared helper code.

These helpers must remain:
- stateless
- agent-agnostic
- side-effect free

They may support:
- context formatting
- prompt assembly
- artifact payload shaping

They must not perform:
- agent-specific branching
- storage writes
- Git operations
- benchmark orchestration
- background execution

Adapters may use **common/**, but **common/** must remain a pure shared utility layer.

Shared utilities may read and transform data, but must not perform any storage mutation.

They must not write to canonical artifact directories, runtime directories,
or interact with Git or persistence layers.

---

# Adapter Independence Rule

Adapters must not import from each other.

Forbidden examples:
```
codex/adapter.py importing claude/adapter.py
openclaw/adapter.py importing codex/adapter.py
```

All shared logic must flow through:
- reasoning_adapters/common/
- the reasoning-engine runtime
- this shared contract

This prevents cross-adapter entanglement.

---

# Runtime vs Benchmark Separation

Runtime adapters and benchmark adapters are separate layers.

Runtime adapters exist for real operational integration.

Benchmark adapters exist for controlled evaluation.

Rule:
benchmark adapters may depend on runtime adapters
runtime adapters must not depend on benchmark adapters

Runtime adapters must not contain:
- benchmark scoring logic
- benchmark case management
- benchmark-only prompt hacks
- evaluation harness behavior

This separation is mandatory.

---

# Artifact Shape Rule

If an adapter constructs or normalizes artifact suggestions, it must preserve the approved artifact schema.

Adapters must not introduce extra fields such as:
- metadata
- tags
- notes
- debug_info
- vendor fields
- agent-specific flags

The approved artifact schema is defined by the reasoning-engine runtime.

Adapters may only populate approved fields.

---

# Context Minimalism Rule

Adapters must preserve working context minimalism.

Adapters should not expand working context into:
- full artifact dumps
- reasoning traces
- large narrative summaries
- duplicated artifact bodies

Adapters may reformat context, but they must not inflate it.

The reasoning engine remains the source of truth for context preparation.

---

# Determinism Rule

Adapter behavior must remain deterministic.

Adapters should avoid:
- random ordering
- hidden prompt expansion
- non-deterministic field selection
- fallback behavior that silently changes output shape

If ordering is relevant, adapters should preserve deterministic ordering from the reasoning engine.

---

# Error Handling Rule

Adapters must fail explicitly on invalid input.

Adapters should raise or return explicit errors when:
- required context is missing
- artifact suggestion shape is invalid
- unsupported agent input is encountered
- required runtime modules cannot be reached

Adapters must not silently repair structural errors.

---

# Expected Interface Shape

This contract does not require one exact Python class shape.

However, all adapters should conceptually support functions in the following areas:
```
load_context(...)
build_agent_input(...)
extract_artifact_suggestion(...) → extract raw candidate from agent output
normalize_artifact_suggestion(...) → transform candidate into approved artifact schema
submit_suggestion(...)
```

The exact naming may differ, but the responsibilities must remain recognizable and separate.

---

# Suggested Responsibility Mapping

A typical adapter may look like this conceptually:
```
load_context(brain_root)
→ retrieve prepared working context

build_agent_input(working_context)
→ format compact agent-facing context

extract_artifact_suggestion(agent_output)
→ normalize candidate artifact suggestion

submit_suggestion(brain_root, artifact_suggestion)
→ hand off into approved proposal flow
```

This is a conceptual map, not a required exact API.

---

# Agent-Specific Freedom

Adapters may differ in:
- prompt formatting
- output parsing strategy
- local helper organization
- transport details
- agent-specific input structure

Adapters must not differ in:
- artifact schema
- proposal flow rules
- canonical storage rules
- reasoning-engine boundaries

This is the core distinction between implementation flexibility and architectural compatibility.

---

# README Usage

A per-agent README.md is optional.

It should be added only when the adapter becomes complex enough to require local documentation.

Examples of when a local README is useful:
- agent-specific parsing constraints
- non-obvious prompt formatting rules
- transport limitations
- execution caveats

Do not add placeholder READMEs without content value.

---

# Final Principle

A runtime adapter must remain a thin, deterministic, agent-specific bridge into the approved PR-Light runtime flow.

It must not become:
- a second reasoning engine
- a benchmark harness
- a storage manager
- a Git controller
- a policy layer

The reasoning adapter layer exists to connect agents to Persistent Reasoning Light without weakening the architecture.

---
