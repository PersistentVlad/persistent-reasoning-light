# Move Clock Hands (sc_8)

## Purpose

This scenario tests whether a system can preserve a cyclic clock state under:

- forward movement
- reverse-trigger events
- asymmetric oscillation
- sign switching at B
- exact return-to-origin correction

It is intentionally designed to break shortcut reasoning.

## Core setup

- Initial state: `A = 12:00`
- One step = `60 minutes`
- `POS_A` = initial A
- `POS_B` = forward B

## Rules

- When you arrive at `B`, change the sign of `+15 minutes` and `-15 minutes`
- On each reverse, move the minute hand by `15 minutes` in the direction of forward or backward movement
- Keep the clock state exact at all times

## Movement scheme

- `A -> B`
- reverse
- `2 steps backward`
- reverse
- `3 steps forward`
- reverse
- `5 steps backward`
- then apply the correct constant to return to initial `A`

## What this scenario tests

- cyclic state retention
- event-triggered sign switching
- reverse-phase state mutation
- asymmetric oscillation handling
- return-to-origin correctness
- resistance to shortcut or checkpoint guessing

## Human-verifiable check

A human can verify quickly:

- whether the final state is exactly `12:00`
- whether `HOUR_HAND = 12`
- whether `MINUTE_HAND = 12`
- whether the reported correction constant is the exact one required to return to `A`

## Required exact output headings

- `CHECKPOINT 0 - INITIAL CLOCK`
- `CHECKPOINT 10 - AFTER FORWARD`
- `CHECKPOINT 12 - AFTER PARTIAL REVERSE`
- `CHECKPOINT 15 - AFTER FORWARD AGAIN`
- `CHECKPOINT 20 - AFTER BACKWARD AGAIN`
- `CHECKPOINT 21 - FINAL CLOCK`
- `FINAL RETAINED CLOCK UNITS`
- `FINAL LOST CLOCK UNITS`

## Output rules

Under each checkpoint:

- use exact lines only
- format: `NAME: VALUE`
- no extra commentary inside checkpoint sections
- no invented state variables

Required names:

- `TIME`
- `HOUR_HAND`
- `MINUTE_HAND`
- `CONST_MINUTES`
- `POS_A`
- `POS_B`

## Correctness

Correctness is separate from retention.

A system may:

- preserve all state names
- but still compute the wrong clock state or the wrong return constant

This scenario is designed to expose exactly that failure.

## Ghost accounting

Ghost units are:

- any extra state-like identifiers not in the allowed set

Ghost remains separate from retention and correctness.

## Why this scenario matters

This scenario is not difficult because of arithmetic.
It is difficult because of:

- conditional event handling
- state mutation during reverse phases
- sign switching at a trigger point
- return-to-origin under asymmetric movement

Weak systems often fail by:

- treating the path as symmetric when it is not
- missing sign changes
- misapplying reverse-trigger minute movement
- guessing the final state from memory instead of tracking the trajectory

This makes the scenario small, exact, and high-signal.

## Interpretation readiness

- retention: deferred
- correctness: deferred
- ghost: deferred

The scenario contract is explicit and execution-ready, but scenario-specific interpretation support remains deferred.
