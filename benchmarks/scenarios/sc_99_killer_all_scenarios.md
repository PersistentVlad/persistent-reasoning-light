# Killer Scenario - Sectioned Full Stress Stack (sc_9)

## Purpose

This is the integrated stress-layer scenario for the benchmark suite.

It combines five independent human-verifiable pressure sections into one continuous scenario:

1. Structural Retention
2. Math State Loss
3. N-Back Anomaly Trap
4. Trail Making
5. Move Clock Hands

Each section contributes up to `20%`.

Total possible section-level retention contribution = `100%`.

## Composite interpretation contract

`sc_9` is interpreted as a composite scenario, not as one flat unit inventory.

Authoring status:

- the scenario now declares a composition-by-reference schema
- each section explicitly references a canonical source scenario
- each section explicitly enumerates `include_steps`
- each section explicitly declares `return_to_origin` and `contract_imports`
- execution resolution is not wired yet in this step
- no implicit inclusion or hidden fallback behavior is allowed

Important rules:

- each section is evaluated independently
- section internals are never merged into one raw-unit pool
- only section-level aggregation is allowed
- no fake global scalar score is introduced

Current implementation status:

- Section 1: interpreted now
- Section 2: interpreted now
- Sections 3-5: explicitly deferred for later section-local interpretation support

## Section headings

Inside every composite checkpoint, the final answer must use exactly these subsection headings:

- `SECTION 1 - STRUCTURAL RETENTION`
- `SECTION 2 - MATH STATE LOSS`
- `SECTION 3 - N-BACK ANOMALY TRAP`
- `SECTION 4 - TRAIL MAKING`
- `SECTION 5 - MOVE CLOCK HANDS`

The top-level final section lists must use only these exact section ids:

- `section_1_structural_retention`
- `section_2_math_state_loss`
- `section_3_n_back_anomaly_trap`
- `section_4_trail_making`
- `section_5_move_clock_hands`

## Section model

### Section 1 - Structural Retention (`20%`)

Tests preservation of exact units:

- `F1-F10`
- `D1-D6`
- `C1-C4`

Current interpretation support:

- retention enabled
- ghost enabled
- correctness deferred

### Section 2 - Math State Loss (`20%`)

Tests preservation of exact canonical math slots:

- `PRODUCT_1`
- `PRODUCT_2`
- `COMBINED_SUM`
- `AFTER_SUBTRACTION`
- `AFTER_DIVISION`
- `AFTER_ADDITION`
- `AFTER_MULTIPLICATION`
- `AFTER_REDUCTION`
- `FINAL_NUMERATOR`
- `FINAL_RESULT`

Current interpretation support:

- retention enabled
- correctness enabled
- ghost unsupported

### Section 3 - N-Back Anomaly Trap (`20%`)

Tests temporal sequence retention for canonical sequence:

- `A-T`

Current interpretation support:

- retention deferred
- correctness unsupported
- ghost deferred

### Section 4 - Trail Making (`20%`)

Tests ordered alternating trail retention:

- `1-A` through `10-J`

Current interpretation support:

- retention deferred
- correctness deferred
- ghost deferred

### Section 5 - Move Clock Hands (`20%`)

Tests cyclic spatial state return to origin:

- `TIME = 12:00`
- `HOUR_HAND = 12`
- `MINUTE_HAND = 00`

Current interpretation support:

- retention deferred
- correctness deferred
- ghost deferred

## Why the section model matters

The killer scenario must not collapse into a single vague score.

Instead:

- 5 independent sections
- each worth `20%`
- interpretation artifacts report section results separately
- top-level totals are sums of section contributions only

This keeps the stress scenario:

- human-readable
- graphable
- honest about partial support
- compatible with later section expansion

## Benchmark role

This scenario is the mandatory integrated stress layer.

It complements the compact diagnostic scenarios and remains the showcase scenario for ordinary benchmark runs.
