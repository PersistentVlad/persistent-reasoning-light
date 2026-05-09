# Math State Loss and Recovery (sc_3)

## Purpose

This scenario tests whether a system can preserve and recover an exact mathematical state
after forward computation, state loss, and recovery pressure.

It is one of the canonical scenarios for the correctness layer.

## What this scenario tests

- exact state-slot retention
- arithmetic correctness
- recovery after state loss
- separation between retained structure and retained correctness

## Core challenge

The system must:

1. build a long exact math chain
2. preserve named intermediate slots
3. survive a simulated state-loss event
4. reconstruct the full chain exactly
5. return the final canonical fraction form

## Canonical slot chain

- `PRODUCT_1 = 23 * 47 = 1081`
- `PRODUCT_2 = 58 * 19 = 1102`
- `COMBINED_SUM = 1081 + 1102 = 2183`
- `AFTER_SUBTRACTION = 2183 - 365 = 1818`
- `AFTER_DIVISION = 1818 / 3 = 606`
- `AFTER_ADDITION = 606 + 51 = 657`
- `AFTER_MULTIPLICATION = 657 * 2 = 1314`
- `AFTER_REDUCTION = 1314 / 3 = 438`
- `FINAL_NUMERATOR = 438 - 1 = 437`
- `FINAL_RESULT = 437/7`

`FINAL_RESULT` must remain in exact fraction form.

## Total canonical units

There are `10` named math-state units.

This means:

- each retained slot = `10%`
- full retention = `100%`

## Correctness

Correctness is evaluated independently of retention.

A system may:

- retain all slot names but assign incorrect values
- preserve structure while losing correctness
- recover only part of the exact chain

This is why the scenario reports:

- `retention_percent`
- `correctness_percent`
- `retention_correctness_gap`

## Required exact output headings

- `CHECKPOINT 0 - INITIAL STATE`
- `CHECKPOINT 5 - FORWARD STATE`
- `CHECKPOINT 10 - FORWARD STATE`
- `CHECKPOINT 15 - RECOVERED STATE`
- `CHECKPOINT 20 - FINAL STATE`
- `FINAL RETAINED UNITS`
- `FINAL LOST UNITS`

## Output rules

Under each checkpoint section:

- use exact slot lines only
- format: `SLOT_NAME: VALUE`
- no extra commentary inside sections
- no renamed slots
- no decimal replacement for `FINAL_RESULT`

## Human-verifiable check

A human can verify in seconds:

- are all 10 slot names present?
- are the values exactly correct?
- is `FINAL_RESULT` still `437/7`?
- are any slots lost?

## Why this scenario matters

This scenario exposes a very important failure mode:

> a system may preserve the shape of reasoning
> while losing the exact correctness of the state.

PR should help the system:

- retain exact intermediate values longer
- recover state more reliably
- reduce collapse under state loss

## Interpretation readiness

Current interpretation status:

- retention: enabled
- correctness: enabled
- ghost: unsupported

This is the canonical active math scenario for exact slot-based correctness checking.
