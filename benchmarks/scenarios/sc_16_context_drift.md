# Scenario: Context Drift Under Similar Alternatives

## Scenario ID
sc_16_context_drift

## Description
This scenario tests whether an agent can preserve the original reasoning direction
when exposed to a nearby but misleading alternative task.

The scenario simulates a common failure mode:
the agent begins solving one problem, then receives a plausible adjacent idea
and gradually drifts away from the original objective without explicitly noticing it.

---

## Core Challenge

The agent must:

1. Start with a clearly defined goal
2. Encounter a similar but competing alternative
3. Reject unjustified task switching
4. Restate the original scope explicitly
5. Continue execution without semantic drift

---

## Expected Behavior

A robust agent should:

- preserve the original task identity
- distinguish relevant vs irrelevant alternative ideas
- avoid silently changing the problem being solved
- continue with a solution aligned to the initial objective

---

## Failure Modes

Typical failures include:

- switching to the distracting alternative without justification
- partially merging two different task scopes
- restating the wrong task as if it were the original one
- producing a final answer that no longer matches the starting objective

---

## Why This Matters

Reasoning drift is one of the most expensive failure modes in long-running agent systems.

An agent may appear productive while actually solving the wrong problem.

This scenario is designed to expose:

- drift resistance
- task identity preservation
- scope re-alignment ability

---

## Notes for Benchmarking

This scenario is useful for comparing:

- baseline systems that rely only on immediate context
- PR-Light systems that preserve compact structured context
- PR-Light + seeded reasoning brain systems that may reinforce stable task boundaries

It is especially relevant for metrics such as:

- reasoning_drift_rate
- plan_retention_rate
- structural_integrity_score

---

## Category

reasoning_drift_detection