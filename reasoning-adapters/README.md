# Reasoning Adapters

## Purpose

The `reasoning-adapters` directory contains integration layers that connect external agent systems to the Persistent Reasoning Light engine.

The adapters act as **bridges between agents and the reasoning engine**.

This separation allows the reasoning core to remain stable while supporting many different agent platforms.

---

# Architectural Role

The architecture separates three layers:

```
Agent System
↓
Reasoning Adapter
↓
Reasoning Engine
↓
Reasoning Brain
```

The adapter is responsible for translating between:

- agent execution context
- reasoning artifacts
- engine API calls

This prevents agent-specific logic from leaking into the reasoning engine.

---

# Why Adapters Exist

Different agent systems operate differently.

Examples include:

- coding agents
- automation agents
- workflow agents
- research assistants

Each system has different:

- task models
- memory structures
- tool interfaces
- execution flows

Adapters allow the reasoning engine to integrate with all of them without modifying the core architecture.

---

# Adapter Responsibilities

A reasoning adapter typically performs the following functions.

### Context Translation

Convert agent state into structured reasoning context.

Example:

```
agent task
↓
adapter
↓
TaskCard
```

---

### Artifact Suggestions

During execution the adapter may generate artifact suggestions based on agent reasoning.

Examples:

- new decisions
- discovered constraints
- reusable procedures
- unresolved issues

These suggestions pass through the artifact suggestion pipeline.

---

### Working Context Loading

Adapters retrieve the working context from the reasoning engine and provide it to the agent.

Example:

```
agent requests context
↓
adapter
↓
engine loads working_context.json
↓
adapter formats context for agent
```

---

### Escalation Requests

If the agent encounters a complex reasoning task, the adapter may escalate reasoning.

Example flow:

```
agent cannot resolve problem
↓
adapter creates DeepQuery
↓
external reasoning system
↓
draft artifacts returned
```

The adapter ensures that external reasoning results remain **draft artifacts**.

---

# Adapter Design Principles

Adapters must follow these principles.

### Isolation

Adapters must isolate agent-specific logic from the reasoning engine.

### Minimalism

Adapters should remain thin translation layers.

### Non-invasive

Adapters must not mutate canonical artifacts directly.

### Transparency

Adapters should make reasoning operations observable and inspectable.

---

# Example Adapter Targets

Adapters may be created for many agent platforms.

Possible integrations include:

```
codex_adapter/
claude_code_adapter/
openclaw_adapter/
zeroclaw_adapter/
generic_agent_adapter/
```

Each adapter translates between the agent runtime and the reasoning engine.

---

# Example Adapter Flow

A typical execution cycle might look like:

```
agent starts task
↓
adapter loads working context
↓
agent executes step
↓
adapter detects reasoning outcome
↓
artifact suggestion created
↓
artifact_filter evaluates suggestion
↓
artifact stored as draft
```

This allows agents to gradually build a persistent reasoning brain.

---

# Adapter Contract

Adapters interact with the reasoning engine through a small interface.

Typical operations include:

```
load_working_context()

suggest_artifact()

list_active_tasks()

commit_artifact()
```

The adapter should not bypass the reasoning engine.

All artifact mutations must go through the engine.

---

# Why This Matters

Without adapters, reasoning engines become tightly coupled to specific agent platforms.

Adapters ensure that:

- the reasoning core remains stable
- integrations remain flexible
- new agent ecosystems can be supported easily

This allows Persistent Reasoning Light to function as a **universal reasoning capability for agents**.

---

# Future Direction

Over time, adapters may evolve to support:

- capability discovery
- automatic installation
- agent-first adoption flows
- reasoning capability marketplaces

Adapters are therefore a key component in enabling the broader Persistent Reasoning ecosystem.

---

End of reasoning-adapters README