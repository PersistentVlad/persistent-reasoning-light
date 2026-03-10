# Adapter Contract

## Purpose

This document defines the integration contract between external agent systems and the Persistent Reasoning Light engine.

Adapters act as the bridge between:

- agent runtime environments
- the reasoning engine
- the persistent reasoning brain

The contract ensures that adapters interact with the reasoning engine in a consistent and safe way.

---

## Architectural Position

Adapters sit between agent systems and the reasoning engine.

```
Agent System
↓
Reasoning Adapter
↓
Reasoning Engine
↓
Reasoning Brain
```

Adapters translate agent execution state into reasoning artifacts and reasoning context.

---

## Adapter Responsibilities

Adapters are responsible for the following tasks.

### Context Retrieval

Adapters request the working reasoning context from the reasoning engine.

Example operation:

```
load_working_context()
```

This context provides the minimal reasoning state required by the agent.

---

### Artifact Suggestion

During execution the adapter may propose reasoning artifacts.

Examples include:

- new decisions
- discovered constraints
- reusable procedures
- unresolved issues

These artifacts must pass through the artifact suggestion filter before entering the reasoning brain.

Example operation:

```
suggest_artifact(artifact)
```

---

### Task Awareness

Adapters may query the reasoning engine for active tasks.

Example operation:

```
list_active_tasks()
```

This allows agents to synchronize with the persistent reasoning state.

---

### Artifact Commit

After validation and approval, artifacts may be committed to the reasoning brain.

Example operation:

```
commit_artifact(artifact)
```

Adapters must never write directly to the artifact storage.

All modifications must pass through the reasoning engine.

---

## Adapter Restrictions

Adapters must follow these constraints.

Adapters must NOT:

- modify artifact files directly
- bypass the artifact filter
- rewrite existing artifacts
- introduce agent-specific structures into the reasoning brain

Adapters are translation layers, not storage managers.

---

## Adapter Minimalism

Adapters should remain thin and focused.

They should:

- translate agent state
- call engine operations
- return structured context

Adapters should not contain heavy reasoning logic.

---

## Multiple Adapter Support

The system may support multiple adapters simultaneously.

Examples include:

```
codex_adapter
claude_code_adapter
openclaw_adapter
zeroclaw_adapter
generic_agent_adapter
```

Each adapter follows the same contract.

---

## Summary

Adapters allow Persistent Reasoning Light to integrate with many agent systems without modifying the reasoning engine.

This architecture keeps the reasoning core stable while enabling flexible agent integration.