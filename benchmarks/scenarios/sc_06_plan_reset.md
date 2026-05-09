# Plan Reset and Re-Alignment (sc_6)

## Purpose

This scenario tests whether a system can detect that its current plan is invalid,
explicitly abandon that plan, and rebuild a new one aligned with updated requirements.

## What this scenario tests

- invalidation recognition
- clean reset behavior
- prevention of old-plan leakage
- retention of the new valid plan
- resistance to mixed-plan collapse

## Canonical plan units

### Old plan (invalid after reset)
- `P1` = define REST endpoints
- `P2` = define request/response schemas
- `P3` = add centralized authentication
- `P4` = add server-side rate limiting
- `P5` = add server-side pagination
- `P6` = add central database persistence

### New plan (valid after reset)
- `N1` = local-first data model
- `N2` = peer/device sync protocol
- `N3` = conflict resolution strategy
- `N4` = offline authentication approach
- `N5` = local pagination/query strategy
- `N6` = device-level persistence model

Total units: `12`

## Structure

- initial old plan
- extension pressure
- explicit invalidation event
- reset and rebuild
- final validation

## Human-verifiable check

A human can verify quickly:

- did the system acknowledge invalidation?
- are old-plan units still leaking into the final active plan?
- are all new-plan units present?
- did the final plan fully shift to the new requirement?

## Required exact output headings

- `CHECKPOINT 0 - INITIAL PLAN`
- `CHECKPOINT 5 - EXTENDED PLAN`
- `CHECKPOINT 10 - INVALIDATED PLAN`
- `CHECKPOINT 15 - RESET PLAN`
- `CHECKPOINT 20 - FINAL PLAN`
- `FINAL RETAINED UNITS`
- `FINAL LOST UNITS`

## Rules

- preserve exact unit ids only
- do not rename units
- old-plan units may appear historically, but must not remain as active final solution units
- final active plan must be built around N1-N6
- no extra unit ids allowed

## Ghost accounting

Ghost units:

- any unit ids outside P1-P6 and N1-N6
- indicate hallucinated planning elements

## Why this scenario matters

This scenario captures a major real-world reasoning failure mode:

> the system notices change, but still drags obsolete plan fragments forward.

Baseline systems often:

- partially merge incompatible plans
- fail to reset cleanly
- keep using invalid assumptions

PR systems should:

- preserve reset boundaries more clearly
- retain the new active plan better
- avoid old-plan leakage

## Interpretation readiness

This scenario defines an explicit reset-boundary structural contract,
but active interpretation support is still deferred.

Current interpretation status:

- retention: deferred
- correctness: unsupported
- ghost: deferred
