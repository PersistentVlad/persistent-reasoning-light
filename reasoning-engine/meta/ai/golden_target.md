# Golden Target — Persistent Reasoning Light Code Style

This file defines the **reference execution style** for AI coding agents implementing the Persistent Reasoning Light runtime.

It provides a concrete example of what correct code should look like in this repository.

AI agents must use this file as a **style reference when generating runtime modules**.

---

# Design Philosophy

Persistent Reasoning Light is intentionally minimal.

The runtime must remain:

- small
- deterministic
- inspectable
- dependency-free

The system prioritizes **clarity and explicit behavior** over abstraction or optimization.

---

# Allowed Dependencies

Only Python **standard library** is allowed.

Do not introduce external packages.

Examples of forbidden dependencies:

- pydantic
- click
- attrs
- dataclasses-json
- networkx
- gitpython

---

# Coding Style Rules

Generated code must follow these principles:

- functions should remain small and readable
- avoid functions longer than ~50 lines
- use explicit control flow
- avoid hidden side effects
- avoid dynamic metaprogramming
- avoid unnecessary abstraction layers

Prefer simple logic over generic frameworks.

---

# Error Handling

The system must **fail explicitly** when encountering invalid input.

Use explicit exceptions such as:

```python
raise ValueError("invalid artifact type")
```
Do not introduce:
- silent fallbacks
- automatic correction
- implicit schema migration
- warning-only failures

Errors must be deterministic and predictable.

---

# Path Handling
Always use pathlib.Path.
Correct pattern:
```
from pathlib import Path

artifact_path = base_path / "tasks" / f"{artifact_id}.json"
```

Avoid:
- manual string concatenation
- implicit directory guessing
- dynamic path inference

Canonical directory mappings must be reused from shared constants.

---

# JSON Serialization

JSON must be deterministic to produce stable Git diffs.
Recommended pattern:

```
import json

json.dumps(
    obj,
    sort_keys=True,
    ensure_ascii=False,
    indent=2
)
```

Rules:
- UTF-8 encoding
- stable key ordering
- consistent indentation
- no trailing whitespace

---

# Function Style Example

```
Example of acceptable function style:

from pathlib import Path


def ensure_json_suffix(artifact_id: str) -> str:
    if not artifact_id:
        raise ValueError("artifact_id must not be empty")
    return f"{artifact_id}.json"


def validate_artifact_type(artifact_type: str, allowed_types: set[str]) -> None:
    if artifact_type not in allowed_types:
        raise ValueError(f"invalid artifact type: {artifact_type}")
```

Characteristics:
- short functions
- explicit validation
- no hidden behavior
- clear naming

---

# Forbidden Patterns

AI agents must not introduce:
- generic utility frameworks
- multi-layer abstraction hierarchies
- dynamic plugin systems
- implicit behavior
- automatic data repair
- silent schema expansion
The runtime must remain **structurally simple.**

---

# Final Principle
Persistent Reasoning Light is a **minimal architectural prototype.**
The goal is not maximum feature coverage.
The goal is:
- architectural clarity
- deterministic behavior
- inspectable reasoning infrastructure
