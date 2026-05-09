# Digit Span + N-Back Hybrid (sc_5)

## Purpose

This scenario tests working memory under transformation and temporal pressure.

It combines:

- digit span (memory)
- transformations (state mutation)
- N-back (temporal access)
- recovery (reconstruction)

## What this scenario tests

- memory retention across transformations
- correctness of transformations
- temporal recall (N-back)
- reconstruction after state loss
- resistance to drift and ghost digits

## Canonical sequence

`3 7 2 9 4 6 8 1 5 0`

Total digits: `10`

Each digit = `10%`

## Structure

- forward transformations (mutation pressure)
- N-back reasoning (temporal pressure)
- simulated state loss
- reconstruction of original sequence

## Human-verifiable check

At the end:

- does the sequence match the original?
- are all digits present?
- is the order correct?
- are any digits missing or duplicated?

## Rules

- preserve digits 0–9 only
- no new digits
- no loss of digits
- order matters
- final sequence must match original exactly

## Ghost accounting

Ghost digits:

- any digit not in canonical sequence
- duplicated or extra digits
- artifacts introduced during transformation

## Why this scenario matters

This scenario combines multiple failure modes:

- memory drift
- incorrect transformation tracking
- temporal confusion (N-back errors)
- inability to recover original state

Baseline systems typically:

- lose ordering
- corrupt digits
- fail to reconstruct original sequence

PR systems should:

- maintain stable memory
- recover sequence accurately
- resist transformation drift

## Interpretation readiness

This scenario already defines sequence, correctness, and ghost metadata.

Current interpretation status:

- retention: deferred
- correctness: deferred
- ghost: deferred

The contract is structurally aligned for later interpretation work,
but this hybrid sequence variant is not engine-supported yet.
