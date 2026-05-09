# Structural Retention (sc_1)

## Purpose

This is the canonical human-verifiable structural retention scenario.

Its role is to measure how well a system preserves a fixed inventory of literal units
across repeated restructuring and reverse reconstruction.

This scenario is designed to be:

- strict
- count-based
- machine-readable
- human-checkable in seconds

## What this scenario tests

- retention of fixed exact unit ids
- resistance to structural drift across many transformations
- ability to reconstruct toward the original state
- resistance to ghost unit generation

## Fixed unit inventory

### Facts
`F1`, `F2`, `F3`, `F4`, `F5`, `F6`, `F7`, `F8`, `F9`, `F10`

### Dependencies
`D1`, `D2`, `D3`, `D4`, `D5`, `D6`

### Constraints
`C1`, `C2`, `C3`, `C4`

Total units: `20`

This means:

- each unit = `5%`
- full retention = `100%`

## Structure

The scenario applies:

- 10 forward restructuring steps
- 10 reverse reconstruction steps

The goal is not to preserve formatting.
The goal is to preserve the exact unit inventory.

## Human-verifiable check

The scenario starts from a fixed canonical inventory
and should end by reconstructing toward that original state.

A human can check quickly:

- are the original units still present?
- are any units missing?
- did any extra unit ids appear?
- does the final state still match the canonical inventory?

## Required exact output headings

- `CHECKPOINT 0 - INITIAL`
- `CHECKPOINT 5 - FORWARD`
- `CHECKPOINT 10 - FORWARD`
- `CHECKPOINT 15 - REVERSE`
- `CHECKPOINT 20 - FINAL`
- `FINAL RETAINED UNITS`
- `FINAL LOST UNITS`

## Rules

- preserve exact unit ids only
- no renaming
- no paraphrase
- no semantic substitution
- no extra unit ids
- final lost units must be explicit or `NONE`

## Ghost accounting

Ghost tracking in this scenario is strict.

Ghost units are:

- extra unit-like ids
- inside validated exact sections only
- matching the configured token pattern
- not part of the canonical inventory

Ghost remains separate from retained/lost accounting.

## Why this scenario matters

This is the simplest strong proof that PR helps preserve structure over time.

If PR works, it should show:

- slower retention loss
- fewer ghost units
- better return toward the original state

If a system drifts, this scenario makes that drift visible immediately and countably.

## Interpretation readiness

Current interpretation status:

- retention: enabled
- correctness: deferred
- ghost: enabled

This is the canonical structural scenario for active strict retention and ghost parsing.
