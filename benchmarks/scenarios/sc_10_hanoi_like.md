# Stack Transfer with Constraints (sc_10)

## Purpose

This scenario tests whether a system can preserve and manipulate a constrained multi-stack state
under forward operations, constraint violations, and reverse reconstruction.

It is a constraint-driven reasoning task with reversible state transitions.

## What this scenario tests

- constraint-aware reasoning
- state transition correctness
- preservation of ordering rules
- resistance to invalid shortcuts
- reversibility of reasoning steps
- recovery to canonical initial state

## Canonical initial state

- `STACK_A = DISC_4 DISC_3 DISC_2 DISC_1`
- `STACK_B = EMPTY`
- `STACK_C = EMPTY`

## Rules

- only one disc may be moved at a time
- a larger disc may never be placed on a smaller disc
- stacks must always remain valid

## Structure

The scenario includes:

- forward valid moves
- illegal move temptation (trap)
- continued constrained reasoning
- reverse reconstruction to initial state

## Human-verifiable check

A human can verify:

- are all discs present?
- are discs ordered correctly?
- are stacks valid?
- does the final state match the original?

## Required exact output headings

- `CHECKPOINT 0 - INITIAL STATE`
- `CHECKPOINT 5 - FORWARD STATE`
- `CHECKPOINT 10 - FORWARD STATE`
- `CHECKPOINT 15 - RECOVERED STATE`
- `CHECKPOINT 20 - FINAL STATE`
- `FINAL RETAINED UNITS`
- `FINAL LOST UNITS`

## Correctness

Correctness is defined by:

- valid stack ordering
- adherence to movement constraints
- exact final reconstruction

## Ghost accounting

Ghost units are:

- non-existent discs
- invalid stack identifiers
- illegal configurations

## Why this scenario matters

This scenario exposes a key reasoning dimension:

> not just remembering state, but obeying rules under pressure

Baseline systems often:

- accept invalid shortcuts
- violate constraints
- fail to reverse correctly

PR systems should:

- preserve constraint rules explicitly
- resist invalid moves
- reconstruct valid states reliably