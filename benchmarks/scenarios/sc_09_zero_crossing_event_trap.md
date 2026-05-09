# Zero Crossing Event Trap (sc_12)

## Purpose

This scenario tests event-driven reasoning under dynamic state mutation.

It combines:

- position updates
- zero-crossing detection
- conditional state mutation
- modifier sign inversion

## Core Rule

Each time the position crosses 0 (sign change):

- add +1 to position
- invert the sign of the modifier

## Initial State

- POSITION = 0
- MODIFIER = +0.1

## Steps

1. Move 5 steps forward
2. Move 6 steps backward
3. Move 2 steps forward
4. Move 1 step backward

Each step uses the current modifier.

## Canonical Final State

- POSITION = 0.1
- MODIFIER = -0.1
- FINAL_POSITION = 0.1

## What this scenario tests

- event detection (zero crossing)
- state mutation triggered by events
- correct ordering of operations
- modifier sign tracking
- resistance to shortcut reasoning

## Why this scenario is hard

The difficulty comes from:

- event-based rules (not step-based)
- sign crossing detection
- modifier mutation mid-process
- dependency between position and modifier

Weak systems often fail by:

- missing the crossing event
- applying the rule at the wrong time
- forgetting to invert modifier
- computing forward/backward as simple sums

## Correctness

Correctness is the primary signal.

Even small mistakes:

- missed crossing
- wrong modifier sign

will lead to incorrect final position.

## Retention

Tracked variables:

- POSITION
- MODIFIER

Full retention requires both variables to be preserved.

## Output requirements

Exact headings must be used:

- CHECKPOINT 0 - INITIAL STATE
- CHECKPOINT 1 - AFTER FORWARD
- CHECKPOINT 2 - AFTER BACKWARD
- CHECKPOINT 3 - AFTER FORWARD 2
- CHECKPOINT 4 - AFTER BACKWARD 2
- CHECKPOINT 5 - FINAL STATE
- FINAL RETAINED VARIABLES
- FINAL LOST VARIABLES

Exact format:

NAME: VALUE

No extra variables allowed.

## Human-verifiable check

A human can quickly verify:

- final POSITION = 0.1
- final MODIFIER = -0.1

## Key failure mode

This scenario exposes:

> inability to handle event-triggered state changes during iterative updates

LLMs often:

- ignore crossing events
- treat movement as linear accumulation
- fail to update modifier correctly

## Category

event_driven_state_update