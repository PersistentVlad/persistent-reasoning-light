# Gemini Execution Contract v1

Persistent Reasoning Light — Benchmark Mode

---

## 1. Purpose

Define the Gemini-specific execution profile for benchmarked-agent invocation in the Persistent Reasoning Light benchmark subsystem.

This profile is intended primarily for low-cost benchmark-system debugging and operational validation.
It does not redefine the role of final architectural validation on the intended target execution provider.

This contract is a **provider-specific specialization** of:

- `agent_execution_contract.md`

It defines only the Gemini-specific execution delta.

All general benchmarked-agent invariants remain in force.

---

## 2. Governing Contract

This contract inherits all requirements from:

- `agent_execution_contract.md`

If any statement in this document appears weaker than the general contract, the general contract takes precedence.

---

## 3. Provider Identity

This execution profile applies to:

> Gemini-backed benchmark execution

This contract describes how a Gemini-backed executor participates in the benchmark system.

It does **not** redefine:

- benchmark architecture
- adapter boundaries
- event-first derivation
- scaffold compatibility
- no-shortcut rule

---

## 4. Invocation Boundary

Gemini-backed model invocation MUST still occur only through the benchmark adapter.

Even though execution transport uses Gemini infrastructure, benchmark invocation remains:

> adapter-controlled only

Forbidden:

- direct Gemini API calls from runners
- direct Gemini API calls from benchmark tools
- direct Gemini API calls from comparison/reporting layers
- hidden execution paths outside the adapter

---

## 5. Input Delivery Rules

The Gemini-backed executor receives:

> one final prompt string only

The prompt must already be fully constructed by the adapter.

The executor MUST NOT:

- add hidden context
- append hidden repository state
- infer filesystem context
- read arbitrary files
- depend on ambient shell state
- depend on unstated environment state beyond explicit executor configuration

All available benchmark context must be embedded explicitly in the prompt.

---

## 6. Output Delivery Rules

The Gemini-backed executor MUST return:

> one final raw textual response

The returned output must represent one complete response, not a concatenation of multiple partial responses.

The executor must expose the response as:

- one contiguous string
- non-empty
- bounded by output limits

The executor MUST NOT return:

- streaming fragments as benchmark output
- multiple response channels
- tool outputs
- structured response containers as the benchmark contract output

Any provider-native response structure must be normalized by the executor into one raw string before it reaches the adapter.

---

## 7. Tool / Capability Policy

Benchmark execution through the Gemini-backed executor MUST NOT enable benchmark-visible tool use.

Forbidden for benchmarked-agent execution:

- repository tools
- filesystem tools
- command execution tools
- hidden external tools
- benchmark-internal helper tools
- function calling or equivalent capability paths that alter benchmark semantics
- any tool-enabled path that gives the model implicit extra context

If the provider supports tools or advanced capabilities natively, they must remain disabled for benchmark mode.

---

## 8. Transport-Specific Rules

The Gemini-backed execution path MUST use:

- explicit provider API access
- non-streaming execution
- one execution attempt only
- explicit timeout handling
- explicit output-size enforcement

The Gemini-specific execution layer may define:

- model name handling
- API key handling
- timeout propagation
- output normalization rules
- transport-level failure mapping

But it must preserve the general contract.

---

## 9. Output Normalization Requirement

Gemini-backed output may contain provider-specific formatting, verbosity, or wrapper text.

Therefore, the Gemini-backed execution layer MUST normalize provider output into:

> exactly one raw benchmark string

This normalization must:

- preserve the semantic content of the provider response
- avoid introducing hidden benchmark logic
- avoid splitting output into multiple benchmark-visible units
- avoid silently manufacturing structured artifact data

Normalization MUST NOT alter semantic meaning beyond removing provider-native envelope/formatting.

The adapter remains responsible for any optional artifact extraction.

---

## 10. Retry / Streaming Policy

The Gemini-backed executor MUST NOT:

- retry implicitly
- stream benchmark output
- reconstruct benchmark output from multiple streamed fragments as a contract-visible behavior

The benchmark sees one execution attempt and one final output string only.

---

## 11. Timeout Policy

Timeout must be enforced explicitly by the Gemini-backed execution layer and/or adapter boundary.

On timeout, the execution path must fail explicitly so that the adapter can emit:

- `task_failed`
- with timeout-related reason metadata

Timeout handling must not silently retry or silently extend execution.

If provider timeout semantics are imperfect or transport-dependent, the benchmark system still treats timeout as an execution boundary.

---

## 12. Output Size Policy

The Gemini-backed execution layer must enforce explicit limits for:

- maximum output characters
- maximum output tokens (if configured)

If provider output exceeds the configured output contract, it must be treated as execution failure according to the general contract.

Silent truncation is discouraged unless explicitly documented and contract-safe.
Failure is preferred to silent mutation of benchmark output.

---

## 13. Failure Mapping

The Gemini-backed execution layer may encounter provider-specific failures such as:

- transport/API failure
- authentication failure
- timeout
- empty response
- whitespace-only response
- malformed non-text response
- oversized output

These failures must be surfaced in a way that allows the adapter to preserve:

- event-first behavior
- explicit failure signaling
- deterministic result derivation from events

Provider-specific failures must not bypass the benchmark pipeline.

---

## 14. Determinism Clarification

This contract does **not** require Gemini to produce identical outputs across independent invocations.

The required invariant is:

> given the same prompt and the same captured Gemini output,  
> adapter handling, event emission, and result derivation remain deterministic

The Gemini-backed execution layer must not introduce nondeterministic post-processing.

---

## 15. Scaffold Compatibility

If scaffold mode is used with the Gemini-backed adapter:

- scaffold output may replace real provider output

But scaffold mode still must preserve:

- adapter-only execution boundary
- event emission
- event-derived result generation
- no result construction inside adapter

---

## 16. Provider-Specific Caution

Gemini-backed execution may differ in formatting style, verbosity, or output consistency from other providers.

The benchmark system must not be tuned in a way that weakens general benchmark invariants merely to accommodate provider-specific quirks.

If Gemini-specific handling is needed, it must remain:

- executor-local
- contract-compliant
- non-invasive to the benchmark architecture

---

## Final Principle

Gemini provides the execution transport.

The benchmark adapter controls the benchmark boundary.

The benchmark system still evaluates reasoning only through events.