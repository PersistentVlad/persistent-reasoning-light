# Scenario: Context Compression Under Constraints

## Scenario ID
sc_17_context_compression

## Description
This scenario tests the agent's ability to compress an expanding reasoning context
into a minimal representation without losing essential information.

It simulates a realistic constraint:
as tasks grow in complexity, the available context must be reduced or structured
in a more efficient form to remain usable.

---

## Core Challenge

The agent must:

1. Build an initial structured solution
2. Expand it with additional features
3. Compress the accumulated context into a compact form
4. Continue the task using only the compressed representation

---

## Expected Behavior

A robust agent should:

- retain all critical structural elements (entities, relationships, decisions)
- remove redundancy without losing meaning
- preserve the ability to reconstruct the solution
- maintain consistency between pre- and post-compression reasoning

---

## Failure Modes

Typical failures include:

- losing important components during compression
- over-compressing into vague or unusable summaries
- introducing inconsistencies after reconstruction
- being unable to continue meaningfully from compressed context

---

## Why This Matters

Context compression is essential for:

- long-running agent systems
- memory-constrained environments
- scalable reasoning architectures

This scenario directly evaluates:

- compression quality
- information retention
- reconstruction fidelity

---

## Notes for Benchmarking

This scenario is especially relevant for metrics such as:

- memory_compression_ratio
- knowledge_retention_rate
- context_growth_rate
- structural_integrity_score

It highlights differences between:

- baseline agents (often degrade under compression)
- PR-Light systems (designed for structured minimal context)
- PR-Light + reasoning brain systems (potentially more stable compression anchors)

---

## Category

context_compression_efficiency