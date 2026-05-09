# Benchmarks — Persistent Reasoning Light

This directory defines the **end-to-end benchmark pipeline** for evaluating
Persistent Reasoning Light (PR-Light) against baseline execution.

The benchmark system is designed to be:

- **Deterministic** — reproducible from scenario definitions and event logs
- **Transparent** — no hidden evaluation logic
- **Layered** — clear separation between execution, metrics, comparison, and reporting
- **Contract-driven** — strict validation across all stages

---

# 📦 Directory Structure
```
benchmarks/ 
├── scenarios/              # Scenario definitions (markdown + JSON) 
├── results/                # Benchmark outputs per mode 
│   ├── baseline/ 
│   ├── pr_ephemeral/ 
│   └── pr_light_brain/ 
├── reports/                # Generated reports (markdown + SVG charts) 
├── tools/                  # Benchmark tools (execution, metrics, comparison, reporting) 
├── run_benchmarks.py       # Ordinary benchmark execution entry point
├── run_experiments.py      # Multi-run experimental characterization entry point
└── README.md
```

The canonical provider-agnostic benchmark execution layer lives at:
`benchmark_execution/`

# Profile Runtime Knobs

Profile-based runs may declare the artifact/context runtime knobs explicitly:

```json
{
  "working_context_format": "reference_only",
  "artifact_generator_mode": "legacy",
  "artifact_filter_mode": "off"
}
```

Supported `working_context_format` values:
- `reference_only`: legacy id-only working context.
- `relevant_summaries`: scenario-prefix selected id + summary context.

Supported `artifact_generator_mode` values:
- `legacy`: current default generator behavior.
- `constrained`: active constrained artifact generator.
- `shadow`: legacy active output plus constrained diagnostic shadow output.

Supported `artifact_filter_mode` values:
- `off`: no filter evaluation.
- `shadow`: diagnostic filter telemetry.
- `soft`: accepted/rejected verdict telemetry with no blocking.

Profile values are defaults for the run. CLI values override profile values:

```bash
py benchmarks/run_benchmarks.py \
  --profile gemini_flash_lite_latest \
  --working-context-format relevant_summaries \
  --artifact-generator-mode shadow \
  --artifact-filter-mode soft
```

These modes affect prompt/context shaping and diagnostic telemetry only. They do
not change scoring.

---

# 🧠 Benchmark Modes

| Mode               | Description 									|
|--------------------|----------------------------------------------|
| `baseline`         | No persistent reasoning, no working context  |
| `pr_ephemeral`     | Optional PR-Ephemeral diagnostic runtime with empty reasoning brain |
| `pr_light_brain`   | PR-Light runtime with seeded reasoning brain |

Default standard benchmark runs execute:
- `baseline`
- `pr_light_brain`

Optional diagnostic intermediate mode:
- `pr_ephemeral`
- controlled by profile flag `diagnostic_modes.pr_ephemeral`
- excluded from execution entirely when disabled

Optional diagnostic post-run enrichment:
- `diagnostic_modes.post_run_artifact_harvest`
- disabled by default
- post-run only
- runtime-only
- governance/storage-mediated
- not part of ordinary benchmark truth or mode semantics

Optional derived Phase 1A retention layer:
- `sc_01_structural_retention`
- generates derived retention artifacts only
- count-based presence/absence only
- no correctness layer yet
- Phase 3 v1 adds ghost tracking only for this scenario
- not part of core benchmark scoring

Optional derived Phase 1B effect summary layer:
- small human-facing run summary only
- derived from existing raw metrics
- currently limited to reuse improvement and rediscovery reduction
- does not replace core scientific evaluation
- does not introduce a global PR score

Phase 2 correctness layer:
- currently enabled only for `sc_03_math_state_loss` in the active canonical map
- adds `correctness_percent` independently from `retention_percent`
- adds `retention_correctness_gap`
- uses exact slot-value checking only
- does not merge correctness into score

Phase 3 v1 ghost layer:
- currently scoped only to `sc_01_structural_retention`
- adds `ghost_units` and `ghost_percent`
- tracks extra non-canonical structure as a separate structural axis
- does not change canonical retained/lost accounting
- math scenarios remain deferred for ghost support

Phase 4 integration layer:
- keeps `retention_layer.json` as the canonical per-scenario interpretation artifact
- keeps `retention_summary.md` as the canonical human-readable per-scenario interpretation artifact
- adds explicit layer support status per scenario
- does not introduce a new scoring system

Diagnostic trajectory layer:
- strictly diagnostic only
- separate from scoring, retention, correctness, structural ghost, temporal ghost, and return-to-origin
- rollout-gated by explicit scenario metadata field `trajectory_readiness`
- `trajectory_readiness=ready` is currently limited to `sc_01_structural_retention`
- `trajectory_readiness=deferred` or `unsupported` does not emit trajectory diagnostics
- `trajectory_contract` is present in metadata as future schema-only support and is currently `null` for every scenario
- no scenario currently enables `trajectory_contract`, and it is not used to compute trajectory diagnostics yet
- current APPLY 1 support is limited to `sc_01_structural_retention`
- `checkpoint_count` means observable parsed checkpoint count, not raw scenario instruction count
- does not introduce a new benchmark score

Layer support status meanings:
- `enabled` = the layer is implemented and its fields are present
- `deferred` = the layer is an intended future interpretation layer for that scenario but is not yet implemented
- `unsupported` = the layer is not part of the current interpretation model for that scenario

Current interpretation support map:
- `sc_03_math_state_loss`
  retention=`enabled`, correctness=`enabled`, ghost=`unsupported`
- `sc_01_structural_retention`
  retention=`enabled`, correctness=`deferred`, ghost=`enabled`
- `sc_02_n_back_anomaly_trap`
  retention=`deferred`, correctness=`unsupported`, ghost=`deferred`
- `sc_04_chain_collapse`
  retention=`deferred`, correctness=`unsupported`, ghost=`deferred`
- `sc_05_digit_span_n_back_hybrid`
  retention=`deferred`, correctness=`deferred`, ghost=`deferred`
- `sc_06_plan_reset`
  retention=`deferred`, correctness=`unsupported`, ghost=`deferred`
- `sc_07_trail_making`
  retention=`deferred`, correctness=`deferred`, ghost=`deferred`
- `sc_08_move_clock_hands`
  retention=`deferred`, correctness=`deferred`, ghost=`deferred`
- `sc_99_killer_all_scenarios`
  retention=`enabled`, correctness=`enabled`, ghost=`enabled`
  composite stress scenario with section-based interpretation
  sections 1-2 are interpreted now; sections 3-5 remain deferred inside the composite artifact
- `sc_00_stateless_direct_transform`
  retention=`unsupported`, correctness=`unsupported`, ghost=`unsupported`

Active interpretation-ready scenarios today:
- `sc_01_structural_retention`
- `sc_03_math_state_loss`
- `sc_99_killer_all_scenarios` (composite, section-based, partial section support)

Structurally aligned but still deferred for later interpretation support:
- `sc_02_n_back_anomaly_trap`
- `sc_04_chain_collapse`
- `sc_05_digit_span_n_back_hybrid`
- `sc_06_plan_reset`
- `sc_07_trail_making`
- `sc_08_move_clock_hands`

Current active canonical diagnostic `scenario_subset`:
- `sc_00_stateless_direct_transform`
- `sc_01_structural_retention`
- `sc_02_n_back_anomaly_trap`
- `sc_03_math_state_loss`
- `sc_04_chain_collapse`
- `sc_05_digit_span_n_back_hybrid`
- `sc_06_plan_reset`
- `sc_07_trail_making`
- `sc_08_move_clock_hands`

Current showcase / mandatory stress scenario:
- `sc_99_killer_all_scenarios`
- selected as `showcase`
- appended by the runner as the mandatory stress case
- authored as a composition-by-reference scenario schema
- each section explicitly lists `source_scenario_id`, `include_steps`, `return_to_origin`, and `contract_imports`
- no implicit step inclusion or implicit contract inheritance is allowed
- current rollout now resolves `sc_9` into a fully explicit scenario before execution
- debug artifact: `benchmarks/reports/<run_id>/scenarios/sc_99_resolved.json`
- interpretation now consumes the resolved explicit `sc_9` structure
- scoring and metric semantics remain unchanged
- interpreted section-by-section
- only section-level aggregation is allowed

---

# 🧩 Scenario Layer

Each scenario is defined as:

- `*.md` — human-readable description
- `*.json` — task semantics
- `*.metadata.json` — benchmark / engine contract metadata

Example:
```
scenarios/ 
├── sc_0_interrupt_compress_continue.md 
├── sc_0_interrupt_compress_continue.json
└── sc_0_interrupt_compress_continue.metadata.json
```

Scenario JSON defines:
- `scenario_id`
- `scenario_name`
- `scenario_type`
- `description`
- `steps[]`

Phase 0–2 migrated field classes are now metadata-authoritative:
- `scenario_mode`
- `showcase`
- `status`
- `return_to_origin`
- `supports_retention`
- `supports_correctness`
- `supports_ghost`
- `supports_temporal_ghost`
- `trajectory_readiness`

Companion metadata files currently define:
- `contract_version`
- `identity`
- `migration_lock`
- `execution_contract`
- `interpretation_support`
- `interpretation_contract`
- `retention_contract`
- `ghost_contract`
- `correctness_contract`
- `trajectory_contract`

Trajectory Contract schema support is present but disabled:
- every scenario currently uses `trajectory_contract: null`
- future enabled contracts must use `mode: checkpoint_expected_values`
- this field is diagnostic-only schema support and does not affect scoring or interpretation formulas
- current `sc_1` trajectory diagnostics remain governed by `trajectory_readiness`, not by `trajectory_contract`

Interpretation Contract is now metadata-authoritative for:
- `interpretation_contract.interpretation_variant`
- `interpretation_contract.layer_support`
- section-level interpretation state for `sc_9`

Retention Contract is now metadata-authoritative for:
- `retention_contract.retention_type`
- `retention_contract.unit_groups`
- `retention_contract.checkpoints`
- `retention_contract.final_sections`
- `retention_contract.required_exact_section_headings`
- section-level retention truth for `sc_9` where applicable

Correctness Contract is now metadata-authoritative for top-level scenarios only:
- `correctness_contract.slot_section_heading`
- `correctness_contract.value_match_policy`
- `correctness_contract.expected_slot_values`

Ghost Contract is now metadata-authoritative for top-level standard scenarios only:
- `ghost_contract.token_pattern`
- `ghost_contract.valid_transformations`
- section-level composite ghost truth for `sc_9` remains intentionally deferred in `scenario.json`

`sc_9` section-level correctness truth is now metadata-authoritative:
- `section_correctness_contracts[].section_id`
- `section_correctness_contracts[].correctness_contract.slot_section_heading`
- `section_correctness_contracts[].correctness_contract.value_match_policy`
- `section_correctness_contracts[].correctness_contract.expected_slot_values`
- this staged batch changes ownership only; composite formulas and behavior remain unchanged

`sc_9` section-level ghost truth is now metadata-authoritative:
- `section_ghost_contracts[].section_id`
- `section_ghost_contracts[].ghost_contract.token_pattern`
- `section_ghost_contracts[].ghost_contract.valid_transformations`
- top-level composite ghost truth remains intentionally deferred where still applicable
- this staged batch changes ownership only; ghost formulas and composite behavior remain unchanged

Still intentionally not migrated:
- section-level composite correctness truth
- ghost contract

Current loader boundary:
- task semantics come from `scenario.json`
- migrated execution/support fields come from `scenario.metadata.json`
- migrated interpretation-contract fields also come from `scenario.metadata.json`
- migrated retention-contract fields also come from `scenario.metadata.json`
- migrated top-level ghost-contract fields also come from `scenario.metadata.json`
- migrated top-level correctness-contract fields also come from `scenario.metadata.json`
- migrated `sc_9` section-level correctness-contract fields also come from `scenario.metadata.json`
- migrated `sc_9` section-level ghost-contract fields also come from `scenario.metadata.json`
- metadata identity mismatch is a hard failure
- top-level composite ghost parser/evaluation contract still remains in `scenario.json` during this stage

Formal reference:
- see [contracts/metadata_field_catalog.md](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmarks\contracts\metadata_field_catalog.md) for the current metadata field catalog, ownership model, validation rules, migration locks, and `sc_9` composite exceptions

Current canonical control example:
- `sc_00_stateless_direct_transform.md`
- `sc_00_stateless_direct_transform.json`
- `sc_00_stateless_direct_transform.metadata.json`

---

# 📊 Result Artifacts

Each scenario run produces **three artifact types per mode**:
```
results/
├── <scenario_id>.trace.log 
├── <scenario_id>.events.jsonl 
├── <scenario_id>.result.json
```

## 1. `.trace.log` — Human-readable execution log

- Full prompt
- Agent output
- Extracted artifacts (if any)

Purpose:
- debugging
- qualitative inspection

## 2. `.events.jsonl` — Structured event stream (canonical source)

- Append-only JSONL stream
- Each line = one event

Example:

```
{"event_type": "task_started", "step_index": 1, ...}
{"event_type": "reasoning_step", "step_index": 2, ...}
```

Properties:
- deterministic (no hidden state)
- schema-validated
- adapter-independent

👉 This is the source of truth for metric computation

## 3. `.result.json` — Derived metrics
- Built from `.events.jsonl` only
- No hidden adapter logic
- No implicit state

Contains sections:
- metadata
- reasoning_stability
- knowledge_persistence
- memory_efficiency
- retrieval_metrics
- persistence_integrity
- task_outcome

For `sc_01_structural_retention`, the report layer may also generate:
- `sc_01_structural_retention.retention_layer.json`
- `sc_01_structural_retention.retention_summary.md`

These are derived reporting artifacts:
- generated after benchmark execution
- strict and count-based
- human-verifiable
- separate from core scientific metrics
- may include a ghost layer for extra non-canonical unit ids in `sc_01_structural_retention`

---
# OpenAI Execution Contract

OpenAI benchmark execution is governed by the OpenAI Execution Contract.
All benchmark-side OpenAI interactions MUST go through the adapter layer.

See:
``` 
benchmarks/contracts/openai_execution_contract.md
```

---

# ⚙️ Entry Points

Two top-level entry points are intentionally supported:

- `benchmarks/run_benchmarks.py`
  Ordinary benchmark execution.
- `benchmarks/run_experiments.py`
  Multi-run experimental characterization.

Important:
- both entry points use the same benchmark adapters
- both rely on the same storage lifecycle contracts
- both rely on the same governance boundaries and mode semantics
- both reuse the same result/comparison primitives
- `run_experiments.py` is not a separate execution world

The experimental entry point is a thin wrapper over:
`benchmarks/tools/explore_pr_sensitivity.py`

That tool remains the harness implementation behind multi-run characterization.

---

# ⚙️ Benchmark Pipeline

## 1. Run benchmark scenarios
```
python benchmarks/run_benchmarks.py
```

⚠️ Current implementation is a scaffold pipeline:
- agent execution is placeholder
- event + result pipeline is fully wired

## 1b. Run multi-run experiments
```
python benchmarks/run_experiments.py
```

Use this entry point for:
- multi-run characterization
- plateau/harm exploration
- PR sensitivity analysis

It reuses the same underlying execution/storage/governance substrate as
ordinary benchmark execution.

## 2. Compute metrics from events
```
python benchmarks/tools/compute_metrics_from_events.py \
  --events path/to/<scenario_id>.events.jsonl \
  --adapter-name openai_codex \
  --output path/to/<scenario_id>.result.json
```

Principles:
- event-derived only
- no hidden evaluation
- deterministic

## 3. Compare results across modes
```
python benchmarks/tools/compare_results.py \
  --scenario-id <scenario_id> \
  --output benchmarks/reports/<run_id>/scenarios/<scenario_id>.comparison.json
```

Produces:
- benchmarks/reports/<run_id>/scenarios/<scenario_id>.comparison.json

## 4. Normalize metrics (for visualization)
```
python benchmarks/tools/normalize_metrics.py
```

- converts raw metrics → normalized [0..1]
- used for radar charts
- does NOT redefine raw truth

Execution adapters may share provider-agnostic executor interfaces from:
`benchmark_execution/`

## 5. Generate radar charts
```
python benchmarks/tools/generate_quickchart_radar_svg.py \
  --radar reasoning_stability \
  --baseline-result benchmarks/results/baseline/<scenario_id>.result.json \
  --pr-ephemeral-result benchmarks/results/pr_ephemeral/<scenario_id>.result.json \
  --pr-light-brain-result benchmarks/results/pr_light_brain/<scenario_id>.result.json \
  --output benchmarks/reports/<run_id>/charts/radar_chart_reasoning_stability.svg
```

- uses external QuickChart API
- visualization-only dependency (does not affect benchmark correctness)

## 6. Generate summary report
```
python benchmarks/tools/generate_summary_report.py \
  --comparison benchmarks/reports/<run_id>/scenarios/<scenario_id>.comparison.json \
  --radars reasoning_stability \
  --output benchmarks/reports/<run_id>/<scenario_id>.summary.md
```

Produces:
- <scenario_id>.summary.md
- benchmarks/reports/<run_id>/charts/<scenario_id>.<radar_name>.svg

Full benchmark runs write run-scoped report outputs under:
- benchmarks/reports/<run_id>/compared_summary_report.md
- benchmarks/reports/<run_id>/comparison_summary.json
- benchmarks/reports/<run_id>/scenarios/<scenario_id>.comparison.json
- benchmarks/reports/<run_id>/charts/radar_chart_<radar_name>.svg

---

# 🧰 Operational Tools

## Reset runtime brain
```
python benchmarks/tools/reset_runtime_brain_and_temp_results.py \
  --reset-runtime-brain
```

Optional:
```
--clean-results
--scenario-id <id>
--dry-run
```

Properties:
- no silent overwrite
- explicit intent required
- safe cleanup

## Review and seed runtime artifacts
```
python benchmarks/tools/review_and_seed_runtime_artifacts.py \
  --artifact-id <id>
```

Optional:
```
--all
--apply
--list
```

Purpose:
- controlled promotion from runtime → seeded brain
- NOT part of benchmark execution
- explicit manual step

---

# 🧱 Architecture Principles

## 1. Event-first evaluation
```
<scenario_id>.events.jsonl → <scenario_id>.result.json → <run_id>/scenarios/<scenario_id>.comparison.json → <run_id>/compared_summary_report.md
```

- events are canonical
- results are derived
- no hidden computation layers

## 2. No silent mutation
- no overwrite of artifacts
- no implicit fixes
- no hidden state changes

## 3. Deterministic pipeline
- same input → same output
- timestamps optional (not required for correctness)
- step_index = primary ordering anchor

## 4. Strict validation everywhere
- scenario validation
- event validation
- result schema validation
- comparison contract validation

Failures are explicit.

## 5. Layer separation
Layer     | Responsibility
Adapter   | execution + event emission
Events    | canonical trace
Metrics   | derived from events
Comparison| cross-mode evaluation
Reporting | visualization + markdown

---

# ⚠️ Important Notes

## This is NOT an evaluation oracle
- metrics are derived, not absolute truth
- some metrics are placeholders / proxies
- no semantic scoring layer exists (yet)

## Baseline vs PR-Light
Baseline may still receive benchmark-visible inputs such as:
- prompt
- context wrapper (benchmark-visible)

But:
- it does NOT have PR runtime semantics

This distinction is intentional.

## Runtime vs Seeded Brain
Brain     | Purpose
runtime   | ephemeral per-run context
seeded    | controlled persistent knowledge

Promotion is:
- manual
- reviewed
- explicit

---

# 🚧 Current Status

- ✅ Scenario system
- ✅ Event logging
- ✅ Result schema
- ✅ Metrics derivation
- ✅ Comparison
- ✅ Reporting
- ⚠️ Agent execution = placeholder (to be integrated)

---

# 🔮 Future Work
- real agent integration (Codex / OpenClaw-like)
- richer event payloads
- better metric fidelity
- multi-run statistical aggregation
- stricter reproducibility validation
- PR governance integration

---

# 🧭 Summary
This benchmark system is not just a testing harness.
It is a contract-driven evaluation pipeline for Persistent Reasoning:
- explicit
- inspectable
- reproducible
- extensible

And most importantly:
It measures not just outputs, but reasoning stability over time.

---
