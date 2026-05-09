# Scenario: Interrupt → Compress → Continue

## Scenario ID
sc_18_interrupt_compress_continue

## Description
This scenario tests the agent's ability to:

- maintain task continuity across interruptions
- compress intermediate reasoning into a compact representation
- recover and continue execution with limited context

The scenario simulates a common real-world failure mode:
an agent begins a task, gets interrupted, and must resume without full access to prior reasoning.

---

## Core Challenge

The agent must:

1. Start a structured task
2. Handle an interruption
3. Produce a compact summary of the current reasoning state
4. Continue execution using only the compressed representation

---

## Expected Behavior

A robust agent should:

- preserve key structural elements of the task
- avoid restarting from scratch
- avoid drifting to a different solution
- demonstrate continuity between pre- and post-interruption reasoning

---

## Failure Modes

Typical failures include:

- loss of plan structure after interruption
- restarting the task from scratch
- inconsistent or contradictory continuation
- inability to use compressed context effectively

---

## Notes for Benchmarking

- This scenario is sensitive to **context retention** and **compression quality**
- It is especially useful for comparing:
  - baseline agents
  - PR-Light agents
  - PR-Light with persistent reasoning brain

---

## Category

context_interruption_recovery