# Trail Making (sc_7)

## Purpose

This scenario tests whether a system can preserve an alternating ordered trail
under forward restructuring, local disruption, recovery, and reverse restoration.

It is adapted from the logic of trail-making tasks:
the system must preserve sequence integrity while alternating across two dimensions.

## What this scenario tests

- ordered dependency retention
- alternating sequence preservation
- resistance to local disruption
- recovery of canonical order
- reverse restoration accuracy
- ghost pair generation

## Canonical trail

`1-A 2-B 3-C 4-D 5-E 6-F 7-G 8-H 9-I 10-J`

Total pairs: `10`

Each pair = `10%`

## Structure

The scenario consists of:

- forward progression
- local disruption with an incorrect fragment
- recovery to canonical order
- reverse and return-to-origin validation

## Human-verifiable check

A human can verify quickly:

- are all 10 canonical pairs present?
- is the order correct?
- were any pairs altered?
- did any non-canonical pairs appear?

## Disruption trap

The scenario injects an incorrect middle fragment:

`5-G 6-E 7-F`

This fragment is intentionally invalid.

The system must:

- reject it as canonical
- recover the original trail
- avoid carrying it into the final state

## Required exact output headings

- `CHECKPOINT 0 - INITIAL TRAIL`
- `CHECKPOINT 5 - FORWARD TRAIL`
- `CHECKPOINT 10 - DISRUPTED TRAIL`
- `CHECKPOINT 15 - RECOVERED TRAIL`
- `CHECKPOINT 20 - FINAL TRAIL`
- `FINAL RETAINED PAIRS`
- `FINAL LOST PAIRS`

## Rules

- preserve exact canonical pairs only
- no renaming
- no substitutions
- no non-canonical pairs
- final trail must match the original exactly

## Correctness

Correctness is evaluated independently from retention.

A system may:

- retain most pairs
- but restore them in the wrong order

This is why the final canonical trail line is checked exactly.

## Ghost accounting

Ghost pairs are:

- any pair not in the canonical set
- especially disruption-derived or invented pairs

Ghost remains separate from retained/lost accounting.

## Why this scenario matters

This scenario exposes a common failure mode:

> the system remembers elements, but loses the rule that connects them in the correct order.

Baseline systems often:

- accept the disrupted fragment
- lose alternating order
- introduce ghost pairs
- fail to return to canonical order

PR systems should:

- preserve ordered structure more reliably
- resist disruption
- recover the exact canonical trail

## Interpretation readiness

This scenario already defines ordered-trail retention, correctness, and ghost metadata.

Current interpretation status:

- retention: deferred
- correctness: deferred
- ghost: deferred

The scenario contract is explicit, but active engine support for this ordered-trail variant remains deferred.
