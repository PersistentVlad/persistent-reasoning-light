
# OpenAI Execution Contract v1

Persistent Reasoning Light — Benchmark Mode

---

## 1. Purpose

Define the OpenAI-specific execution profile for benchmarked-agent invocation in the Persistent Reasoning Light benchmark subsystem.

This contract is a **provider-specific specialization** of:

- `agent_execution_contract.md`

It defines only the OpenAI-specific execution delta.

All general benchmarked-agent invariants remain in force.

---

## 2. Governing Contract

This contract inherits all requirements from:

- `agent_execution_contract.md`

If any statement in this document appears weaker than the general contract, the general contract takes precedence.

---

## 3. Provider Identity

This execution profile applies to:

> OpenAI-backed benchmark execution

This contract describes how an OpenAI-backed executor participates in the benchmark system.

It does **not** redefine:

- benchmark architecture
- adapter boundaries
- event-first derivation
- scaffold compatibility
- no-shortcut rule

---

## 4. Invocation Boundary

OpenAI-backed model invocation MUST still occur only through the benchmark adapter.

Even though execution transport uses OpenAI infrastructure, benchmark invocation remains:

> adapter-controlled only

Forbidden:

- direct OpenAI API calls from runners
- direct OpenAI API calls from benchmark tools
- direct OpenAI API calls from comparison/reporting layers
- hidden execution paths outside the adapter

---

## 5. Input Delivery Rules

The OpenAI-backed executor receives:

> one final prompt string only

The prompt must already be fully constructed by the adapter.

The executor MUST NOT:

- add hidden context
- append hidden repository state
- infer filesystem context
- read arbitrary files
- depend on ambient shell state
- depend on unstated environment state beyond explicit executor configuration
- reuse cached responses across benchmark runs

---

## 6. Output Delivery Rules

The OpenAI-backed executor MUST return:

> one final raw textual response

The executor must expose the response as:

- one contiguous string
- non-empty
- bounded by output limits

The output MUST represent a single complete response, not a concatenation of multiple responses.

The executor MUST NOT return:

- streaming fragments as benchmark output
- multiple response channels
- tool outputs
- structured response containers as the benchmark contract output

Normalization MUST NOT alter semantic content.

Any provider-native response structure must be normalized by the executor into one raw string before it reaches the adapter.

---

## 7. Transport / SDK Requirements

The OpenAI-backed execution path MUST use:

- official OpenAI-supported API access
- non-streaming execution
- no benchmark-visible tool invocation

The OpenAI-specific execution layer may define:

- model name handling
- API key handling
- timeout propagation
- output normalization rules
- transport-level failure mapping

But it must preserve the general contract.

---

## 8. Tool Use Policy

Benchmark execution through the OpenAI-backed executor MUST NOT enable benchmark-visible tool use.

Forbidden for benchmarked-agent execution:

- repository tools
- filesystem tools
- command execution tools
- hidden external tools
- benchmark-internal helper tools
- any tool-enabled path that changes the benchmark semantics

If the provider supports tools natively, they must remain disabled for benchmark mode.

---

## 9. Retry / Streaming Policy

The OpenAI-backed executor MUST NOT:

- retry implicitly
- stream benchmark output
- reconstruct benchmark output from multiple streamed fragments as a contract-visible behavior

The benchmark sees one execution attempt and one final output string only.

---

## 10. Timeout Policy

Timeout must be enforced explicitly by the OpenAI-backed execution layer and/or adapter boundary.

Timeout MUST be enforced at least once before returning control to the adapter.

On timeout, the execution path must fail explicitly so that the adapter can emit:

- `task_failed`
- with timeout-related reason metadata

Timeout handling must not silently retry or silently extend execution.

---

## 11. Output Size Policy

The OpenAI-backed execution layer must enforce explicit limits for:

- maximum output characters
- maximum output tokens (if configured)

If provider output exceeds the configured output contract, it must be treated as execution failure according to the general contract.

---

## 12. Failure Mapping

The OpenAI-backed execution layer may encounter provider-specific failures such as:

- transport/API failure
- authentication failure
- timeout
- empty response
- malformed non-text response
- oversized output

These failures must be surfaced in a way that allows the adapter to preserve:

- event-first behavior
- explicit failure signaling
- deterministic result derivation from events

Provider-specific failures must not bypass the benchmark pipeline.

---

## 13. Scaffold Compatibility

If scaffold mode is used with the OpenAI-backed adapter:

- scaffold output may replace real provider output

But scaffold mode still must preserve:

- adapter-only execution boundary
- event emission
- event-derived result generation
- no result construction inside adapter

---

## 14. Future Split Note

This contract defines the **current OpenAI-backed benchmark execution profile**.

If multiple OpenAI-based agent profiles emerge in the future, this contract may be split into more specific execution contracts.

---

## Final Principle

OpenAI provides the execution transport.

The benchmark adapter controls the benchmark boundary.

The benchmark system still evaluates reasoning only through events.