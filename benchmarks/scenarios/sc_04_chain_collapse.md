# Reasoning Chain Collapse (sc_4)

## Purpose

This scenario tests whether a system can preserve a long dependency chain
under expansion, compression, and reconstruction pressure.

## What this scenario tests

- dependency chain retention
- resistance to chain collapse
- reconstruction after compression
- order preservation
- ghost step generation

## Canonical chain

`S1 → S2 → S3 → ... → S15`

Total steps: `15`

Each step = ~6.7%

## Structure

- forward expansion (structure growth)
- compression (information loss pressure)
- reconstruction (recovery)
- reverse (order integrity)

## Human-verifiable check

A human can verify quickly:

- all 15 steps present?
- order preserved?
- any steps missing?
- any extra steps?

## Rules

- preserve exact step ids only
- no renaming
- no skipping steps
- no new steps

## Ghost accounting

Ghost steps:

- any step id not in S1–S15
- indicates hallucinated chain elements

## Why this scenario matters

This scenario exposes a critical failure mode:

> systems often collapse structured reasoning into vague summaries

PR systems should:

- retain full chain length
- preserve dependencies
- reconstruct accurately after compression

Baseline systems typically:

- drop steps
- merge steps
- lose ordering
- introduce ghost steps

## Interpretation readiness

This scenario defines an explicit chain-retention structure,
but active scenario-specific interpretation support is still deferred.

Current interpretation status:

- retention: deferred
- correctness: unsupported
- ghost: deferred
