# Temporal Rule Propagation (sc_11)

## Purpose

This scenario tests whether a system can correctly propagate state through a small dependency graph under overlapping temporal rules.

It is intentionally compact but cognitively adversarial.

## What this scenario tests

- temporal rule activation
- dependency propagation
- overwrite vs propagation handling
- resistance to shortcut reasoning
- exact final-state correctness

## Rules

The scenario uses these exact rules:

1. `A always equals B until step 4`
2. `C always equals D until step 2`
3. `B always equals C starting from step 2`

## Initial state

- `A = 0`
- `B = 0`
- `C = 0`
- `D = 0`

## Updates

1. `D = C + 1`
2. `C = 2`
3. `D = 3`

## Canonical final state

- `A = 2`
- `B = 2`
- `C = 2`
- `D = 3`

Final answer:

- `FINAL_A = 2`

## Total canonical units

The scenario tracks 4 canonical state variables:

- `A`
- `B`
- `C`
- `D`

This means:

- each retained variable = `25%`
- full retention = `100%`

## Correctness

Correctness is the primary signal in this scenario.

A system may retain all variable names while still applying temporal rules incorrectly.

This scenario is designed to expose exactly that failure mode.

## Required exact output headings

- `CHECKPOINT 0 - INITIAL STATE`
- `CHECKPOINT 2 - AFTER STEP 1`
- `CHECKPOINT 3 - AFTER STEP 2`
- `CHECKPOINT 4 - AFTER STEP 3`
- `CHECKPOINT 5 - FINAL STATE`
- `FINAL RETAINED VARIABLES`
- `FINAL LOST VARIABLES`

## Output rules

Under each checkpoint:

- use exact slot lines only
- format: `NAME: VALUE`
- no extra commentary inside checkpoint sections
- no renamed variables
- no additional variables beyond:
  - `A`
  - `B`
  - `C`
  - `D`
  - `FINAL_A` (final checkpoint only)

## Human-verifiable check

A human can verify quickly:

- whether the final value of `A` is `2`
- whether the full final state is:
  - `A = 2`
  - `B = 2`
  - `C = 2`
  - `D = 3`

## Ghost accounting

Ghost variables are:

- any variables not in the allowed set:
  - `A`
  - `B`
  - `C`
  - `D`
  - `FINAL_A`

Ghost remains separate from retention and correctness.

## Why this scenario matters

This scenario exposes a common LLM failure mode:

> rules that look global are applied at the wrong time,
> and updates are not propagated consistently.

Weak systems often fail by:

- applying a rule too early
- applying a rule too long
- mixing static equality with dynamic updates
- preserving variable names while corrupting values

This makes the scenario small, exact, and high-signal.