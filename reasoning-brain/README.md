# Reasoning Brain

## What is this directory?

The `reasoning-brain` directory stores **persistent reasoning artifacts** used by agents.

Instead of relying only on temporary conversation context, agents can store small structured reasoning elements that remain available across execution cycles.

These artifacts form a **minimal structured memory layer** for AI agents.

The goal is to improve **long-horizon task stability**.

---

# Core Idea

Most agents lose context during long tasks.

Typical failure pattern:

```
task
↓
plan
↓
execute
↓
context drift
↓
replanning
↓
loop
```

The reasoning brain stabilizes execution by storing durable reasoning elements.

Example flow:

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

This allows agents to remember important reasoning outcomes.

---

# Artifact Philosophy

Artifacts represent **durable reasoning elements**, not temporary thoughts.

Rule:

```
One artifact = one durable reasoning element
```

Artifacts should remain:

- small
- readable
- structured
- inspectable

They must **not contain long reasoning dumps or LLM essays**.

---

# Artifact Types

The reasoning brain currently supports a minimal artifact vocabulary.

```
TaskCard
DecisionCard
ConstraintCard
ProcedureCard
IssueCard
```

Each artifact type represents a specific role in reasoning continuity.

---

# Artifact Roles

### TaskCard

Represents the current task or goal.

Example:

```
Implement a Git-based artifact loader
```

---

### DecisionCard

Stores architectural or reasoning decisions that should not be reconsidered repeatedly.

Example:

```
Use Git as canonical artifact storage
```

---

### ConstraintCard

Represents rules that must not be violated.

Example:

```
Canonical artifacts must not be rewritten in place
```

---

### ProcedureCard

Defines reusable workflows.

Example:

```
Steps required to add a new reasoning artifact
```

---

### IssueCard

Represents unresolved architectural or reasoning questions.

Example:

```
Should relation storage remain JSONL or move to a graph index?
```

---

# Directory Structure

The reasoning brain is organized by artifact type.

Example structure:

```
reasoning-brain/

tasks/
decisions/
constraints/
procedures/
issues/
```

Each artifact is stored as a **single JSON file**.

Example:

```
tasks/task_git_artifact_loader.json
```

---

# Example Brain

A minimal reasoning brain might contain only five artifacts.

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

This is enough to represent:

- current goal
- accepted architectural decision
- safety constraint
- reusable workflow
- open question

---

# Working Context

Agents typically should not load the entire reasoning brain.

Instead a **working context projection** is generated.

Example:

```
views/working_context.json
```

Example content:

```
{
  "active_task": "task_git_artifact_loader",
  "decisions": ["decision_use_git_storage"],
  "constraints": ["constraint_no_artifact_overwrite"],
  "open_issues": ["issue_relation_storage"]
}
```

This keeps reasoning retrieval efficient.

---

# Reasoning Evolution

Artifacts evolve through repository changes.

Typical lifecycle:

```
agent produces reasoning
↓
artifact suggestion created
↓
artifact_filter evaluates suggestion
↓
draft artifact stored
↓
artifact committed to brain
```

This preserves reasoning continuity without heavy governance.

---

# Git as Reasoning Lineage

The reasoning brain works naturally with Git.

Git provides:

- artifact history
- reasoning transparency
- distributed replication
- inspectable evolution

Because artifacts are small JSON files, repository history becomes a **reasoning timeline**.

---

# Why This Matters

Agents frequently fail long tasks because they forget their own reasoning decisions.

A structured reasoning brain solves this problem by preserving:

- decisions
- constraints
- procedures
- unresolved questions

This makes agent behavior more stable and predictable.

---

# Relationship to Persistent Reasoning

This reasoning brain is part of **Persistent Reasoning Light (PR-Light)**.

PR-Light is a simplified operational profile of the larger **Persistent Reasoning architecture**.

It provides:

- minimal structured reasoning memory
- simple Git-based persistence
- compatibility with agent systems

---

# Pipeline for minimal PR engine

```
agent
↓
suggest artifact
↓
runtime/inbox
↓
artifact_filter
↓
runtime/drafts
↓
commit
↓
brain
↓
relations
↓
views
```

---

# Summary

The reasoning brain is a lightweight structured memory system that helps agents maintain reasoning continuity across long tasks.

Instead of storing large unstructured memory, it stores **small reasoning artifacts** that capture the most important elements of reasoning.

This simple structure enables agents to remain consistent, efficient, and inspectable.

---