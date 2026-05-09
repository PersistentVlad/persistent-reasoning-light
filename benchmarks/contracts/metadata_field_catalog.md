# Benchmark Scenario Metadata Field Catalog

## 1. Purpose

This catalog documents the benchmark scenario metadata system as it exists today.

The benchmark scenario bundle is intentionally split into:

- `scenario.json`: task-facing scenario semantics
- `scenario.metadata.json`: benchmark / engine contract metadata

The split exists so benchmark logic can evolve contract ownership, validation, and migration state without rewriting task instructions or scenario semantics.

This document describes current implementation reality only. It does not define future schema changes.

## 2. Source-of-Truth Model

Current source-of-truth model:

- `scenario.json` is authoritative for task semantics.
- `scenario.metadata.json` is authoritative for migrated benchmark / engine contract fields.
- The loader builds a merged runtime config for compatibility with downstream code.

Important:

- The merged runtime config is compatibility-facing, not itself the source of truth.
- Migrated field classes may still appear in merged runtime objects, but those values are synthesized from metadata.
- Deferred field classes remain authoritative in `scenario.json` until migrated.

## 3. Loader Precedence

Canonical loader path:

- [scenario_utils.py](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmark_adapters\common\scenario_utils.py)
- primary entrypoint: `load_scenario_config_with_metadata(...)`

Current precedence rules:

1. Load `scenario.json`
2. Load `scenario.metadata.json`
3. Validate filename id, scenario id, metadata identity
4. Merge migrated metadata-authoritative fields into an effective runtime config
5. Validate the merged runtime config

Hard-fail rules:

- metadata identity mismatch hard-fails
- migrated section metadata keyed by `section_id` hard-fails on mismatch
- required migrated contract blocks hard-fail when missing or malformed

Current metadata-authoritative field classes:

- execution contract
- interpretation support
- interpretation contract
- retention contract
- top-level correctness contract
- top-level ghost contract
- `sc_9` section-level correctness contract
- `sc_9` section-level ghost contract

Deferred field classes remain authoritative in `scenario.json`.

## 4. Schema Overview

Current metadata blocks in `scenario.metadata.json`:

| Block | Meaning | Typical presence |
|---|---|---|
| `contract_version` | Schema/migration version marker | required |
| `identity` | Explicit scenario identity | required |
| `migration_lock` | Source-of-truth migration flags | required |
| `execution_contract` | Execution-facing scenario mode/status/showcase flags | required |
| `interpretation_support` | Layer support and readiness gates | required |
| `interpretation_contract` | Interpretation variant and layer support contract | required |
| `retention_contract` | Retention parsing/evaluation truth | required when retention supported, else null |
| `correctness_contract` | Top-level correctness truth for standard scenarios | required key; object or null |
| `ghost_contract` | Top-level ghost truth for standard scenarios | required key; object or null |
| `trajectory_contract` | Future diagnostic-only trajectory truth | required key; currently null in repo scenarios |
| `section_correctness_contracts` | `sc_9` section-level correctness truth | optional, `sc_9` only |
| `section_ghost_contracts` | `sc_9` section-level ghost truth | optional, `sc_9` only |

## 5. Field Catalog

### 5.1 Core identity and migration fields

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `contract_version` | Metadata schema version marker | string | non-empty | yes | metadata | copied into merged config | must be non-empty string | migrated |
| `identity.scenario_id` | Explicit scenario identity | string | valid scenario id | yes | metadata | validated against filename and scenario.json | mismatch hard-fails | migrated |
| `migration_lock` | Per-field-class migration state | object | boolean values | yes | metadata | copied into merged config | required keys must exist and be boolean | migrated |

### 5.2 `migration_lock` keys

Current known keys:

Global keys required in all metadata files:

- `execution_contract`
- `interpretation_support`
- `interpretation_contract`
- `retention_contract`
- `ghost_contract`
- `correctness_contract`

Current `sc_9`-specific keys:

- `section_correctness_contract`
- `section_ghost_contract`

Meaning:

- `true`: this field class is metadata-authoritative for that scenario
- `false`: this field class remains deferred / scenario-authoritative for that scenario

Note:

- The loader requires the global keys in all metadata files.
- The section-level keys are currently `sc_9`-specific staged extensions.

### 5.3 Execution contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `execution_contract.scenario_mode` | Scenario execution mode | string | `standard`, `sectioned`, `showcase` | yes | metadata | merged to `scenario_mode` | required enum | migrated |
| `execution_contract.showcase` | Showcase flag | boolean | `true/false` | yes | metadata | merged to `showcase` | must be boolean | migrated |
| `execution_contract.status` | Scenario lifecycle status | string | `stable`, `experimental`, `deprecated` | yes | metadata | merged to `status` | required enum | migrated |
| `execution_contract.return_to_origin` | Return-to-origin flag | boolean | `true/false` | yes | metadata | merged to `return_to_origin` | must be boolean | migrated |

### 5.4 Interpretation support

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `interpretation_support.supports_retention` | Retention support gate | boolean | `true/false` | yes | metadata | merged to `supports_retention` | must be boolean | migrated |
| `interpretation_support.supports_correctness` | Correctness support gate | boolean | `true/false` | yes | metadata | merged to `supports_correctness` | must be boolean | migrated |
| `interpretation_support.supports_ghost` | Ghost support gate | boolean | `true/false` | yes | metadata | merged to `supports_ghost` | must be boolean | migrated |
| `interpretation_support.supports_temporal_ghost` | Temporal ghost support gate | boolean | `true/false` | yes | metadata | merged to `supports_temporal_ghost` | must be boolean | migrated |
| `interpretation_support.trajectory_readiness` | Trajectory diagnostic readiness | string | `ready`, `deferred`, `unsupported` | yes | metadata | merged to `trajectory_readiness` | required enum | migrated |

### 5.5 Interpretation contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `interpretation_contract.interpretation_variant` | Interpretation pipeline variant | string | non-empty | yes | metadata | synthesized into `interpretation_spec.interpretation_variant` | must be non-empty string | migrated |
| `interpretation_contract.layer_support` | Layer support per scenario | object | `enabled`, `deferred`, `unsupported` per layer | yes | metadata | synthesized into `interpretation_spec.layer_support` | keys required: `retention`, `correctness`, `ghost` | migrated |
| `interpretation_contract.reason` | Human-readable interpretation rationale | string | non-empty when present | optional | metadata | copied into synthesized `interpretation_spec.reason` | must be non-empty string if present | migrated |
| `interpretation_contract.sections[]` | Section-level interpretation state for sectioned scenarios | list | keyed by `section_id` | optional, used by `sc_9` | metadata | merged onto section structures | duplicate/unknown section ids hard-fail | migrated for `sc_9` |

### 5.6 Retention contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `retention_contract.retention_type` | Retention evaluation type | string | non-empty | required when retention supported | metadata | synthesized into `retention_spec.retention_type` | must be non-empty string | migrated |
| `retention_contract.unit_groups` | Retention unit groups | list | non-empty when present | optional | metadata | synthesized into `retention_spec.unit_groups` | list when present | migrated |
| `retention_contract.checkpoints` | Retention checkpoints | list | non-empty | required when retention supported | metadata | synthesized into `retention_spec.checkpoints` | non-empty list | migrated |
| `retention_contract.final_sections` | Final retained/lost headings | object | retained/lost strings | required when retention supported | metadata | synthesized into `retention_spec.final_sections` | retained/lost keys required | migrated |
| `retention_contract.required_exact_section_headings` | Exact heading contract | list | non-empty strings | required when retention supported | metadata | synthesized into `retention_spec.required_exact_section_headings` | non-empty list | migrated |
| `retention_contract.sections[]` | Section-level retention truth for sectioned scenarios | list | keyed by `section_id` | optional, used by `sc_9` | metadata | merged onto `retention_spec.sections[]` | duplicate/unknown section ids hard-fail | migrated for `sc_9` |

### 5.7 Top-level correctness contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `correctness_contract.slot_section_heading` | Heading containing exact slot truth | string | non-empty | object required only for supported non-sectioned correctness scenarios | metadata | synthesized to top-level `correctness_spec` and `retention_spec.correctness_spec` | standard scenarios only | migrated |
| `correctness_contract.value_match_policy` | Exactness policy | string | non-empty | same as above | metadata | same | must be non-empty string | migrated |
| `correctness_contract.expected_slot_values` | Expected slot map | object | non-empty string->string map | same as above | metadata | same | non-empty object | migrated |

For sectioned scenarios:

- `correctness_contract` must be `null`

### 5.8 Top-level ghost contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `ghost_contract.token_pattern` | Token parser regex | string | non-empty | object required for migrated standard ghost scenarios | metadata | synthesized to top-level `retention_spec.ghost_spec` | standard scenarios only | migrated |
| `ghost_contract.valid_transformations` | Allowed ghost transformations | object | string -> list[string] | same as above | metadata | same | object with non-empty string keys; list[string] values | migrated |

For sectioned scenarios:

- `ghost_contract` must be `null`

### 5.9 `sc_9` section-level correctness contracts

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `section_correctness_contracts[]` | Section correctness contract entries | list | non-empty list when migration enabled | `sc_9` only | metadata | synthesized into `retention_spec.sections[*].correctness_spec` | entries keyed by `section_id`; duplicate/unknown ids hard-fail | migrated for `sc_9` |
| `section_correctness_contracts[].section_id` | Section selector | string | non-empty existing `section_id` | yes | metadata | used for matching only | unknown/missing ids hard-fail | migrated |
| `section_correctness_contracts[].correctness_contract.*` | Section correctness truth | object | same rules as top-level correctness contract | yes | metadata | synthesized into section runtime structure | required for correctness-enabled migrated section ids | migrated |

Current live migrated `sc_9` section:

- `section_2_math_state_loss`

### 5.10 `sc_9` section-level ghost contracts

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `section_ghost_contracts[]` | Section ghost contract entries | list | non-empty list when migration enabled | `sc_9` only | metadata | synthesized into `retention_spec.sections[*].ghost_spec` | entries keyed by `section_id`; duplicate/unknown ids hard-fail | migrated for `sc_9` |
| `section_ghost_contracts[].section_id` | Section selector | string | non-empty existing `section_id` | yes | metadata | used for matching only | unknown/missing ids hard-fail | migrated |
| `section_ghost_contracts[].ghost_contract.token_pattern` | Section ghost parser regex | string | non-empty | yes | metadata | synthesized into section runtime structure | required for ghost-enabled migrated section ids | migrated |
| `section_ghost_contracts[].ghost_contract.valid_transformations` | Section ghost transformation map | object | string -> list[string] | yes | metadata | synthesized into section runtime structure | validated like top-level ghost contract | migrated |

Current live migrated `sc_9` section:

- `section_1_structural_retention`

### 5.11 Trajectory contract

| Field path | Meaning | Type | Allowed values | Required | Authoritative file | Runtime synthesis | Validation rules | Migration state |
|---|---|---|---|---|---|---|---|---|
| `trajectory_contract` | Future diagnostic-only per-checkpoint trajectory contract | `null` or object | `null`, `{ "enabled": false }`, or enabled checkpoint contract | yes | metadata | none in this stage | null/disabled accepted; enabled shape strictly validated | schema-only |
| `trajectory_contract.enabled` | Explicit trajectory contract activation flag | boolean | `true/false` | required when object | metadata | none | must be boolean | schema-only |
| `trajectory_contract.mode` | Enabled trajectory contract mode | string | `checkpoint_expected_values` | required when enabled | metadata | none | exact enum | schema-only |
| `trajectory_contract.checkpoint_expected_values[]` | Expected state per checkpoint | list | non-empty list | required when enabled | metadata | none | entries must be valid objects | schema-only |
| `trajectory_contract.checkpoint_expected_values[].checkpoint_id` | Checkpoint selector | string | non-empty | required when enabled | metadata | none | duplicate checkpoint ids hard-fail | schema-only |
| `trajectory_contract.checkpoint_expected_values[].expected_slot_values` | Expected checkpoint slots | object | string -> string | required when enabled | metadata | none | non-empty object; values must be strings | schema-only |

Current repo default:

- `trajectory_contract: null` for every scenario

Important:

- This block is future diagnostic-only schema support.
- It is not synthesized into runtime scenario configs in this stage.
- It does not compute trajectory diagnostics.
- It does not affect scoring, retention, correctness, structural ghost, temporal ghost, or return-to-origin.

## 6. Migration State By Field Class

Current migration state:

| Field class | State |
|---|---|
| Execution contract | migrated |
| Interpretation support | migrated |
| Interpretation contract | migrated |
| Retention contract | migrated |
| Top-level correctness contract | migrated |
| Top-level ghost contract | migrated |
| `sc_9` section-level correctness | migrated |
| `sc_9` section-level ghost | migrated |
| Trajectory contract | schema-only, disabled/null |

Current deferred pieces:

- `sc_9` top-level composite ghost contract in `scenario.json`
- trajectory computation from `trajectory_contract`

## 7. Composite / `sc_9` Special Handling

`sc_99_killer_all_scenarios` is the current sectioned composite exception path.

Still authoritative in `scenario.json` for `sc_9`:

- `composition_spec`
- section order
- `include_steps`
- `max_percent`
- `return_to_origin`
- `section_label`
- `section_heading`
- `section_spec_ref`
- `contract_imports`
- top-level composite `retention_spec.ghost_spec`

Now metadata-authoritative for `sc_9`:

- section-level interpretation state
- section-level retention truth
- section-level correctness truth
- section-level ghost truth

Section matching rules:

- all section migrations are keyed strictly by `section_id`
- unknown metadata `section_id` hard-fails
- duplicate metadata `section_id` hard-fails
- missing migrated truth for a required enabled section hard-fails

Important:

- The composite resolution flow is intentionally preserved.
- The loader hydrates section contract truth before section resolution so downstream code continues to see the legacy-compatible structures it expects.

## 8. Validation Rules

Current validation rules enforced in the loader include:

- `identity.scenario_id` must match filename
- `scenario.json.scenario_id` must match metadata identity
- required metadata blocks must exist
- required global `migration_lock` keys must exist and be boolean
- execution enums must be valid
- interpretation support booleans must be explicit
- `trajectory_readiness` must be one of:
  - `ready`
  - `deferred`
  - `unsupported`
- `trajectory_contract`:
  - `null` is valid and is the current repo-wide default
  - `{ "enabled": false }` is valid as an explicit disabled object
  - enabled contracts require `mode: "checkpoint_expected_values"`
  - enabled contracts require non-empty `checkpoint_expected_values`
  - checkpoint ids must be non-empty strings
  - expected slot values must be a non-empty string-to-string object
- top-level `correctness_contract`:
  - object for supported non-sectioned correctness scenarios
  - `null` for sectioned scenarios
- top-level `ghost_contract`:
  - object for migrated standard ghost scenarios
  - `null` for sectioned scenarios
- section migration lock keys:
  - if present, must be boolean
- section-level migrated lists:
  - must be non-empty lists when enabled
  - entries must be objects
  - `section_id` must be non-empty
  - duplicate ids hard-fail
  - unknown ids hard-fail

Contract-version expectations in current repo state:

- standard scenarios currently use `1.4`
- `sc_9` currently uses `1.6`

The loader validates that `contract_version` is present and non-empty; repo tests enforce the current known versions.

## 9. Migration Locks

`migration_lock` records per-scenario field-class ownership state.

Current meanings:

- `execution_contract`: execution fields are metadata-owned
- `interpretation_support`: support booleans/readiness are metadata-owned
- `interpretation_contract`: interpretation variant/layer support are metadata-owned
- `retention_contract`: retention truth is metadata-owned
- `correctness_contract`: top-level correctness truth is metadata-owned
- `ghost_contract`: top-level ghost truth is metadata-owned
- `section_correctness_contract`: `sc_9` section correctness truth is metadata-owned
- `section_ghost_contract`: `sc_9` section ghost truth is metadata-owned

In practice:

- `true` means loader synthesis should enforce metadata as authoritative
- `false` means that field class is still deferred to scenario-side ownership for that scenario

## 10. Compatibility Synthesis

The loader still synthesizes several legacy-compatible runtime fields for downstream compatibility.

Current synthesized runtime structures include:

- `interpretation_spec`
- `retention_spec`
- top-level `correctness_spec`
- top-level `ghost_spec` via `retention_spec.ghost_spec`
- `retention_spec.sections[*].correctness_spec`
- `retention_spec.sections[*].ghost_spec`

Important:

- synthesized runtime values are compatibility-facing only
- they must not be mistaken for the authoritative storage location
- `trajectory_contract` is intentionally not synthesized into runtime configs in this schema-only stage

## 11. Deferred / Future Field Classes

Currently deferred, and only because they are still present in implementation today:

- `sc_9` top-level composite ghost contract in `scenario.json`

Not documented as active:

- any future trajectory contract block
- any future migration-lock keys not present in repo today

## 12. Examples

### 12.1 Standard scenario metadata example

Representative standard scenario:

- [sc_01_structural_retention.metadata.json](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmarks\scenarios\sc_01_structural_retention.metadata.json)

Example excerpts:

```json
{
  "contract_version": "1.4",
  "migration_lock": {
    "execution_contract": false,
    "interpretation_support": false,
    "interpretation_contract": false,
    "retention_contract": true,
    "correctness_contract": true,
    "ghost_contract": true
  },
  "execution_contract": {
    "scenario_mode": "standard",
    "showcase": false,
    "status": "stable",
    "return_to_origin": false
  },
  "ghost_contract": {
    "token_pattern": "[A-Z][0-9]+",
    "valid_transformations": {}
  },
  "trajectory_contract": null
}
```

### 12.2 `sc_9` section-level metadata example

Representative composite scenario:

- [sc_99_killer_all_scenarios.metadata.json](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmarks\scenarios\sc_99_killer_all_scenarios.metadata.json)

Example excerpts:

```json
{
  "contract_version": "1.6",
  "migration_lock": {
    "execution_contract": false,
    "interpretation_support": false,
    "interpretation_contract": false,
    "retention_contract": true,
    "correctness_contract": true,
    "ghost_contract": false,
    "section_correctness_contract": true,
    "section_ghost_contract": true
  },
  "section_correctness_contracts": [
    {
      "section_id": "section_2_math_state_loss",
      "correctness_contract": {
        "slot_section_heading": "SECTION 2 - MATH STATE LOSS",
        "value_match_policy": "exact_string",
        "expected_slot_values": {
          "FINAL_RESULT": "437/7"
        }
      }
    }
  ],
  "section_ghost_contracts": [
    {
      "section_id": "section_1_structural_retention",
      "ghost_contract": {
        "token_pattern": "[A-Z][0-9]+",
        "valid_transformations": {}
      }
    }
  ],
  "trajectory_contract": null
}
```

## Reference Pointers

Primary implementation and validation references:

- [scenario_utils.py](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmark_adapters\common\scenario_utils.py)
- [test_benchmark_hardening.py](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmarks\tools\tests\test_benchmark_hardening.py)
- [README.md](C:\Projects\AI\code\GitHub Repository Structure\persistent-reasoning-light\benchmarks\README.md)
