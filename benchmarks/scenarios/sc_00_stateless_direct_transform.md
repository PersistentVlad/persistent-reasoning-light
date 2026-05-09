# Stateless Direct Transform (sc_0)

## Purpose

This scenario serves as a control baseline.

It verifies that persistent reasoning (PR) does not introduce artificial gains
in tasks that are purely local and stateless.

## What is being tested

- Direct transformation correctness
- Stability across repeated independent steps
- Absence of unintended cross-step influence

## Scenario properties

- Each step is independent
- No memory reuse is required
- No state accumulation is allowed
- No benefit from persistence is expected

## Expected behavior

All modes should perform similarly:

- BASELINE ~= PR_EPHEMERAL ~= PR_LIGHT_BRAIN

Any measurable improvement from PR modes should be considered suspicious
and investigated.

## Human verification

Each step is trivial to verify:

- snake_case -> camelCase
- no ambiguity
- no interpretation required

## Failure modes

- Incorrect transformation (formatting errors)
- Leakage between steps (unexpected carry-over)
- Artificial improvement from PR modes

## Why this scenario matters

This scenario establishes a neutral reference point.

It ensures that observed gains in other scenarios are due to:

- memory retention
- reasoning continuity
- structural persistence

and not due to benchmark bias or unintended advantages.

## Interpretation readiness

This scenario is intentionally a control.

Current interpretation status:

- retention: unsupported
- correctness: unsupported
- ghost: unsupported

It should not be treated as a retention-style scenario in later interpretation dispatch.
