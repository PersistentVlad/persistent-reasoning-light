# Reasoning Model

## Purpose

Persistent Reasoning Light introduces a minimal reasoning model designed to preserve important reasoning outcomes across agent execution cycles.

Instead of storing full reasoning traces, the system captures **durable reasoning elements** as structured artifacts.

---

## Core Principle

The central rule of the reasoning model is:

```
One artifact = one durable reasoning element
```

Artifacts represent conclusions, decisions, constraints, and tasks that should persist across reasoning steps.

They are not intended to capture temporary thoughts or raw reasoning chains.

---

## Artifact Types

The system uses a small artifact vocabulary.

Supported artifact types:

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

Each artifact type represents a specific reasoning function.

---

### TaskCard

Represents the current goal or task.

Example:

```
Implement Git-based artifact loader
```

---

### DecisionCard

Represents a resolved architectural or reasoning decision.

Decisions prevent the agent from repeatedly reconsidering the same options.

Example:

```
Use Git as canonical artifact storage
```

---

### ConstraintCard

Represents rules that must not be violated.

Constraints protect reasoning stability.

Example:

```
Canonical artifacts must not be rewritten in place
```

---

### ProcedureCard

Represents reusable workflows or operational steps.

Example:

```
Steps required to add a reasoning artifact
```

---

### IssueCard

Represents unresolved questions.

Issues signal areas where reasoning is incomplete.

Example:

```
Should relation storage remain JSONL or move to graph index?
```

---

## Working Context

Agents typically operate using a compact working context rather than loading the entire reasoning brain.

Example working context:

```
{
  "active_task": "task_git_artifact_loader",
  "decisions": ["decision_use_git_storage"],
  "constraints": ["constraint_no_artifact_overwrite"],
  "open_issues": ["issue_relation_storage"]
}
```

The working context provides the minimal reasoning state needed for execution.

---

## Artifact Lifecycle

Artifacts follow a simple lifecycle.

```
reasoning outcome
↓
artifact suggestion
↓
artifact_filter evaluation
↓
draft artifact
↓
artifact commit
```

This process ensures that only durable reasoning elements enter the persistent brain.

---

## Artifact Suggestion Filtering

Agents may generate artifact suggestions during execution.

The artifact filter evaluates whether suggestions represent durable reasoning elements.

The filter performs simple checks such as:

- valid artifact type
- presence of meaningful fields
- absence of trivial duplicates
- avoidance of temporary reasoning text

The filter must remain deterministic and lightweight.

---

## Reasoning Stability

The reasoning model improves agent stability by preserving:

- accepted decisions
- operational constraints
- reusable procedures
- unresolved issues

This prevents agents from repeatedly rediscovering the same reasoning outcomes.

---

## Relation to Full Persistent Reasoning

Persistent Reasoning Light is a simplified operational model.

Full Persistent Reasoning introduces additional features such as:

- reasoning governance
- invariant enforcement
- lineage verification
- recovery semantics

PR-Light focuses only on **practical reasoning persistence for agents**.