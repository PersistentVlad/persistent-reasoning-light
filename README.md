# Persistent Reasoning Light

A minimal structured reasoning layer for AI agents.

Most agents fail long tasks for one simple reason:

**they forget their own decisions.**

Persistent Reasoning Light gives agents a small structured brain that preserves decisions, constraints, procedures, and open questions across execution cycles.

Instead of rebuilding context every step, agents reuse durable reasoning artifacts stored in Git.

---

## The Problem

Typical agent execution looks like this:

```
task
↓
plan
↓
execute
↓
context drift
↓
replan
↓
loop
```

Agents repeatedly rediscover the same decisions because reasoning is not persistent.

---

## The Idea

Persistent Reasoning Light introduces a tiny structured memory layer.

```
task
↓
plan
↓
store reasoning artifacts
↓
execute
↓
reuse decisions and constraints
```

Agents keep a **reasoning brain** composed of small artifact cards.

---

## Example Reasoning Brain

```
tasks/
  task_git_artifact_loader.json

decisions/
  decision_use_git_storage.json

constraints/
  constraint_no_artifact_overwrite.json

procedures/
  procedure_add_artifact.json

issues/
  issue_relation_storage.json
```

Five cards already capture:

- the current task
- accepted decisions
- safety constraints
- reusable workflows
- unresolved architectural questions

---

## Project Structure

```
persistent-reasoning-light/
├── reasoning-engine/
│   ├── README.md
│   ├── pyproject.toml
│   ├── .gitignore
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── artifact_types.py
│   │   ├── artifact_filter.py
│   │   ├── artifact_cards.py
│   │   ├── storage.py
│   │   ├── validation.py
│   │   ├── relations.py
│   │   ├── view_builder.py
│   │   ├── git_adapter.py
│   │   ├── context_loader.py
│   │   └── cli.py
│   │
│   ├── meta/
│   │   ├── ai/
│   │   │   ├── AIContext.md
│   │   │   ├── architecture_context.md
│   │   │   ├── codex_rules.md
│   │   │   └── codex_tasks.md
│   │   │
│   │   └── docs/
│   │       ├── architecture.md
│   │       ├── reasoning_model.md
│   │       ├── repository_layout.md
│   │       ├── agent_adoption_model
│   │       └── adapter_contract.md
│   │
│   └── dev/
│       └── tests/
│           ├── test_cards.py
│           ├── test_storage.py
│           ├── test_relations.py
│           ├── test_view_builder.py
│           └── test_git_adapter.py
│
├── reasoning-brain/
│   ├── README.md
│   │
│   ├── brain/
│   │   ├── tasks/
│   │   ├── decisions/
│   │   ├── constraints/
│   │   ├── procedures/
│   │   └── issues/
│   │
│   ├── relations/
│   │   ├── depends_on.jsonl
│   │   └── blocks.jsonl
│   │
│   ├── views/
│   │   └── working_context.json
│   │
│   └── runtime/
│       ├── drafts/
│       └── inbox/
│
└── reasoning-adapters/
    ├── README.md
    ├── openclaw/
    ├── zeroclaw/
    ├── codex/
    └── claude/
```

- **reasoning-engine** — core runtime
- **reasoning-brain** — persistent reasoning artifacts
- **reasoning-adapters** — integrations for agent systems

---

## Why Git?

Artifacts are stored as small JSON files.

Git provides:

- transparent reasoning history
- inspectable decisions
- distributed replication
- simple infrastructure

Git history becomes a **timeline of reasoning evolution**.

---

## Agent-First Adoption

PR-Light is designed for **agents to adopt first**.

Typical adoption cycle:

```
agent detects reasoning instability
↓
agent installs structured memory capability
↓
agent begins storing reasoning artifacts
↓
task stability improves
↓
human notices artifact files
```

Agents benefit immediately. Humans discover the system later.

---

## Design Principles

PR-Light prioritizes:

- minimal architecture
- human-readable artifacts
- Git-native persistence
- agent compatibility
- long-task stability

---

## Status

Experimental prototype exploring structured reasoning persistence for AI agents.