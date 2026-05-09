# Scenario: Multi-Step Math Reasoning Consistency

## Scenario ID
sc_15_math_reasoning

## Description
This scenario tests whether the agent can preserve exact mathematical state
and exact canonical values across a multi-step reasoning task using strict
named slots and exact output headings.

Unlike prose-heavy reasoning checks, this scenario is intentionally strict:
retention and correctness must both be human-verifiable without semantic
interpretation.

---

## Core Challenge

The agent must:

1. Evaluate an initial arithmetic expression
2. Transform the exact intermediate result
3. Re-verify the exact chain
4. Extend the verified chain to a final result
5. Return the full exact named chain in the required slot format

---

## Canonical Math Chain

The exact canonical chain for this scenario is:

- `SUM_18_27 = 18 + 27 = 45`
- `LEFT_PRODUCT = 45 * 6 = 270`
- `RIGHT_PRODUCT = 14 * 9 = 126`
- `INITIAL_DIFFERENCE = 270 - 126 = 144`
- `AFTER_DIVISION = 144 / 3 = 48`
- `AFTER_ADDITION = 48 + 25 = 73`
- `FINAL_RESULT = 73 * 4 - 17 = 275`

`FINAL_RESULT` must remain in exact integer form.

---

## Required Exact Output Headings

- `CHECKPOINT 1 - VERIFIED CHAIN`
- `FINAL RETAINED UNITS`
- `FINAL LOST UNITS`

Under `CHECKPOINT 1 - VERIFIED CHAIN`, the agent must use exact slot lines:

- `SUM_18_27: ...`
- `LEFT_PRODUCT: ...`
- `RIGHT_PRODUCT: ...`
- `INITIAL_DIFFERENCE: ...`
- `AFTER_DIVISION: ...`
- `AFTER_ADDITION: ...`
- `FINAL_RESULT: ...`

Under `FINAL LOST UNITS`, the agent must list lost slot names or `NONE`.

This keeps correctness checking deterministic and separate from retention.

---

## Expected Behavior

A robust agent should:

- preserve the exact named chain
- verify the exact intermediate values before extending the computation
- avoid arithmetic drift across the chain
- produce the exact canonical final integer result

---

## Failure Modes

Typical failures include:

- retaining slot structure but assigning incorrect values
- carrying forward an incorrect intermediate value
- listing the pre-extension value as the final result
- producing a plausible derivation that does not match the canonical chain

---

## Why This Matters

This scenario shows whether the agent:

- truly preserves exact math state
- can re-verify the exact chain before continuing
- retains structure without silently losing correctness

It is intentionally narrow so correctness can remain a separate signal from
retention.

---

## Category

mathematical_reasoning_integrity
