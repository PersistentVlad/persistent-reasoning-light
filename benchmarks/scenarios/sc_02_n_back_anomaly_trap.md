# N-Back with Anomaly Trap (sc_2)

## Purpose

This scenario tests temporal memory retention under pressure using a 3-back rule,
combined with a deliberately injected anomaly segment.

It evaluates whether the system can:

- maintain a correct temporal reference
- resist adopting incorrect intermediate inputs
- reconstruct the original sequence after disruption

## What this scenario tests

- temporal memory consistency (N-back)
- resistance to local corruption (anomaly trap)
- sequence reconstruction ability
- ghost element generation

## Canonical sequence

`A B C D E F G H I J K L M N O P Q R S T`

Total elements: `20`

## Structure

The scenario consists of:

- 10 forward reasoning steps (3-back)
- 1 anomaly injection step
- 10 reverse reconstruction steps

## The anomaly trap

At one step, the sequence is presented as:

`K X Q Z P`

This is intentionally incorrect.

The system must:

- detect or ignore this anomaly
- continue reasoning using the original sequence
- avoid incorporating false elements (X, Q, Z)

## Human-verifiable check

At the end:

- does the final sequence match the original?
- are any original elements missing?
- are any new elements introduced?

## Required exact headings

- `CHECKPOINT 0 - INITIAL SEQUENCE`
- `CHECKPOINT 5 - FORWARD`
- `CHECKPOINT 10 - FORWARD`
- `CHECKPOINT 15 - REVERSE`
- `CHECKPOINT 20 - FINAL`
- `FINAL RETAINED ELEMENTS`
- `FINAL LOST ELEMENTS`

## Rules

- preserve only canonical elements A–T
- do not adopt altered anomaly elements
- no new elements allowed
- maintain sequence integrity

## Ghost accounting

Ghost elements are:

- any elements not in A–T
- especially anomaly-derived values (X, Z, etc.)

Ghost is tracked separately and indicates drift or hallucination.

## Why this scenario matters

This is one of the strongest tests of temporal reasoning.

It reveals:

- memory drift over time
- susceptibility to incorrect intermediate inputs
- inability to reconstruct prior state

PR systems should:

- resist anomaly adoption
- maintain correct temporal references
- reconstruct the original sequence more reliably

Baseline systems typically:

- adopt the anomaly
- lose track of original sequence
- generate ghost elements

## Interpretation readiness

This scenario already defines explicit sequence and ghost metadata.

Current interpretation status:

- retention: deferred
- correctness: unsupported
- ghost: deferred

The metadata is structurally aligned for a later interpretation refactor,
but this exact sequence variant is not engine-supported yet.
