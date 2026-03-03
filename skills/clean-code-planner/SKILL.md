---
name: clean-code-planner
description: Use when about to write, edit, or refactor any code — even a single-line change. Apply before modifying any existing file, adding a new function, creating a new module, or any code modification of any size.
---

# Clean Code Planner

Before touching any code, produce a code plan. Always. Even for small changes.

## Step 1: Classify the Change

| Size | Criteria |
|------|----------|
| **Small** | ≤5 lines, one existing file, no new functions or types |
| **Medium** | New function/class, 2+ files, or new constants/types added |
| **Large** | New module/directory, new abstraction layer, or crosses architectural boundaries |

When uncertain between sizes → use the larger one.

## Step 2: Plan at the Right Depth

### Small Change — 3-Question Sanity Check

Answer all three before writing:

1. **DRY:** Does this already exist somewhere in the codebase?
2. **Naming:** Does the name reveal intent, not implementation?
3. **Layer:** Is this code in the right file and right layer?

If any answer is "no" or "unsure" → escalate to Medium.

### Medium Change — Full Structural Plan

Produce the Code Plan (see template below) covering:

- Which files to modify and why
- Which new files to create (constants, types, utils, etc.)
- Which functions/types to extract and where they belong
- Reuse opportunities — search the codebase before creating anything new
- Dependency direction — stable ← volatile

### Large Change — Architecture Layer Assignment + Full Plan

Produce the full Medium plan, plus assign every new component to a layer:

| Layer | What lives here | Rule |
|-------|----------------|------|
| **Entities** | Business objects, core rules | No external imports |
| **Use Cases** | Workflows, application logic | Imports Entities only |
| **Adapters** | Controllers, presenters, gateways | Imports Use Cases |
| **Framework** | DB, HTTP, UI wiring | Outermost, most volatile |

**Dependency Rule:** Imports only point inward (toward Entities). A Use Case must never import from a Framework layer. If it does, the direction is wrong — invert it.

## Step 3: Write the Code Plan

## Code Plan: [change description]
**Size:** small | medium | large

### Files to Modify
- `path/to/file` — what changes and why

### New Files to Create
- `path/to/constants.py` — [constants: X, Y, Z]
- `path/to/types.py` — [types: TypeA, TypeB]

### Functions/Types to Extract
- `function_name()` — extracted from `source_function()`
  Reason: [different rate of change / independently testable / different abstraction level]

### Reuse Opportunities
- `existing_fn()` in `path/to/utils.py` already does X — use it instead of reimplementing

### Dependency Direction
- `new_module` → `existing_stable_module` ✓ (new is more volatile, direction is correct)

### Naming Decisions
- [non-obvious names and reasoning]

Small changes: just answer the 3 questions inline. No full template needed unless any answer is "no."

## Key Principles for Planning Decisions

### SOLID

**Single Responsibility (S):** If you need "and" to describe what something does — split it. One reason to change, driven by one actor.

**Open/Closed (O):** Extend behavior by adding new code (new function, new class, new module) — not by modifying existing working code. Use interfaces, strategy patterns, or composition to make components extensible without editing their source.

**Liskov Substitution (L):** Every subtype must be usable wherever its parent type is expected, with no surprises. If overriding a method changes preconditions, postconditions, or side effects — the inheritance is wrong. Prefer composition over inheritance when substitution semantics are unclear.

**Interface Segregation (I):** Many small, focused interfaces beat one large interface. No client should depend on methods it doesn't use. Split fat interfaces into role-specific ones.

**Dependency Inversion (D):** Stable things define interfaces; volatile things implement them. Business logic never imports from DB, HTTP, or UI layers. High-level modules depend on abstractions, not concrete implementations.

### Other Core Principles

**DRY:** One authoritative source per piece of knowledge. Before writing anything new, search: does this already exist? Duplication is not only copy-paste — it's any two places that must change when one fact changes.

**YAGNI:** Do not build features, abstractions, or configurability that are not needed right now. Three similar lines of code is better than a premature abstraction. Design for current requirements, not hypothetical future ones.

**KISS:** Choose the simplest solution that solves the problem. If the design needs a diagram to explain — simplify it. Complexity is a cost; justify every piece of it.

**Composition over inheritance:** Prefer composing objects (has-a) over inheritance hierarchies (is-a). Inheritance couples parent and child tightly and makes changes fragile. Use inheritance only when there is a genuine "is-a" relationship with Liskov-safe substitution.

**Naming reveals intent:** If you can't name it cleanly, it's doing too many things. Name by what it IS or DOES, not how it works internally. `get_active_users_by_role()` not `get_users2()`. When you struggle to name something, that is a design signal — split it.

**Function abstraction level:** Each function operates at one level of abstraction. A function that orchestrates a workflow calls named sub-functions — it does not mix high-level steps with low-level implementation details in the same body.

**Extract when:** a block has a different rate of change, is independently testable, has a meaningful name that would explain the "why", or is reusable elsewhere.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Constants defined inline | Move to `constants.py` (or language equivalent) |
| Types/enums defined in service files | Move to `types.py` |
| Business logic importing from DB/HTTP | Invert the dependency — use an interface |
| New utility written without searching first | Always grep for existing implementations |
| Class created for stateless logic | Use functions; classes are for state or lifecycle |
| Function does two things | Split it; name each part |
| Name describes implementation, not concept | Name the concept (`build_user_index` not `parse_json_and_build_dict`) |
| Everything in one file | One file = one responsibility; split by type of change |
| Deep inheritance hierarchy | Flatten with composition; inherit only for genuine is-a |
| Building for "future requirements" | YAGNI — delete it and add when actually needed |
| Fat interface with many methods | Split into focused role-specific interfaces |
| Modifying working code to add a feature | Extend via new code; use abstraction to keep existing code closed |

## Language-Specific Structure

For language-specific file conventions, apply the relevant language skill alongside this plan:

- **Python:** `python-coding-rules` — covers `types.py`, `constants.py`, empty `__init__.py`, `Final[T]`, etc.
- Other languages: apply their equivalent module/file structure conventions
